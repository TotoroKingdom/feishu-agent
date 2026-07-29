from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agent.state import WorkflowState, ensure_state_is_safe
from app.approvals import (
    APPROVAL_ACTION_APPROVE,
    APPROVAL_ACTION_CANCEL,
    APPROVAL_ACTION_CONTINUE,
    APPROVAL_ACTION_LEGACY_CANCEL,
    APPROVAL_ACTION_MODIFY,
    APPROVAL_ACTION_REJECT,
    GenerationApprovalStore,
    build_generation_scope,
)
from app.collection.service import CollectionService, CollectionStageOutcome
from app.metrics.service import MetricStageOutcome, MetricsService
from app.publishing.service import PublishPlanOutcome, PublishResumeOutcome, PublishingService
from app.reporting.service import ReportStageOutcome, ReportingService


def build_workflow_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    approval_store: GenerationApprovalStore | None = None,
    collection_service: CollectionService | None = None,
    metrics_service: MetricsService | None = None,
    reporting_service: ReportingService | None = None,
    publishing_service: PublishingService | None = None,
) -> Any:
    store = approval_store or _MissingGenerationApprovalStore()
    collector = collection_service or _MissingCollectionService()
    metrics = metrics_service or _MissingMetricsService()
    reporter = reporting_service or _MissingReportingService()
    publisher = publishing_service or _MissingPublishingService()
    builder = StateGraph(WorkflowState)
    builder.add_node("load_project_config", _load_project_config)
    builder.add_node("build_generation_scope", _build_generation_scope)
    builder.add_node("request_generation_confirmation", _request_generation_confirmation(store))
    builder.add_node("wait_generation_confirmation", _wait_generation_confirmation(store))
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
    builder.add_edge(START, "load_project_config")
    builder.add_edge("load_project_config", "build_generation_scope")
    builder.add_edge("build_generation_scope", "request_generation_confirmation")
    builder.add_edge("request_generation_confirmation", "wait_generation_confirmation")
    builder.add_conditional_edges(
        "wait_generation_confirmation",
        _generation_approval_route,
        {
            "build_generation_scope": "build_generation_scope",
            "collect_feishu_data": "collect_feishu_data",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "collect_feishu_data",
        _collection_route,
        {
            "collect_github_data": "collect_github_data",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "collect_github_data",
        _collection_route,
        {
            "normalize_data": "normalize_data",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "normalize_data",
        _collection_route,
        {
            "validate_data": "validate_data",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "validate_data",
        _collection_route,
        {
            "calculate_metrics": "calculate_metrics",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "calculate_metrics",
        _collection_route,
        {
            "build_evidence": "build_evidence",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "build_evidence",
        _collection_route,
        {
            "generate_structured_report": "generate_structured_report",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "generate_structured_report",
        _collection_route,
        {
            "verify_grounding": "verify_grounding",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "verify_grounding",
        _collection_route,
        {
            "render_report": "render_report",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "render_report",
        _collection_route,
        {
            "build_publish_plan": "build_publish_plan",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "build_publish_plan",
        _collection_route,
        {
            "request_publish_confirmation": "request_publish_confirmation",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "request_publish_confirmation",
        _collection_route,
        {
            "wait_publish_confirmation": "wait_publish_confirmation",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "wait_publish_confirmation",
        _publish_approval_route,
        {
            "wait_publish_confirmation": "wait_publish_confirmation",
            "generate_structured_report": "generate_structured_report",
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


def _collect_feishu_data(collector: CollectionService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        outcome = collector.collect_feishu_data(state["run_id"], _require_scope(state))
        if outcome.status == "blocked":
            return {
                "current_stage": "blocked",
                "current_node": "collect_feishu_data",
                "source_batch_refs": _append_unique(state.get("source_batch_refs", []), outcome.source_batch_ref),
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
        return {
            "current_stage": "collecting_github_data",
            "current_node": "collect_github_data",
            "source_batch_refs": _append_unique(state.get("source_batch_refs", []), outcome.source_batch_ref),
            "error_code": None,
            "error_summary": None,
        }

    return _node


def _collect_github_data(collector: CollectionService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        outcome = collector.collect_github_data(state["run_id"], _require_scope(state))
        if outcome.status == "blocked":
            return {
                "current_stage": "blocked",
                "current_node": "collect_github_data",
                "source_batch_refs": _append_unique(state.get("source_batch_refs", []), outcome.source_batch_ref),
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
        return {
            "current_stage": "normalizing_data",
            "current_node": "normalize_data",
            "source_batch_refs": _append_unique(state.get("source_batch_refs", []), outcome.source_batch_ref),
            "error_code": None,
            "error_summary": None,
        }

    return _node


def _normalize_data(collector: CollectionService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        outcome = collector.normalize_data(state["run_id"], _require_scope(state))
        if outcome.status == "blocked":
            return {
                "current_stage": "blocked",
                "current_node": "normalize_data",
                "normalized_snapshot_ref": state.get("normalized_snapshot_ref"),
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
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
            return {
                "current_stage": "blocked",
                "current_node": "validate_data",
                "error_code": "NORMALIZED_SNAPSHOT_MISSING",
                "error_summary": "Normalized snapshot missing from state",
            }
        outcome = collector.validate_data(state["run_id"], normalized_snapshot_ref)
        if outcome.status == "blocked":
            return {
                "current_stage": "blocked",
                "current_node": "validate_data",
                "validation_result_ref": outcome.validation_result_ref,
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
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
            return {
                "current_stage": "blocked",
                "current_node": "calculate_metrics",
                "error_code": "NORMALIZED_SNAPSHOT_MISSING",
                "error_summary": "Normalized snapshot missing from state",
            }
        outcome = metrics_service.calculate_metrics(state["run_id"], normalized_snapshot_ref)
        if outcome.status == "blocked":
            return {
                "current_stage": "blocked",
                "current_node": "calculate_metrics",
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
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
            return {
                "current_stage": "blocked",
                "current_node": "build_evidence",
                "error_code": "METRICS_SNAPSHOT_MISSING",
                "error_summary": "Metric snapshot missing from state",
            }
        outcome = reporter.build_evidence(state["run_id"], metrics_ref)
        if outcome.status == "blocked":
            return {
                "current_stage": "blocked",
                "current_node": "build_evidence",
                "evidence_set_ref": outcome.evidence_set_ref,
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
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
            return {
                "current_stage": "blocked",
                "current_node": "generate_structured_report",
                "error_code": "EVIDENCE_SET_MISSING",
                "error_summary": "Evidence set missing from state",
            }
        outcome = reporter.generate_structured_report(state["run_id"], evidence_set_ref)
        if outcome.status == "blocked":
            return {
                "current_stage": "blocked",
                "current_node": "generate_structured_report",
                "report_version_ref": outcome.report_version_ref,
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
        return {
            "current_stage": "verifying_grounding",
            "current_node": "verify_grounding",
            "report_version_ref": outcome.report_version_ref,
            "error_code": None,
            "error_summary": None,
        }

    return _node


def _verify_grounding(reporter: ReportingService):
    def _node(state: WorkflowState) -> dict[str, object]:
        ensure_state_is_safe(state)
        report_version_ref = state.get("report_version_ref")
        if not isinstance(report_version_ref, str) or not report_version_ref:
            return {
                "current_stage": "blocked",
                "current_node": "verify_grounding",
                "error_code": "REPORT_VERSION_MISSING",
                "error_summary": "Report version missing from state",
            }
        outcome = reporter.verify_grounding(state["run_id"], report_version_ref)
        if outcome.status == "blocked":
            return {
                "current_stage": "blocked",
                "current_node": "verify_grounding",
                "report_version_ref": outcome.report_version_ref,
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
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
            return {
                "current_stage": "blocked",
                "current_node": "render_report",
                "error_code": "REPORT_VERSION_MISSING",
                "error_summary": "Report version missing from state",
            }
        outcome = reporter.render_report(state["run_id"], report_version_ref)
        if outcome.status == "blocked":
            return {
                "current_stage": "blocked",
                "current_node": "render_report",
                "report_version_ref": outcome.report_version_ref,
                "error_code": outcome.error_code,
                "error_summary": outcome.error_summary,
            }
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
                    "supplement": _resume_supplement(resume_payload, action),
                },
                "cancel_requested": False,
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
                    "supplement": _resume_supplement(resume_payload, action),
                },
                "cancel_requested": False,
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
                "status": "approved" if outcome.current_stage == "publish_approved" else "cancelled",
                "approved_scope_hash": None,
                "approved_plan_hash": outcome.plan_hash if outcome.current_stage == "publish_approved" else None,
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
                "supplement": _resume_supplement(resume_payload, action),
            },
            "cancel_requested": outcome.current_stage == "cancelled",
        }

    return _node


def _generation_approval_route(state: WorkflowState) -> str:
    requested_action = _normalize_action_if_present(state.get("requested_action"))
    if requested_action is None:
        return END
    if requested_action == APPROVAL_ACTION_MODIFY:
        return "build_generation_scope"
    if requested_action in {APPROVAL_ACTION_CANCEL, APPROVAL_ACTION_LEGACY_CANCEL, APPROVAL_ACTION_REJECT}:
        return END
    return "collect_feishu_data"


def _collection_route(state: WorkflowState) -> str:
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
    }:
        return str(current_node)
    return END


def _publish_approval_route(state: WorkflowState) -> str:
    if state.get("current_stage") == "blocked":
        return END
    current_node = state.get("current_node")
    if current_node in {"wait_publish_confirmation", "generate_structured_report"}:
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
    if action != "update_supplement":
        return None
    supplement = payload.get("supplement") or payload.get("payload")
    if not isinstance(supplement, Mapping):
        raise ValueError("supplement is required for update_supplement")
    return dict(supplement)


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


class _MissingPublishingService:
    def build_publish_plan(self, *_: object, **__: object) -> PublishPlanOutcome:
        raise RuntimeError("publishing_service is required")

    def request_publish_confirmation(self, *_: object, **__: object) -> PublishPlanOutcome:
        raise RuntimeError("publishing_service is required")

    def resume_publish_confirmation(self, *_: object, **__: object) -> PublishResumeOutcome:
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
