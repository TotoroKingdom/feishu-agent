from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agent.diagnosis import DiagnosisOutcome, DiagnosisService
from app.agent.state import WorkflowState, ensure_state_is_safe
from app.approvals import (
    APPROVAL_ACTION_APPROVE,
    APPROVAL_ACTION_CANCEL,
    APPROVAL_ACTION_CONTINUE,
    APPROVAL_ACTION_LEGACY_CANCEL,
    APPROVAL_ACTION_MODIFY,
    APPROVAL_ACTION_REJECT,
    APPROVAL_ACTION_SUBMIT_HUMAN_INPUT,
    HUMAN_INPUT_APPROVAL_ACTIONS,
    GenerationApprovalStore,
    HumanInputApprovalStore,
    build_generation_scope,
    canonical_json_hash,
)
from app.collection.service import CollectionService, CollectionStageOutcome
from app.metrics.service import MetricsService, MetricStageOutcome
from app.publishing.service import PublishingService, PublishPlanOutcome, PublishResumeOutcome
from app.reporting.service import ReportingService, ReportStageOutcome


def build_workflow_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    approval_store: GenerationApprovalStore | None = None,
    diagnosis_service: DiagnosisService | None = None,
    collection_service: CollectionService | None = None,
    metrics_service: MetricsService | None = None,
    reporting_service: ReportingService | None = None,
    publishing_service: PublishingService | None = None,
    human_input_store: HumanInputApprovalStore | None = None,
) -> Any:
    store = approval_store or _MissingGenerationApprovalStore()
    diagnostician = diagnosis_service or _MissingDiagnosisService()
    collector = collection_service or _MissingCollectionService()
    metrics = metrics_service or _MissingMetricsService()
    reporter = reporting_service or _MissingReportingService()
    publisher = publishing_service or _MissingPublishingService()
    human_store = human_input_store or _MissingHumanInputApprovalStore()
    builder = StateGraph(WorkflowState)
    builder.add_node("load_project_config", _load_project_config)
    builder.add_node("build_generation_scope", _build_generation_scope)
    builder.add_node("request_generation_confirmation", _request_generation_confirmation(store))
    builder.add_node("wait_generation_confirmation", _wait_generation_confirmation(store))
    builder.add_node("diagnose_problem", _diagnose_problem(diagnostician))
    builder.add_node("request_human_input", _request_human_input(human_store))
    builder.add_node("wait_human_input", _wait_human_input(human_store))
    builder.add_node("collect_feishu_data", _collect_feishu_data(collector))
    builder.add_node("collect_github_data", _collect_github_data(collector))
    builder.add_node("normalize_data", _normalize_data(collector))
    builder.add_node("validate_data", _validate_data(collector))
    builder.add_node("calculate_metrics", _calculate_metrics(metrics))
    builder.add_node("build_evidence", _build_evidence(reporter))
    builder.add_node("generate_structured_report", _generate_structured_report(reporter))
    builder.add_node("verify_grounding", _verify_grounding(reporter))
    builder.add_node("render_report", _render_report(reporter))
    builder.add_node("build_publish_plan", _build_publish_plan(publisher))
    builder.add_node("request_publish_confirmation", _request_publish_confirmation(publisher))
    builder.add_node("wait_publish_confirmation", _wait_publish_confirmation(publisher))
    builder.add_node("create_feishu_document", _create_feishu_document(publisher))
    builder.add_node("send_group_summary", _send_group_summary(publisher))
    builder.add_node("archive_report_record", _archive_report_record(publisher))
    builder.add_node("verify_side_effects", _verify_side_effects(publisher))
    builder.add_node("compensate_partial_failure", _compensate_partial_failure(publisher))
    builder.add_node("cancel_run", _cancel_run)
    builder.add_node("complete_run", _complete_run)
    builder.add_edge(START, "load_project_config")
    builder.add_edge("load_project_config", "build_generation_scope")
    builder.add_edge("build_generation_scope", "request_generation_confirmation")
    builder.add_edge("request_generation_confirmation", "wait_generation_confirmation")
    builder.add_edge("request_human_input", "wait_human_input")
    builder.add_conditional_edges(
        "wait_generation_confirmation",
        _generation_approval_route,
        {
            "build_generation_scope": "build_generation_scope",
            "collect_feishu_data": "collect_feishu_data",
            "cancel_run": "cancel_run",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "wait_human_input",
        _human_input_route,
        {
            "validate_data": "validate_data",
            "collect_feishu_data": "collect_feishu_data",
            "collect_github_data": "collect_github_data",
            "normalize_data": "normalize_data",
            "calculate_metrics": "calculate_metrics",
            "build_evidence": "build_evidence",
            "generate_structured_report": "generate_structured_report",
            "verify_grounding": "verify_grounding",
            "render_report": "render_report",
            "build_publish_plan": "build_publish_plan",
            "request_human_input": "request_human_input",
            "wait_human_input": "wait_human_input",
            "complete_run": "complete_run",
            "cancel_run": "cancel_run",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "diagnose_problem",
        _diagnosis_route,
        {
            "collect_feishu_data": "collect_feishu_data",
            "collect_github_data": "collect_github_data",
            "normalize_data": "normalize_data",
            "validate_data": "validate_data",
            "request_human_input": "request_human_input",
            "wait_human_input": "wait_human_input",
            "calculate_metrics": "calculate_metrics",
            "build_evidence": "build_evidence",
            "generate_structured_report": "generate_structured_report",
            "verify_grounding": "verify_grounding",
            "render_report": "render_report",
            "build_publish_plan": "build_publish_plan",
            "complete_run": "complete_run",
            "cancel_run": "cancel_run",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "collect_feishu_data",
        _collection_route,
        {
            "collect_github_data": "collect_github_data",
            "diagnose_problem": "diagnose_problem",
            "cancel_run": "cancel_run",
            "request_human_input": "request_human_input",
            "wait_human_input": "wait_human_input",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "collect_github_data",
        _collection_route,
        {
            "normalize_data": "normalize_data",
            "diagnose_problem": "diagnose_problem",
            "cancel_run": "cancel_run",
            "request_human_input": "request_human_input",
            "wait_human_input": "wait_human_input",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "normalize_data",
        _collection_route,
        {
            "validate_data": "validate_data",
            "diagnose_problem": "diagnose_problem",
            "cancel_run": "cancel_run",
            "request_human_input": "request_human_input",
            "wait_human_input": "wait_human_input",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "validate_data",
        _collection_route,
        {
            "calculate_metrics": "calculate_metrics",
            "diagnose_problem": "diagnose_problem",
            "cancel_run": "cancel_run",
            "request_human_input": "request_human_input",
            "wait_human_input": "wait_human_input",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "calculate_metrics",
        _collection_route,
        {
            "build_evidence": "build_evidence",
            "diagnose_problem": "diagnose_problem",
            "cancel_run": "cancel_run",
            "request_human_input": "request_human_input",
            "wait_human_input": "wait_human_input",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "build_evidence",
        _collection_route,
        {
            "generate_structured_report": "generate_structured_report",
            "diagnose_problem": "diagnose_problem",
            "cancel_run": "cancel_run",
            "request_human_input": "request_human_input",
            "wait_human_input": "wait_human_input",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "generate_structured_report",
        _collection_route,
        {
            "verify_grounding": "verify_grounding",
            "diagnose_problem": "diagnose_problem",
            "cancel_run": "cancel_run",
            "request_human_input": "request_human_input",
            "wait_human_input": "wait_human_input",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "verify_grounding",
        _collection_route,
        {
            "render_report": "render_report",
            "diagnose_problem": "diagnose_problem",
            "cancel_run": "cancel_run",
            "request_human_input": "request_human_input",
            "wait_human_input": "wait_human_input",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "render_report",
        _collection_route,
        {
            "build_publish_plan": "build_publish_plan",
            "diagnose_problem": "diagnose_problem",
            "cancel_run": "cancel_run",
            "request_human_input": "request_human_input",
            "wait_human_input": "wait_human_input",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "build_publish_plan",
        _collection_route,
        {
            "request_publish_confirmation": "request_publish_confirmation",
            "diagnose_problem": "diagnose_problem",
            "cancel_run": "cancel_run",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "request_publish_confirmation",
        _collection_route,
        {
            "wait_publish_confirmation": "wait_publish_confirmation",
            "diagnose_problem": "diagnose_problem",
            "cancel_run": "cancel_run",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "wait_publish_confirmation",
        _publish_approval_route,
        {
            "wait_publish_confirmation": "wait_publish_confirmation",
            "build_generation_scope": "build_generation_scope",
            "generate_structured_report": "generate_structured_report",
            "create_feishu_document": "create_feishu_document",
            "cancel_run": "cancel_run",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "create_feishu_document",
        _publish_side_effect_route,
        {
            "send_group_summary": "send_group_summary",
            "cancel_run": "cancel_run",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "send_group_summary",
        _publish_side_effect_route,
        {
            "archive_report_record": "archive_report_record",
            "cancel_run": "cancel_run",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "archive_report_record",
        _publish_side_effect_route,
        {
            "verify_side_effects": "verify_side_effects",
            "cancel_run": "cancel_run",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "verify_side_effects",
        _publish_side_effect_route,
        {
            "compensate_partial_failure": "compensate_partial_failure",
            "complete_run": "complete_run",
            "cancel_run": "cancel_run",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "compensate_partial_failure",
        _publish_side_effect_route,
        {
            "cancel_run": "cancel_run",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "complete_run",
        _publish_side_effect_route,
        {
            "cancel_run": "cancel_run",
            END: END,
        },
    )
    return builder.compile(checkpointer=checkpointer, name="weekly_report.v1")


def _load_project_config(state: WorkflowState) -> dict[str, object]:
    ensure_state_is_safe(state)
    report_period = _ensure_report_period(state)
    return {
        "current_stage": "config_loaded",
        "current_node": "build_generation_scope",
        "report_period": report_period,
        "control": {
            "requested_action": None,
            "resume_from": "load_project_config",
            "cancel_requested": False,
            "scope_override": None,
        },
        "requested_action": None,
        "resume_from": "load_project_config",
        "cancel_requested": False,
    }


def _build_generation_scope(state: WorkflowState) -> dict[str, object]:
    ensure_state_is_safe(state)
    scope_revision = int(state.get("scope_revision", 1))
    requested_action = _normalize_action_if_present(state.get("requested_action"))
    if requested_action == APPROVAL_ACTION_MODIFY:
        scope_revision += 1

    scope = build_generation_scope(state)
    approval = {
        "active_approval_ref": None,
        "approval_type": "generation",
        "approval_revision": scope_revision,
        "status": "none",
        "approved_scope_hash": None,
        "challenge_id": None,
        "requested_from": [],
    }
    return {
        "scope_revision": scope_revision,
        "approval_revision": scope_revision,
        "scope": scope,
        "approval": approval,
        "current_stage": "requesting_confirmation",
        "current_node": "request_generation_confirmation",
        "requested_action": None,
        "resume_from": "build_generation_scope",
        "control": {
            "requested_action": None,
            "resume_from": "build_generation_scope",
            "cancel_requested": False,
            "scope_override": None,
        },
        "cancel_requested": False,
    }


def _request_generation_confirmation(
    store: GenerationApprovalStore,
):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        scope = _require_scope(state)
        scope_revision = int(state.get("scope_revision", 1))
        approval = store.ensure_pending_generation_approval(
            run_id=state["run_id"],
            revision=scope_revision,
            scope_hash=_require_scope_hash(scope),
            requested_from=_requested_from(state),
        )
        return {
            "approval": {
                "active_approval_ref": approval.id,
                "approval_type": approval.approval_type,
                "approval_revision": approval.revision,
                "status": approval.status,
                "approved_scope_hash": None,
                "challenge_id": approval.challenge_id,
                "requested_from": list(approval.requested_from),
            },
            "current_stage": "waiting_confirmation",
            "current_node": "wait_generation_confirmation",
            "requested_action": None,
            "resume_from": "request_generation_confirmation",
            "control": {
                "requested_action": None,
                "resume_from": "request_generation_confirmation",
                "cancel_requested": False,
                "scope_override": None,
            },
            "cancel_requested": False,
        }

    return _node


def _wait_generation_confirmation(store: GenerationApprovalStore):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        scope = _require_scope(state)
        approval = _require_approval(state)
        prompt = {
            "run_id": state["run_id"],
            "current_stage": state["current_stage"],
            "current_node": "wait_generation_confirmation",
            "scope_revision": state.get("scope_revision", 1),
            "approval_revision": state.get("approval_revision", 1),
            "challenge_id": approval["challenge_id"],
            "approval_ref": approval["active_approval_ref"],
            "presented_hash": _require_scope_hash(scope),
            "allowed_actions": [
                APPROVAL_ACTION_APPROVE,
                APPROVAL_ACTION_MODIFY,
                APPROVAL_ACTION_CANCEL,
                APPROVAL_ACTION_REJECT,
            ],
        }
        resume_payload = interrupt(prompt)
        if not isinstance(resume_payload, Mapping):
            raise ValueError("resume payload must be a mapping")
        ensure_state_is_safe(resume_payload)

        action = _normalize_action(resume_payload.get("action"))
        challenge_id = _resume_challenge_id(resume_payload)
        expected_challenge_id = str(approval["challenge_id"])
        if challenge_id != expected_challenge_id:
            raise ValueError("approval challenge_id mismatch")
        if _resume_revision(resume_payload) != int(state.get("approval_revision", 1)):
            raise ValueError("approval revision mismatch")
        if _resume_presented_hash(resume_payload) != _require_scope_hash(scope):
            raise ValueError("presented scope hash mismatch")

        actor_id = _resume_actor_id(resume_payload, state)
        if action == APPROVAL_ACTION_MODIFY:
            override = _resume_scope_override(resume_payload)
            store.mark_generation_approval_decision(
                challenge_id=challenge_id,
                action=APPROVAL_ACTION_MODIFY,
                actor_id=actor_id,
                supplement={"scope_override": override},
            )
            return {
                "requested_action": APPROVAL_ACTION_MODIFY,
                "scope_override": override,
                "approval": {
                    "active_approval_ref": approval["active_approval_ref"],
                    "approval_type": approval["approval_type"],
                    "approval_revision": approval["approval_revision"],
                    "status": "superseded",
                    "approved_scope_hash": None,
                    "challenge_id": approval["challenge_id"],
                    "requested_from": approval["requested_from"],
                },
                "current_stage": "building_generation_scope",
                "current_node": "build_generation_scope",
                "resume_from": "wait_generation_confirmation",
                "control": {
                    "requested_action": APPROVAL_ACTION_MODIFY,
                    "resume_from": "wait_generation_confirmation",
                    "cancel_requested": False,
                    "scope_override": override,
                },
                "cancel_requested": False,
            }

        decision = store.mark_generation_approval_decision(
            challenge_id=challenge_id,
            action=action,
            actor_id=actor_id,
        )
        if action in {APPROVAL_ACTION_CANCEL, APPROVAL_ACTION_LEGACY_CANCEL}:
            current_stage = "cancelled"
        elif action == APPROVAL_ACTION_REJECT:
            current_stage = "rejected"
        else:
            current_stage = "collecting_feishu_data"

        return {
            "requested_action": action,
            "approval": {
                "active_approval_ref": approval["active_approval_ref"],
                "approval_type": approval["approval_type"],
                "approval_revision": approval["approval_revision"],
                "status": decision.status,
                "approved_scope_hash": _require_scope_hash(scope)
                if decision.status == "approved"
                else None,
                "challenge_id": approval["challenge_id"],
                "requested_from": approval["requested_from"],
            },
            "current_stage": current_stage,
            "current_node": "collect_feishu_data"
            if current_stage == "collecting_feishu_data"
            else "complete_run",
            "resume_from": "wait_generation_confirmation",
            "control": {
                "requested_action": action,
                "resume_from": "wait_generation_confirmation",
                "cancel_requested": decision.status == "cancelled",
                "scope_override": None,
            },
            "cancel_requested": decision.status == "cancelled",
        }

    return _node


def _request_human_input(store: HumanInputApprovalStore):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        diagnosis = _require_diagnosis(state)
        requested_fields = _human_input_requested_fields(diagnosis)
        resume_from = _human_input_resume_from(diagnosis)
        prompt_schema = {
            "problem_key": str(
                diagnosis.get("problem_key") or diagnosis.get("active_problem_key") or ""
            ),
            "requested_fields": requested_fields,
            "resume_from": resume_from,
            "checkpoint_id": str(diagnosis.get("checkpoint_id") or ""),
        }
        approval_revision = int(state.get("approval_revision", 1)) + 1
        approval = store.ensure_pending_human_input_approval(
            run_id=state["run_id"],
            revision=approval_revision,
            request_payload_hash=canonical_json_hash(prompt_schema),
            requested_from=_requested_from(state),
        )
        return {
            "approval_revision": approval.revision,
            "approval": {
                "active_approval_ref": approval.id,
                "approval_type": approval.approval_type,
                "approval_revision": approval.revision,
                "status": approval.status,
                "approved_scope_hash": None,
                "approved_plan_hash": None,
                "request_payload_hash": approval.request_payload_hash,
                "challenge_id": approval.challenge_id,
                "requested_from": list(approval.requested_from),
            },
            "current_stage": "waiting_human_input",
            "current_node": "wait_human_input",
            "requested_action": None,
            "resume_from": "request_human_input",
            "control": {
                "requested_action": None,
                "resume_from": "request_human_input",
                "cancel_requested": False,
                "scope_override": None,
            },
            "cancel_requested": False,
        }

    return _node


def _wait_human_input(store: HumanInputApprovalStore):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        diagnosis = _require_diagnosis(state)
        approval = _require_approval(state)
        requested_fields = _human_input_requested_fields(diagnosis)
        resume_from = _human_input_resume_from(diagnosis)
        prompt = {
            "run_id": state["run_id"],
            "current_stage": state["current_stage"],
            "current_node": "wait_human_input",
            "approval_revision": state.get("approval_revision", 1),
            "challenge_id": approval["challenge_id"],
            "approval_ref": approval["active_approval_ref"],
            "presented_hash": _require_request_payload_hash(approval),
            "problem_key": diagnosis.get("problem_key") or diagnosis.get("active_problem_key"),
            "attempt": diagnosis.get("attempt"),
            "reason": diagnosis.get("reason") or state.get("error_summary"),
            "required_fields": requested_fields,
            "resume_from": resume_from,
            "checkpoint_id": diagnosis.get("checkpoint_id") or approval["active_approval_ref"],
            "allowed_actions": [
                APPROVAL_ACTION_SUBMIT_HUMAN_INPUT,
                APPROVAL_ACTION_CANCEL,
                APPROVAL_ACTION_LEGACY_CANCEL,
            ],
        }
        resume_payload = interrupt(prompt)
        if not isinstance(resume_payload, Mapping):
            raise ValueError("resume payload must be a mapping")
        ensure_state_is_safe(resume_payload)

        action = _normalize_human_input_action(resume_payload.get("action"))
        challenge_id = _resume_challenge_id(resume_payload)
        expected_challenge_id = str(approval["challenge_id"])
        if challenge_id != expected_challenge_id:
            raise ValueError("approval challenge_id mismatch")
        if _resume_revision(resume_payload) != int(state.get("approval_revision", 1)):
            raise ValueError("approval revision mismatch")
        if _resume_presented_hash(resume_payload) != _require_request_payload_hash(approval):
            raise ValueError("presented human input hash mismatch")

        actor_id = _resume_actor_id(resume_payload, state)
        if action in {APPROVAL_ACTION_CANCEL, APPROVAL_ACTION_LEGACY_CANCEL}:
            decision = store.mark_human_input_decision(
                challenge_id=challenge_id,
                action=APPROVAL_ACTION_CANCEL,
                actor_id=actor_id,
            )
            return {
                "requested_action": APPROVAL_ACTION_CANCEL,
                "approval": {
                    "active_approval_ref": approval["active_approval_ref"],
                    "approval_type": approval["approval_type"],
                    "approval_revision": approval["approval_revision"],
                    "status": decision.status,
                    "approved_scope_hash": None,
                    "approved_plan_hash": None,
                    "request_payload_hash": approval["request_payload_hash"],
                    "challenge_id": approval["challenge_id"],
                    "requested_from": approval["requested_from"],
                },
                "current_stage": "cancelled",
                "current_node": "complete_run",
                "resume_from": "wait_human_input",
                "control": {
                    "requested_action": APPROVAL_ACTION_CANCEL,
                    "resume_from": "wait_human_input",
                    "cancel_requested": True,
                    "scope_override": None,
                },
                "cancel_requested": True,
            }

        supplement = _resume_supplement(resume_payload, APPROVAL_ACTION_SUBMIT_HUMAN_INPUT)
        _validate_human_input_supplement(supplement, requested_fields)
        decision = store.mark_human_input_decision(
            challenge_id=challenge_id,
            action=APPROVAL_ACTION_SUBMIT_HUMAN_INPUT,
            actor_id=actor_id,
            supplement=supplement,
        )
        return {
            "requested_action": APPROVAL_ACTION_SUBMIT_HUMAN_INPUT,
            "approval": {
                "active_approval_ref": approval["active_approval_ref"],
                "approval_type": approval["approval_type"],
                "approval_revision": approval["approval_revision"],
                "status": decision.status,
                "approved_scope_hash": None,
                "approved_plan_hash": None,
                "request_payload_hash": approval["request_payload_hash"],
                "challenge_id": approval["challenge_id"],
                "requested_from": approval["requested_from"],
            },
            "current_stage": _stage_for_node(resume_from),
            "current_node": resume_from,
            "resume_from": "wait_human_input",
            "control": {
                "requested_action": APPROVAL_ACTION_SUBMIT_HUMAN_INPUT,
                "resume_from": "wait_human_input",
                "cancel_requested": False,
                "scope_override": None,
            },
            "cancel_requested": False,
        }

    return _node


def _diagnose_problem(diagnosis_service: DiagnosisService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        outcome = diagnosis_service.diagnose_problem(state)
        if outcome.status == "blocked":
            return {
                "diagnosis": outcome.diagnosis_patch,
                "current_stage": "blocked",
                "current_node": str(
                    state.get("diagnosis", {}).get("source_node")
                    or state.get("current_node")
                    or "diagnose_problem"
                ),
                "error_code": state.get("error_code"),
                "error_summary": state.get("error_summary"),
            }
        next_node = outcome.next_node or "complete_run"
        return {
            "diagnosis": outcome.diagnosis_patch,
            "current_stage": _stage_for_node(next_node),
            "current_node": next_node,
            "requested_action": None,
            "resume_from": "diagnose_problem",
            "control": {
                "requested_action": None,
                "resume_from": "diagnose_problem",
                "cancel_requested": False,
            },
            "cancel_requested": False,
        }

    return _node


def _collect_feishu_data(collector: CollectionService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        outcome = collector.collect_feishu_data(state["run_id"], _require_scope(state))
        if outcome.status == "blocked":
            return _diagnosis_block(
                state,
                source_node="collect_feishu_data",
                error_code=outcome.error_code,
                error_summary=outcome.error_summary,
                source_batch_refs=_extend_unique(
                    state.get("source_batch_refs", []),
                    outcome.source_batch_refs or [outcome.source_batch_ref],
                ),
            )
        return {
            "current_stage": "collecting_github_data",
            "current_node": "collect_github_data",
            "source_batch_refs": _extend_unique(
                state.get("source_batch_refs", []),
                outcome.source_batch_refs or [outcome.source_batch_ref],
            ),
            "error_code": None,
            "error_summary": None,
        }

    return _node


def _collect_github_data(collector: CollectionService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        outcome = collector.collect_github_data(state["run_id"], _require_scope(state))
        if outcome.status == "blocked":
            return _diagnosis_block(
                state,
                source_node="collect_github_data",
                error_code=outcome.error_code,
                error_summary=outcome.error_summary,
                source_batch_refs=_extend_unique(
                    state.get("source_batch_refs", []),
                    outcome.source_batch_refs or [outcome.source_batch_ref],
                ),
            )
        return {
            "current_stage": "normalizing_data",
            "current_node": "normalize_data",
            "source_batch_refs": _extend_unique(
                state.get("source_batch_refs", []),
                outcome.source_batch_refs or [outcome.source_batch_ref],
            ),
            "error_code": None,
            "error_summary": None,
        }

    return _node


def _normalize_data(collector: CollectionService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        outcome = collector.normalize_data(state["run_id"], _require_scope(state))
        if outcome.status == "blocked":
            return _diagnosis_block(
                state,
                source_node="normalize_data",
                error_code=outcome.error_code,
                error_summary=outcome.error_summary,
                normalized_snapshot_ref=state.get("normalized_snapshot_ref"),
            )
        return {
            "current_stage": "validating_data",
            "current_node": "validate_data",
            "normalized_snapshot_ref": outcome.normalized_snapshot_ref,
            "error_code": None,
            "error_summary": None,
        }

    return _node


def _validate_data(collector: CollectionService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        normalized_snapshot_ref = state.get("normalized_snapshot_ref")
        if not isinstance(normalized_snapshot_ref, str) or not normalized_snapshot_ref:
            return _diagnosis_block(
                state,
                source_node="validate_data",
                error_code="NORMALIZED_SNAPSHOT_MISSING",
                error_summary="Normalized snapshot missing from state",
            )
        outcome = collector.validate_data(state["run_id"], normalized_snapshot_ref)
        if outcome.status == "blocked":
            return _diagnosis_block(
                state,
                source_node="validate_data",
                error_code=outcome.error_code,
                error_summary=outcome.error_summary,
                validation_result_ref=outcome.validation_result_ref,
            )
        return {
            "current_stage": "calculating_metrics",
            "current_node": "calculate_metrics",
            "validation_result_ref": outcome.validation_result_ref,
            "error_code": None,
            "error_summary": None,
        }

    return _node


def _calculate_metrics(metrics_service: MetricsService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        normalized_snapshot_ref = state.get("normalized_snapshot_ref")
        if not isinstance(normalized_snapshot_ref, str) or not normalized_snapshot_ref:
            return _diagnosis_block(
                state,
                source_node="calculate_metrics",
                error_code="NORMALIZED_SNAPSHOT_MISSING",
                error_summary="Normalized snapshot missing from state",
            )
        outcome = metrics_service.calculate_metrics(state["run_id"], normalized_snapshot_ref)
        if outcome.status == "blocked":
            return _diagnosis_block(
                state,
                source_node="calculate_metrics",
                error_code=outcome.error_code,
                error_summary=outcome.error_summary,
            )
        return {
            "current_stage": "building_evidence",
            "current_node": "build_evidence",
            "metrics_ref": outcome.metrics_ref,
            "error_code": None,
            "error_summary": None,
        }

    return _node


def _build_evidence(reporter: ReportingService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        metrics_ref = state.get("metrics_ref")
        if not isinstance(metrics_ref, str) or not metrics_ref:
            return _diagnosis_block(
                state,
                source_node="build_evidence",
                error_code="METRICS_SNAPSHOT_MISSING",
                error_summary="Metric snapshot missing from state",
            )
        outcome = reporter.build_evidence(state["run_id"], metrics_ref)
        if outcome.status == "blocked":
            return _diagnosis_block(
                state,
                source_node="build_evidence",
                error_code=outcome.error_code,
                error_summary=outcome.error_summary,
                evidence_set_ref=outcome.evidence_set_ref,
            )
        return {
            "current_stage": "generating_structured_report",
            "current_node": "generate_structured_report",
            "evidence_set_ref": outcome.evidence_set_ref,
            "error_code": None,
            "error_summary": None,
        }

    return _node


def _generate_structured_report(reporter: ReportingService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        evidence_set_ref = state.get("evidence_set_ref")
        if not isinstance(evidence_set_ref, str) or not evidence_set_ref:
            return _diagnosis_block(
                state,
                source_node="generate_structured_report",
                error_code="EVIDENCE_SET_MISSING",
                error_summary="Evidence set missing from state",
            )
        outcome = reporter.generate_structured_report(
            state["run_id"],
            evidence_set_ref,
            force_new_version=bool(state.get("report_regeneration_requested")),
        )
        if outcome.status == "blocked":
            return _diagnosis_block(
                state,
                source_node="generate_structured_report",
                error_code=outcome.error_code,
                error_summary=outcome.error_summary,
                report_version_ref=outcome.report_version_ref,
            )
        return {
            "current_stage": "verifying_grounding",
            "current_node": "verify_grounding",
            "report_version_ref": outcome.report_version_ref,
            "report_regeneration_requested": False,
            "error_code": None,
            "error_summary": None,
        }

    return _node


def _verify_grounding(reporter: ReportingService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        report_version_ref = state.get("report_version_ref")
        if not isinstance(report_version_ref, str) or not report_version_ref:
            return _diagnosis_block(
                state,
                source_node="verify_grounding",
                error_code="REPORT_VERSION_MISSING",
                error_summary="Report version missing from state",
            )
        outcome = reporter.verify_grounding(state["run_id"], report_version_ref)
        if outcome.status == "blocked":
            return _diagnosis_block(
                state,
                source_node="verify_grounding",
                error_code=outcome.error_code,
                error_summary=outcome.error_summary,
                report_version_ref=outcome.report_version_ref,
            )
        return {
            "current_stage": "rendering_report",
            "current_node": "render_report",
            "report_version_ref": outcome.report_version_ref,
            "error_code": None,
            "error_summary": None,
        }

    return _node


def _render_report(reporter: ReportingService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        report_version_ref = state.get("report_version_ref")
        if not isinstance(report_version_ref, str) or not report_version_ref:
            return _diagnosis_block(
                state,
                source_node="render_report",
                error_code="REPORT_VERSION_MISSING",
                error_summary="Report version missing from state",
            )
        outcome = reporter.render_report(state["run_id"], report_version_ref)
        if outcome.status == "blocked":
            return _diagnosis_block(
                state,
                source_node="render_report",
                error_code=outcome.error_code,
                error_summary=outcome.error_summary,
                report_version_ref=outcome.report_version_ref,
            )
        return {
            "current_stage": "report_rendered",
            "current_node": "build_publish_plan",
            "report_version_ref": outcome.report_version_ref,
            "rendered_report_ref": outcome.rendered_report_ref,
            "error_code": None,
            "error_summary": None,
        }

    return _node


def _build_publish_plan(publisher: PublishingService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        report_version_ref = state.get("report_version_ref")
        if not isinstance(report_version_ref, str) or not report_version_ref:
            return {
                "current_stage": "blocked",
                "current_node": "build_publish_plan",
                "error_code": "REPORT_VERSION_MISSING",
                "error_summary": "Report version missing from state",
            }
        outcome = publisher.build_publish_plan(state["run_id"], report_version_ref)
        if outcome.status == "blocked":
            return {
                "current_stage": "blocked",
                "current_node": "build_publish_plan",
                "publish_plan_ref": outcome.publish_plan_ref or state.get("publish_plan_ref"),
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
        return {
            "publish_plan_ref": outcome.publish_plan_ref,
            "publish": {
                "plan_hash": outcome.plan_hash,
                "operation_refs": [],
                "next_operation_index": 0,
                "side_effect_status": "not_started",
            },
            "approval": {
                "active_approval_ref": None,
                "approval_type": "publish",
                "approval_revision": outcome.publish_plan_version,
                "status": "none",
                "approved_scope_hash": None,
                "approved_plan_hash": None,
                "challenge_id": None,
                "requested_from": [],
            },
            "approval_revision": outcome.publish_plan_version,
            "current_stage": "building_publish_plan",
            "current_node": "request_publish_confirmation",
            "requested_action": None,
            "resume_from": "build_publish_plan",
            "control": {
                "requested_action": None,
                "resume_from": "build_publish_plan",
                "cancel_requested": False,
            },
            "cancel_requested": False,
        }

    return _node


def _request_publish_confirmation(publisher: PublishingService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        publish_plan_ref = state.get("publish_plan_ref")
        if not isinstance(publish_plan_ref, str) or not publish_plan_ref:
            return {
                "current_stage": "blocked",
                "current_node": "request_publish_confirmation",
                "error_code": "PUBLISH_PLAN_MISSING",
                "error_summary": "Publish plan missing from state",
            }
        approval = publisher.request_publish_confirmation(
            run_id=state["run_id"],
            publish_plan_ref=publish_plan_ref,
            requested_from=_requested_from(state),
        )
        if approval.status == "blocked":
            return {
                "current_stage": "blocked",
                "current_node": "request_publish_confirmation",
                "error_code": approval.error_code,
                "error_summary": approval.error_summary,
                "publish_plan_ref": approval.publish_plan_ref or publish_plan_ref,
            }
        return {
            "publish_plan_ref": approval.publish_plan_ref,
            "publish": {
                "plan_hash": approval.plan_hash,
                "operation_refs": [],
                "next_operation_index": 0,
                "side_effect_status": "not_started",
            },
            "approval": {
                "active_approval_ref": approval.approval_ref,
                "approval_type": "publish",
                "approval_revision": approval.approval_revision,
                "status": "pending",
                "approved_scope_hash": None,
                "approved_plan_hash": None,
                "challenge_id": approval.challenge_id,
                "requested_from": _requested_from(state),
            },
            "approval_revision": approval.approval_revision,
            "current_stage": "waiting_publish_approval",
            "current_node": "wait_publish_confirmation",
            "requested_action": None,
            "resume_from": "request_publish_confirmation",
            "control": {
                "requested_action": None,
                "resume_from": "request_publish_confirmation",
                "cancel_requested": False,
            },
            "cancel_requested": False,
        }

    return _node


def _wait_publish_confirmation(publisher: PublishingService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        publish_plan_ref = state.get("publish_plan_ref")
        publish = state.get("publish")
        approval = _require_approval(state)
        if not isinstance(publish_plan_ref, str) or not publish_plan_ref:
            return {
                "current_stage": "blocked",
                "current_node": "wait_publish_confirmation",
                "error_code": "PUBLISH_PLAN_MISSING",
                "error_summary": "Publish plan missing from state",
            }
        plan_hash = _require_publish_plan_hash(publish)
        prompt = {
            "run_id": state["run_id"],
            "current_stage": state["current_stage"],
            "current_node": "wait_publish_confirmation",
            "publish_plan_ref": publish_plan_ref,
            "approval_revision": state.get("approval_revision", approval["approval_revision"]),
            "challenge_id": approval["challenge_id"],
            "approval_ref": approval["active_approval_ref"],
            "presented_hash": plan_hash,
            "allowed_actions": [
                "approve_publish",
                "regenerate_report",
                "update_supplement",
                "cancel_publish",
            ],
        }
        resume_payload = interrupt(prompt)
        if not isinstance(resume_payload, Mapping):
            raise ValueError("resume payload must be a mapping")
        ensure_state_is_safe(resume_payload)

        action = _normalize_publish_action(resume_payload.get("action"))
        challenge_id = _resume_challenge_id(resume_payload)
        expected_challenge_id = str(approval["challenge_id"])
        if challenge_id != expected_challenge_id:
            raise ValueError("approval challenge_id mismatch")
        if _resume_revision(resume_payload) != int(state.get("approval_revision", 1)):
            raise ValueError("approval revision mismatch")
        supplement = _resume_supplement(resume_payload, action)
        scope_override = _scope_override_from_supplement(supplement)
        if _resume_presented_hash(resume_payload) != plan_hash:
            outcome = publisher.resume_publish_confirmation(
                run_id=state["run_id"],
                publish_plan_ref=publish_plan_ref,
                approval_ref=str(approval["active_approval_ref"]),
                challenge_id=challenge_id,
                approval_revision=int(approval["approval_revision"]),
                presented_hash=_resume_presented_hash(resume_payload),
                action=action,
                actor_id=_resume_actor_id(resume_payload, state),
                requested_from=approval["requested_from"],
                supplement=supplement,
            )
            if outcome.status == "blocked":
                return {
                    "current_stage": "blocked",
                    "current_node": "wait_publish_confirmation",
                    "publish_plan_ref": publish_plan_ref,
                    "error_code": outcome.error_code,
                    "error_summary": outcome.error_summary,
                }
            if action == "update_supplement" and scope_override is not None:
                return {
                    "publish_plan_ref": None,
                    "publish": {
                        "plan_hash": None,
                        "operation_refs": state.get("publish", {}).get("operation_refs", []),
                        "next_operation_index": 0,
                        "side_effect_status": "not_started",
                    },
                    "approval": {
                        "active_approval_ref": None,
                        "approval_type": None,
                        "approval_revision": int(approval["approval_revision"]),
                        "status": "superseded",
                        "approved_scope_hash": None,
                        "approved_plan_hash": None,
                        "challenge_id": None,
                        "requested_from": approval["requested_from"],
                    },
                    "approval_revision": int(approval["approval_revision"]),
                    "scope_override": scope_override,
                    "requested_action": APPROVAL_ACTION_MODIFY,
                    "current_stage": "building_generation_scope",
                    "current_node": "build_generation_scope",
                    "resume_from": "wait_publish_confirmation",
                    "control": {
                        "requested_action": APPROVAL_ACTION_MODIFY,
                        "resume_from": "wait_publish_confirmation",
                        "cancel_requested": False,
                        "scope_override": scope_override,
                    },
                    "cancel_requested": False,
                    "report_regeneration_requested": False,
                }
            return {
                "publish_plan_ref": outcome.publish_plan_ref,
                "publish": {
                    "plan_hash": outcome.plan_hash,
                    "operation_refs": state.get("publish", {}).get("operation_refs", []),
                    "next_operation_index": 0,
                    "side_effect_status": "not_started",
                },
                "approval": {
                    "active_approval_ref": outcome.approval_ref,
                    "approval_type": "publish",
                    "approval_revision": outcome.approval_revision,
                    "status": "pending",
                    "approved_scope_hash": None,
                    "approved_plan_hash": None,
                    "challenge_id": outcome.challenge_id,
                    "requested_from": approval["requested_from"],
                },
                "approval_revision": outcome.approval_revision,
                "current_stage": outcome.current_stage,
                "current_node": outcome.current_node,
                "requested_action": action,
                "resume_from": "wait_publish_confirmation",
                "control": {
                    "requested_action": action,
                    "resume_from": "wait_publish_confirmation",
                    "cancel_requested": False,
                    "supplement": supplement,
                },
                "cancel_requested": False,
                "report_regeneration_requested": action
                in {"regenerate_report", "update_supplement"}
                and scope_override is None,
            }

        outcome = publisher.resume_publish_confirmation(
            run_id=state["run_id"],
            publish_plan_ref=publish_plan_ref,
            approval_ref=str(approval["active_approval_ref"]),
            challenge_id=challenge_id,
            approval_revision=int(approval["approval_revision"]),
            presented_hash=plan_hash,
            action=action,
            actor_id=_resume_actor_id(resume_payload, state),
            requested_from=approval["requested_from"],
            supplement=_resume_supplement(resume_payload, action),
        )
        if outcome.status == "blocked":
            return {
                "current_stage": "blocked",
                "current_node": "wait_publish_confirmation",
                "publish_plan_ref": publish_plan_ref,
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
        if action == "update_supplement" and scope_override is not None:
            return {
                "publish_plan_ref": None,
                "publish": {
                    "plan_hash": None,
                    "operation_refs": state.get("publish", {}).get("operation_refs", []),
                    "next_operation_index": 0,
                    "side_effect_status": "not_started",
                },
                "approval": {
                    "active_approval_ref": None,
                    "approval_type": None,
                    "approval_revision": int(approval["approval_revision"]),
                    "status": "superseded",
                    "approved_scope_hash": None,
                    "approved_plan_hash": None,
                    "challenge_id": None,
                    "requested_from": approval["requested_from"],
                },
                "approval_revision": int(approval["approval_revision"]),
                "scope_override": scope_override,
                "requested_action": APPROVAL_ACTION_MODIFY,
                "current_stage": "building_generation_scope",
                "current_node": "build_generation_scope",
                "resume_from": "wait_publish_confirmation",
                "control": {
                    "requested_action": APPROVAL_ACTION_MODIFY,
                    "resume_from": "wait_publish_confirmation",
                    "cancel_requested": False,
                    "scope_override": scope_override,
                },
                "cancel_requested": False,
                "report_regeneration_requested": False,
            }
        if outcome.current_node == "generate_structured_report":
            return {
                "publish_plan_ref": None,
                "publish": {
                    "plan_hash": None,
                    "operation_refs": [],
                    "next_operation_index": 0,
                    "side_effect_status": "not_started",
                },
                "approval": {
                    "active_approval_ref": None,
                    "approval_type": None,
                    "approval_revision": int(approval["approval_revision"]),
                    "status": "superseded",
                    "approved_scope_hash": None,
                    "approved_plan_hash": None,
                    "challenge_id": None,
                    "requested_from": approval["requested_from"],
                },
                "approval_revision": int(approval["approval_revision"]),
                "current_stage": outcome.current_stage,
                "current_node": outcome.current_node,
                "requested_action": action,
                "resume_from": "wait_publish_confirmation",
                "control": {
                    "requested_action": action,
                    "resume_from": "wait_publish_confirmation",
                    "cancel_requested": False,
                    "supplement": supplement,
                },
                "cancel_requested": False,
                "report_regeneration_requested": action
                in {"regenerate_report", "update_supplement"},
            }

        return {
            "publish_plan_ref": outcome.publish_plan_ref,
            "publish": {
                "plan_hash": outcome.plan_hash,
                "operation_refs": [],
                "next_operation_index": 0,
                "side_effect_status": "not_started",
            },
            "approval": {
                "active_approval_ref": outcome.approval_ref,
                "approval_type": "publish",
                "approval_revision": outcome.approval_revision,
                "status": "approved" if outcome.current_stage != "cancelled" else "cancelled",
                "approved_scope_hash": None,
                "approved_plan_hash": outcome.plan_hash
                if outcome.current_stage != "cancelled"
                else None,
                "challenge_id": outcome.challenge_id or challenge_id,
                "requested_from": approval["requested_from"],
            },
            "approval_revision": outcome.approval_revision,
            "current_stage": outcome.current_stage,
            "current_node": outcome.current_node,
            "requested_action": action,
            "resume_from": "wait_publish_confirmation",
            "control": {
                "requested_action": action,
                "resume_from": "wait_publish_confirmation",
                "cancel_requested": outcome.current_stage == "cancelled",
                "supplement": supplement,
            },
            "cancel_requested": outcome.current_stage == "cancelled",
            "report_regeneration_requested": action in {"regenerate_report", "update_supplement"}
            and scope_override is None,
        }

    return _node


def _create_feishu_document(publisher: PublishingService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        publish_plan_ref = state.get("publish_plan_ref")
        publish = state.get("publish")
        approved_plan_hash = _require_publish_plan_hash(publish)
        if not isinstance(publish_plan_ref, str) or not publish_plan_ref:
            return {
                "current_stage": "blocked",
                "current_node": "create_feishu_document",
                "error_code": "PUBLISH_PLAN_MISSING",
                "error_summary": "Publish plan missing from state",
            }
        outcome = publisher.create_feishu_document(
            run_id=state["run_id"],
            publish_plan_ref=publish_plan_ref,
            approved_plan_hash=approved_plan_hash,
        )
        if outcome.status == "blocked":
            return {
                "current_stage": outcome.current_stage or "blocked",
                "current_node": "create_feishu_document",
                "publish_plan_ref": publish_plan_ref,
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
        return {
            "publish": {
                "plan_hash": approved_plan_hash,
                "operation_refs": _append_unique(
                    publish.get("operation_refs"), outcome.operation_ref
                ),
                "next_operation_index": outcome.next_operation_index or 1,
                "side_effect_status": outcome.side_effect_status or "executing",
            },
            "current_stage": outcome.current_stage or "publishing",
            "current_node": outcome.current_node or "send_group_summary",
            "requested_action": None,
            "resume_from": "create_feishu_document",
            "control": {
                "requested_action": None,
                "resume_from": "create_feishu_document",
                "cancel_requested": False,
            },
            "cancel_requested": False,
        }

    return _node


def _send_group_summary(publisher: PublishingService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        publish_plan_ref = state.get("publish_plan_ref")
        publish = state.get("publish")
        approved_plan_hash = _require_publish_plan_hash(publish)
        if not isinstance(publish_plan_ref, str) or not publish_plan_ref:
            return {
                "current_stage": "blocked",
                "current_node": "send_group_summary",
                "error_code": "PUBLISH_PLAN_MISSING",
                "error_summary": "Publish plan missing from state",
            }
        outcome = publisher.send_group_summary(
            run_id=state["run_id"],
            publish_plan_ref=publish_plan_ref,
            approved_plan_hash=approved_plan_hash,
        )
        if outcome.status == "blocked":
            return {
                "current_stage": outcome.current_stage or "blocked",
                "current_node": "send_group_summary",
                "publish_plan_ref": publish_plan_ref,
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
        return {
            "publish": {
                "plan_hash": approved_plan_hash,
                "operation_refs": _append_unique(
                    publish.get("operation_refs"), outcome.operation_ref
                ),
                "next_operation_index": outcome.next_operation_index or 2,
                "side_effect_status": outcome.side_effect_status or "executing",
            },
            "current_stage": outcome.current_stage or "publishing",
            "current_node": outcome.current_node or "archive_report_record",
            "requested_action": None,
            "resume_from": "send_group_summary",
            "control": {
                "requested_action": None,
                "resume_from": "send_group_summary",
                "cancel_requested": False,
            },
            "cancel_requested": False,
        }

    return _node


def _archive_report_record(publisher: PublishingService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        publish_plan_ref = state.get("publish_plan_ref")
        publish = state.get("publish")
        approved_plan_hash = _require_publish_plan_hash(publish)
        if not isinstance(publish_plan_ref, str) or not publish_plan_ref:
            return {
                "current_stage": "blocked",
                "current_node": "archive_report_record",
                "error_code": "PUBLISH_PLAN_MISSING",
                "error_summary": "Publish plan missing from state",
            }
        outcome = publisher.archive_report_record(
            run_id=state["run_id"],
            publish_plan_ref=publish_plan_ref,
            approved_plan_hash=approved_plan_hash,
        )
        if outcome.status == "blocked":
            return {
                "current_stage": outcome.current_stage or "blocked",
                "current_node": "archive_report_record",
                "publish_plan_ref": publish_plan_ref,
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
        return {
            "publish": {
                "plan_hash": approved_plan_hash,
                "operation_refs": _append_unique(
                    publish.get("operation_refs"), outcome.operation_ref
                ),
                "next_operation_index": outcome.next_operation_index or 3,
                "side_effect_status": outcome.side_effect_status or "executing",
            },
            "current_stage": outcome.current_stage or "publishing",
            "current_node": outcome.current_node or "verify_side_effects",
            "requested_action": None,
            "resume_from": "archive_report_record",
            "control": {
                "requested_action": None,
                "resume_from": "archive_report_record",
                "cancel_requested": False,
            },
            "cancel_requested": False,
        }

    return _node


def _verify_side_effects(publisher: PublishingService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        publish_plan_ref = state.get("publish_plan_ref")
        publish = state.get("publish")
        approved_plan_hash = _require_publish_plan_hash(publish)
        if not isinstance(publish_plan_ref, str) or not publish_plan_ref:
            return {
                "current_stage": "blocked",
                "current_node": "verify_side_effects",
                "error_code": "PUBLISH_PLAN_MISSING",
                "error_summary": "Publish plan missing from state",
            }
        outcome = publisher.verify_side_effects(
            run_id=state["run_id"],
            publish_plan_ref=publish_plan_ref,
            approved_plan_hash=approved_plan_hash,
        )
        if outcome.status == "blocked":
            return {
                "current_stage": outcome.current_stage or "blocked",
                "current_node": outcome.current_node or "verify_side_effects",
                "publish_plan_ref": publish_plan_ref,
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
        return {
            "publish": {
                "plan_hash": approved_plan_hash,
                "operation_refs": publish.get("operation_refs", []),
                "next_operation_index": outcome.next_operation_index or 3,
                "side_effect_status": outcome.side_effect_status or "verified",
                "summary": outcome.error_summary or publish.get("summary"),
            },
            "current_stage": outcome.current_stage or "publishing",
            "current_node": outcome.current_node or "complete_run",
            "requested_action": None,
            "resume_from": "verify_side_effects",
            "control": {
                "requested_action": None,
                "resume_from": "verify_side_effects",
                "cancel_requested": False,
            },
            "cancel_requested": False,
        }

    return _node


def _compensate_partial_failure(publisher: PublishingService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        publish_plan_ref = state.get("publish_plan_ref")
        publish = state.get("publish")
        approved_plan_hash = _require_publish_plan_hash(publish)
        if not isinstance(publish_plan_ref, str) or not publish_plan_ref:
            return {
                "current_stage": "blocked",
                "current_node": "compensate_partial_failure",
                "error_code": "PUBLISH_PLAN_MISSING",
                "error_summary": "Publish plan missing from state",
            }
        outcome = publisher.compensate_partial_failure(
            run_id=state["run_id"],
            publish_plan_ref=publish_plan_ref,
            approved_plan_hash=approved_plan_hash,
        )
        if outcome.status == "blocked":
            return {
                "current_stage": outcome.current_stage or "blocked",
                "current_node": "compensate_partial_failure",
                "publish_plan_ref": publish_plan_ref,
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
        return {
            "publish": {
                "plan_hash": approved_plan_hash,
                "operation_refs": publish.get("operation_refs", []),
                "next_operation_index": outcome.next_operation_index or 3,
                "side_effect_status": outcome.side_effect_status or "partial_failed",
                "summary": outcome.error_summary or publish.get("summary"),
            },
            "current_stage": outcome.current_stage or "partial_failed",
            "current_node": outcome.current_node or "complete_run",
            "requested_action": None,
            "resume_from": "compensate_partial_failure",
            "control": {
                "requested_action": None,
                "resume_from": "compensate_partial_failure",
                "cancel_requested": False,
            },
            "cancel_requested": False,
        }

    return _node


def _complete_run(state: WorkflowState) -> dict[str, object]:
    ensure_state_is_safe(state)
    publish = state.get("publish")
    plan_hash = None
    side_effect_status = None
    operation_refs: list[object] = []
    next_operation_index = 0
    if isinstance(publish, Mapping):
        plan_hash = publish.get("plan_hash") if isinstance(publish.get("plan_hash"), str) else None
        side_effect_status = (
            publish.get("side_effect_status")
            if isinstance(publish.get("side_effect_status"), str)
            else None
        )
        existing_refs = publish.get("operation_refs")
        if isinstance(existing_refs, list):
            operation_refs = [item for item in existing_refs if isinstance(item, str)]
        next_value = publish.get("next_operation_index")
        if isinstance(next_value, int):
            next_operation_index = next_value
    return {
        "publish": {
            "plan_hash": plan_hash,
            "operation_refs": operation_refs,
            "next_operation_index": next_operation_index,
            "side_effect_status": side_effect_status or "verified",
        },
        "current_stage": "succeeded",
        "current_node": "complete_run",
        "requested_action": None,
        "resume_from": "complete_run",
        "control": {
            "requested_action": None,
            "resume_from": "complete_run",
            "cancel_requested": False,
        },
        "cancel_requested": False,
    }


def _cancel_run(state: WorkflowState) -> dict[str, object]:
    ensure_state_is_safe(state)
    publish = state.get("publish")
    plan_hash = None
    side_effect_status = None
    operation_refs: list[object] = []
    next_operation_index = 0
    if isinstance(publish, Mapping):
        plan_hash = publish.get("plan_hash") if isinstance(publish.get("plan_hash"), str) else None
        side_effect_status = (
            publish.get("side_effect_status")
            if isinstance(publish.get("side_effect_status"), str)
            else None
        )
        existing_refs = publish.get("operation_refs")
        if isinstance(existing_refs, list):
            operation_refs = [item for item in existing_refs if isinstance(item, str)]
        next_value = publish.get("next_operation_index")
        if isinstance(next_value, int):
            next_operation_index = next_value
    return {
        "publish": {
            "plan_hash": plan_hash,
            "operation_refs": operation_refs,
            "next_operation_index": next_operation_index,
            "side_effect_status": side_effect_status or "cancelled",
        },
        "current_stage": "cancelled",
        "current_node": "complete_run",
        "requested_action": None,
        "resume_from": "cancel_run",
        "control": {
            "requested_action": None,
            "resume_from": "cancel_run",
            "cancel_requested": False,
        },
        "cancel_requested": False,
    }


def _stage_for_node(node_name: str) -> str:
    mapping = {
        "load_project_config": "config_loaded",
        "build_generation_scope": "building_generation_scope",
        "request_generation_confirmation": "requesting_confirmation",
        "wait_generation_confirmation": "waiting_confirmation",
        "collect_feishu_data": "collecting_feishu_data",
        "collect_github_data": "collecting_github_data",
        "normalize_data": "normalizing_data",
        "validate_data": "validating_data",
        "calculate_metrics": "calculating_metrics",
        "build_evidence": "building_evidence",
        "generate_structured_report": "generating_structured_report",
        "verify_grounding": "verifying_grounding",
        "render_report": "rendering_report",
        "build_publish_plan": "building_publish_plan",
        "request_publish_confirmation": "requesting_publish_confirmation",
        "wait_publish_confirmation": "waiting_publish_approval",
        "request_human_input": "requesting_human_input",
        "wait_human_input": "waiting_human_input",
        "create_feishu_document": "publishing",
        "send_group_summary": "publishing",
        "archive_report_record": "publishing",
        "verify_side_effects": "publishing",
        "compensate_partial_failure": "compensating",
        "diagnose_problem": "diagnosing_problem",
        "complete_run": "succeeded",
        "cancel_run": "cancelled",
    }
    return mapping.get(node_name, "blocked")


def _diagnosis_block(
    state: WorkflowState,
    *,
    source_node: str,
    error_code: str | None,
    error_summary: str | None,
    **extra: object,
) -> dict[str, object]:
    diagnosis = state.get("diagnosis")
    diagnosis_patch: dict[str, object] = {}
    if isinstance(diagnosis, Mapping):
        diagnosis_patch.update(diagnosis)
    diagnosis_patch.update(
        {
            "source_node": source_node,
            "next_repair_action": diagnosis_patch.get("next_repair_action"),
            "planned_node": diagnosis_patch.get("planned_node"),
        }
    )
    return {
        **extra,
        "diagnosis": diagnosis_patch,
        "current_stage": "diagnosing_problem",
        "current_node": "diagnose_problem",
        "error_code": error_code,
        "error_summary": error_summary,
    }


def _generation_approval_route(state: WorkflowState) -> str:
    if state.get("cancel_requested"):
        return "cancel_run"
    requested_action = _normalize_action_if_present(state.get("requested_action"))
    if requested_action is None:
        return END
    if requested_action == APPROVAL_ACTION_MODIFY:
        return "build_generation_scope"
    if requested_action in {
        APPROVAL_ACTION_CANCEL,
        APPROVAL_ACTION_LEGACY_CANCEL,
        APPROVAL_ACTION_REJECT,
    }:
        return END
    return "collect_feishu_data"


def _collection_route(state: WorkflowState) -> str:
    if state.get("cancel_requested"):
        return "cancel_run"
    if state.get("current_stage") == "blocked":
        return END
    current_node = state.get("current_node")
    if current_node in {
        "collect_github_data",
        "normalize_data",
        "validate_data",
        "calculate_metrics",
        "build_evidence",
        "generate_structured_report",
        "verify_grounding",
        "render_report",
        "build_publish_plan",
        "request_publish_confirmation",
        "wait_publish_confirmation",
        "diagnose_problem",
        "request_human_input",
        "wait_human_input",
    }:
        return str(current_node)
    return END


def _diagnosis_route(state: WorkflowState) -> str:
    if state.get("cancel_requested"):
        return "cancel_run"
    if state.get("current_stage") == "blocked":
        return END
    current_node = state.get("current_node")
    if current_node in {
        "collect_feishu_data",
        "collect_github_data",
        "normalize_data",
        "validate_data",
        "calculate_metrics",
        "build_evidence",
        "generate_structured_report",
        "verify_grounding",
        "render_report",
        "build_publish_plan",
        "request_publish_confirmation",
        "wait_publish_confirmation",
        "request_human_input",
        "wait_human_input",
        "complete_run",
        "cancel_run",
    }:
        return str(current_node)
    return END


def _human_input_route(state: WorkflowState) -> str:
    if state.get("cancel_requested"):
        return "cancel_run"
    current_node = state.get("current_node")
    if current_node in {
        "validate_data",
        "collect_feishu_data",
        "collect_github_data",
        "normalize_data",
        "calculate_metrics",
        "build_evidence",
        "generate_structured_report",
        "verify_grounding",
        "render_report",
        "build_publish_plan",
        "request_human_input",
        "wait_human_input",
        "complete_run",
        "cancel_run",
    }:
        return str(current_node)
    return END


def _publish_approval_route(state: WorkflowState) -> str:
    if state.get("cancel_requested"):
        return "cancel_run"
    if state.get("current_stage") == "blocked":
        return END
    current_node = state.get("current_node")
    if current_node in {
        "wait_publish_confirmation",
        "build_generation_scope",
        "generate_structured_report",
        "create_feishu_document",
    }:
        return str(current_node)
    return END


def _publish_side_effect_route(state: WorkflowState) -> str:
    if state.get("cancel_requested"):
        return "cancel_run"
    if state.get("current_stage") in {"blocked", "succeeded", "partial_failed"}:
        return END
    current_node = state.get("current_node")
    if current_node in {
        "send_group_summary",
        "archive_report_record",
        "verify_side_effects",
        "compensate_partial_failure",
        "complete_run",
    }:
        return str(current_node)
    return END


def _ensure_report_period(state: Mapping[str, object]) -> dict[str, object]:
    report_period = state.get("report_period")
    if isinstance(report_period, Mapping):
        return {
            "start_at": _as_string(report_period.get("start_at"), "start_at"),
            "end_at": _as_string(report_period.get("end_at"), "end_at"),
            "timezone": _as_string(report_period.get("timezone"), "timezone"),
        }

    return {
        "start_at": _as_string(state.get("period_start"), "period_start"),
        "end_at": _as_string(state.get("period_end"), "period_end"),
        "timezone": _as_string(state.get("project_timezone"), "project_timezone"),
    }


def _require_scope(state: Mapping[str, object]) -> dict[str, object]:
    scope = state.get("scope")
    if not isinstance(scope, Mapping):
        raise ValueError("scope is required")
    scope_dict = dict(scope)
    if "scope_hash" not in scope_dict:
        raise ValueError("scope hash is required")
    return scope_dict


def _require_scope_hash(scope: Mapping[str, object]) -> str:
    value = scope.get("scope_hash")
    if not isinstance(value, str) or not value:
        raise ValueError("scope hash is required")
    return value


def _require_approval(state: Mapping[str, object]) -> dict[str, object]:
    approval = state.get("approval")
    if not isinstance(approval, Mapping):
        raise ValueError("approval is required")
    approval_dict = dict(approval)
    required_keys = ("active_approval_ref", "challenge_id", "approval_revision", "requested_from")
    for key in required_keys:
        if key not in approval_dict:
            raise ValueError(f"approval.{key} is required")
    return approval_dict


def _require_diagnosis(state: Mapping[str, object]) -> dict[str, object]:
    diagnosis = state.get("diagnosis")
    if not isinstance(diagnosis, Mapping):
        raise ValueError("diagnosis is required")
    diagnosis_dict = dict(diagnosis)
    required_keys = ("active_problem_key", "required_fields", "resume_from", "checkpoint_id")
    for key in required_keys:
        if key not in diagnosis_dict:
            raise ValueError(f"diagnosis.{key} is required")
    return diagnosis_dict


def _require_request_payload_hash(approval: Mapping[str, object]) -> str:
    value = approval.get("request_payload_hash")
    if not isinstance(value, str) or not value:
        raise ValueError("request_payload_hash is required")
    return value


def _resume_challenge_id(payload: Mapping[str, object]) -> str:
    value = payload.get("challenge_id") or payload.get("approval_ref")
    if not isinstance(value, str) or not value:
        raise ValueError("challenge_id is required")
    return value


def _resume_revision(payload: Mapping[str, object]) -> int:
    value = payload.get("approval_revision")
    if not isinstance(value, int):
        raise ValueError("approval_revision is required")
    return value


def _resume_presented_hash(payload: Mapping[str, object]) -> str:
    value = payload.get("presented_hash")
    if not isinstance(value, str) or not value:
        raise ValueError("presented_hash is required")
    return value


def _resume_actor_id(payload: Mapping[str, object], state: Mapping[str, object]) -> str:
    value = payload.get("actor_id") or state.get("requester_id") or "local-demo"
    if not isinstance(value, str) or not value:
        return "local-demo"
    return value


def _resume_scope_override(payload: Mapping[str, object]) -> dict[str, object]:
    override = payload.get("scope_override") or payload.get("payload")
    if not isinstance(override, Mapping):
        raise ValueError("scope_override is required for modify_generation_scope")
    return dict(override)


def _resume_supplement(payload: Mapping[str, object], action: str) -> dict[str, object] | None:
    if action not in {"update_supplement", APPROVAL_ACTION_SUBMIT_HUMAN_INPUT}:
        return None
    supplement = payload.get("supplement") or payload.get("payload")
    if not isinstance(supplement, Mapping):
        raise ValueError("supplement is required")
    return dict(supplement)


def _scope_override_from_supplement(
    supplement: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if supplement is None:
        return None
    override = supplement.get("scope_override")
    if not isinstance(override, Mapping):
        return None
    return dict(override)


def _human_input_requested_fields(diagnosis: Mapping[str, object]) -> list[dict[str, object]]:
    requested_fields = diagnosis.get("required_fields")
    if not isinstance(requested_fields, Sequence) or isinstance(
        requested_fields, str | bytes | bytearray
    ):
        raise ValueError("diagnosis.required_fields is required")
    fields: list[dict[str, object]] = []
    for item in requested_fields:
        if not isinstance(item, Mapping):
            raise ValueError("diagnosis.required_fields must be a list of mappings")
        field_name = item.get("name")
        field_type = item.get("type")
        required = item.get("required", True)
        if not isinstance(field_name, str) or not field_name:
            raise ValueError("diagnosis.required_fields entries require a name")
        if field_type not in {"string", "number", "boolean", "object", "array"}:
            raise ValueError("diagnosis.required_fields entries require a supported type")
        if not isinstance(required, bool):
            raise ValueError("diagnosis.required_fields entries require a boolean required flag")
        fields.append({"name": field_name, "type": field_type, "required": required})
    return fields


def _human_input_resume_from(diagnosis: Mapping[str, object]) -> str:
    value = diagnosis.get("resume_from")
    if not isinstance(value, str) or not value:
        raise ValueError("diagnosis.resume_from is required")
    return value


def _normalize_human_input_action(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("action is required")
    normalized = value.strip().casefold()
    aliases = {
        APPROVAL_ACTION_SUBMIT_HUMAN_INPUT: APPROVAL_ACTION_SUBMIT_HUMAN_INPUT,
        APPROVAL_ACTION_CANCEL: APPROVAL_ACTION_CANCEL,
        APPROVAL_ACTION_LEGACY_CANCEL: APPROVAL_ACTION_CANCEL,
    }
    if normalized not in HUMAN_INPUT_APPROVAL_ACTIONS:
        raise ValueError(f"unsupported human input approval action: {value}")
    return aliases[normalized]


def _validate_human_input_supplement(
    supplement: Mapping[str, object] | None,
    requested_fields: Sequence[Mapping[str, object]],
) -> None:
    if supplement is None:
        raise ValueError("supplement is required")
    if not isinstance(supplement, Mapping):
        raise ValueError("supplement must be a mapping")
    allowed_names = {
        str(field.get("name"))
        for field in requested_fields
        if isinstance(field.get("name"), str) and field.get("name")
    }
    unknown_keys = set(supplement) - allowed_names
    if unknown_keys:
        raise ValueError(
            f"unsupported supplement fields: {sorted(str(key) for key in unknown_keys)}"
        )
    for field in requested_fields:
        name = field.get("name")
        field_type = field.get("type")
        required = field.get("required", True)
        if not isinstance(name, str) or not name:
            raise ValueError("diagnosis.required_fields entries require a name")
        if not isinstance(required, bool):
            raise ValueError("diagnosis.required_fields entries require a boolean required flag")
        if required and name not in supplement:
            raise ValueError(f"supplement.{name} is required")
        if name not in supplement:
            continue
        value = supplement.get(name)
        if field_type == "string":
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"supplement.{name} must be a non-empty string")
        elif field_type == "number":
            if not isinstance(value, int | float) or isinstance(value, bool):
                raise ValueError(f"supplement.{name} must be a number")
        elif field_type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"supplement.{name} must be a boolean")
        elif field_type == "object":
            if not isinstance(value, Mapping):
                raise ValueError(f"supplement.{name} must be a mapping")
        elif field_type == "array":
            if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
                raise ValueError(f"supplement.{name} must be a list")
        else:
            raise ValueError("unsupported supplement field type")


def _requested_from(state: Mapping[str, object]) -> list[str]:
    requester_id = state.get("requester_id")
    if isinstance(requester_id, str) and requester_id:
        return [requester_id]
    return ["local-demo"]


def _normalize_action(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("action is required")
    normalized = value.strip().casefold()
    action_aliases = {
        APPROVAL_ACTION_APPROVE: APPROVAL_ACTION_APPROVE,
        APPROVAL_ACTION_CONTINUE: APPROVAL_ACTION_APPROVE,
        APPROVAL_ACTION_MODIFY: APPROVAL_ACTION_MODIFY,
        APPROVAL_ACTION_CANCEL: APPROVAL_ACTION_CANCEL,
        APPROVAL_ACTION_LEGACY_CANCEL: APPROVAL_ACTION_CANCEL,
        APPROVAL_ACTION_REJECT: APPROVAL_ACTION_REJECT,
    }
    if normalized not in action_aliases:
        raise ValueError(f"unsupported generation approval action: {value}")
    return action_aliases[normalized]


def _normalize_action_if_present(value: object) -> str | None:
    if value is None:
        return None
    return _normalize_action(value)


def _normalize_publish_action(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("action is required")
    normalized = value.strip().casefold()
    allowed_actions = {
        "approve_publish",
        "regenerate_report",
        "update_supplement",
        "cancel_publish",
    }
    if normalized not in allowed_actions:
        raise ValueError(f"unsupported publish approval action: {value}")
    return normalized


def _as_string(value: object, field_name: str) -> str:
    if isinstance(value, str):
        return value
    raise ValueError(f"{field_name} must be a string")


def _append_unique(existing: object, new_value: str | None) -> list[str]:
    items: list[str] = []
    if isinstance(existing, list):
        items.extend(item for item in existing if isinstance(item, str))
    if isinstance(new_value, str) and new_value:
        items.append(new_value)
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _extend_unique(existing: object, new_values: Sequence[str | None]) -> list[str]:
    items: list[str] = []
    if isinstance(existing, list):
        items.extend(item for item in existing if isinstance(item, str))
    for value in new_values:
        if isinstance(value, str) and value:
            items.append(value)
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _require_publish_plan_hash(publish: object) -> str:
    if not isinstance(publish, Mapping):
        raise ValueError("publish is required")
    value = publish.get("plan_hash")
    if not isinstance(value, str) or not value:
        raise ValueError("publish.plan_hash is required")
    return value


class _MissingGenerationApprovalStore:
    def ensure_pending_generation_approval(self, **_: object) -> Any:
        raise RuntimeError("approval_store is required")

    def mark_generation_approval_decision(self, **_: object) -> Any:
        raise RuntimeError("approval_store is required")


class _MissingHumanInputApprovalStore:
    def ensure_pending_human_input_approval(self, **_: object) -> Any:
        raise RuntimeError("human_input_store is required")

    def mark_human_input_decision(self, **_: object) -> Any:
        raise RuntimeError("human_input_store is required")


class _MissingDiagnosisService:
    def diagnose_problem(self, *_: object, **__: object) -> DiagnosisOutcome:
        raise RuntimeError("diagnosis_service is required")


class _MissingPublishingService:
    def build_publish_plan(self, *_: object, **__: object) -> PublishPlanOutcome:
        raise RuntimeError("publishing_service is required")

    def request_publish_confirmation(self, *_: object, **__: object) -> PublishPlanOutcome:
        raise RuntimeError("publishing_service is required")

    def resume_publish_confirmation(self, *_: object, **__: object) -> PublishResumeOutcome:
        raise RuntimeError("publishing_service is required")

    def create_feishu_document(self, *_: object, **__: object) -> Any:
        raise RuntimeError("publishing_service is required")

    def send_group_summary(self, *_: object, **__: object) -> Any:
        raise RuntimeError("publishing_service is required")

    def archive_report_record(self, *_: object, **__: object) -> Any:
        raise RuntimeError("publishing_service is required")

    def verify_side_effects(self, *_: object, **__: object) -> Any:
        raise RuntimeError("publishing_service is required")


class _MissingCollectionService:
    def collect_feishu_data(self, *_: object, **__: object) -> CollectionStageOutcome:
        raise RuntimeError("collection_service is required")

    def collect_github_data(self, *_: object, **__: object) -> CollectionStageOutcome:
        raise RuntimeError("collection_service is required")

    def normalize_data(self, *_: object, **__: object) -> CollectionStageOutcome:
        raise RuntimeError("collection_service is required")

    def validate_data(self, *_: object, **__: object) -> CollectionStageOutcome:
        raise RuntimeError("collection_service is required")


class _MissingMetricsService:
    def calculate_metrics(self, *_: object, **__: object) -> MetricStageOutcome:
        raise RuntimeError("metrics_service is required")


class _MissingReportingService:
    def build_evidence(self, *_: object, **__: object) -> ReportStageOutcome:
        raise RuntimeError("reporting_service is required")

    def generate_structured_report(self, *_: object, **__: object) -> ReportStageOutcome:
        raise RuntimeError("reporting_service is required")

    def verify_grounding(self, *_: object, **__: object) -> ReportStageOutcome:
        raise RuntimeError("reporting_service is required")

    def render_report(self, *_: object, **__: object) -> ReportStageOutcome:
        raise RuntimeError("reporting_service is required")
