from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from langgraph.checkpoint.base import CheckpointTuple
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, StateSnapshot
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.graph import build_workflow_graph
from app.agent.diagnosis import DiagnosisService
from app.agent.state import build_initial_state, thread_id_for_run
from app.approvals import GenerationApprovalStore, HumanInputApprovalStore
from app.collection.service import CollectionService
from app.db.models import (
    HumanApproval,
    Project,
    PublishPlan,
    ReportRun,
    RunStatusHistory,
    SideEffectOperation,
    new_id,
)
from app.metrics.service import MetricsService
from app.publishing.generation import build_publish_plan_hash
from app.publishing.service import PublishingService
from app.reporting.service import ReportingService
from app.runtime.leases import DEFAULT_RUN_LEASE_SECONDS, RunLeaseConflictError, RunLeaseService

RETRYABLE_ERROR_CLASSES = {"timeout", "rate_limited", "transient_timeout"}

SessionFactory = Callable[[], Session]


@dataclass(slots=True)
class WorkflowExecutionResult:
    run_id: str
    thread_id: str
    status: str
    checkpoint_id: str | None
    snapshot: StateSnapshot


class WorkflowRuntime:
    def __init__(
        self,
        session_factory: SessionFactory,
        checkpointer: Any | None = None,
        diagnosis_service: DiagnosisService | None = None,
        collection_service: CollectionService | None = None,
        metrics_service: MetricsService | None = None,
        reporting_service: ReportingService | None = None,
        publishing_service: PublishingService | None = None,
        human_input_store: HumanInputApprovalStore | None = None,
        worker_id: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._worker_id = worker_id or new_id()
        self._run_lease_seconds = DEFAULT_RUN_LEASE_SECONDS
        self._lease_service = RunLeaseService(session_factory)
        self._approval_store = GenerationApprovalStore(session_factory)
        self._human_input_store = human_input_store or HumanInputApprovalStore(session_factory)
        self._diagnosis_service = diagnosis_service or DiagnosisService(session_factory)
        self._collection_service = collection_service or CollectionService(session_factory)
        self._metrics_service = metrics_service or MetricsService(session_factory)
        self._reporting_service = reporting_service or ReportingService(session_factory)
        self._publishing_service = publishing_service or PublishingService(session_factory)
        self._checkpointer: Any = checkpointer or MemorySaver()
        self._graph = build_workflow_graph(
            self._checkpointer,
            self._approval_store,
            self._diagnosis_service,
            self._collection_service,
            self._metrics_service,
            self._reporting_service,
            self._publishing_service,
            self._human_input_store,
        )

    def start(self, run_id: str) -> WorkflowExecutionResult:
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            project = self._load_project(session, run.project_id)
            thread_id = self._ensure_run_identity(run)
            config = self._config(thread_id)
            existing = self._existing_checkpoint(config)
            if existing is not None:
                snapshot = cast(StateSnapshot, self._graph.get_state(config))
                return self._result_from_snapshot(run_id, thread_id, snapshot)
            lease_now = datetime.now(UTC)
            self._claim_run_lease(run, now=lease_now)
            initial_state = self._initial_state(run, project)
            session.flush()
            self._graph.invoke(initial_state, config=config)
            snapshot = cast(StateSnapshot, self._graph.get_state(config))
            self._record_transition(
                session,
                run,
                from_status=run.status,
                to_status=self._status_from_snapshot(snapshot),
                reason_code=self._reason_code_from_snapshot(snapshot, started=True),
                node_name=self._current_node_from_snapshot(snapshot),
                checkpoint_ref=self._checkpoint_id(snapshot),
            )
            run.status = self._status_from_snapshot(snapshot)
            run.current_stage = self._current_stage_from_snapshot(snapshot) or run.current_stage
            run.current_node = self._current_node_from_snapshot(snapshot)
            run.scope_revision = self._scope_revision_from_snapshot(snapshot) or run.scope_revision
            self._release_run_lease(run, now=datetime.now(UTC))
            session.commit()
            return self._result_from_snapshot(run_id, thread_id, snapshot)

    def resume(self, run_id: str, resume_payload: Mapping[str, object]) -> WorkflowExecutionResult:
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            thread_id = self._ensure_run_identity(run)
            config = self._config(thread_id)
            if self._existing_checkpoint(config) is None:
                raise ValueError("run has no checkpoint to resume")
            snapshot = cast(StateSnapshot, self._graph.get_state(config))
            if run.status != "waiting":
                return self._result_from_snapshot(run_id, thread_id, snapshot)
            pending = self._load_pending_approval(session, run_id)
            normalized_resume_payload = dict(resume_payload)
            if pending is not None:
                if (
                    "challenge_id" not in normalized_resume_payload
                    and "approval_ref" not in normalized_resume_payload
                ):
                    normalized_resume_payload["challenge_id"] = pending.challenge_id
                    normalized_resume_payload["approval_ref"] = pending.challenge_id
                if "approval_revision" not in normalized_resume_payload:
                    normalized_resume_payload["approval_revision"] = pending.revision
                if "presented_hash" not in normalized_resume_payload:
                    if pending.approval_type == "generation":
                        scope_hash = (
                            snapshot.values.get("scope", {}).get("scope_hash")
                            if isinstance(snapshot.values.get("scope"), Mapping)
                            else None
                        )
                        if isinstance(scope_hash, str):
                            normalized_resume_payload["presented_hash"] = scope_hash
                    elif pending.approval_type == "publish":
                        publish_hash = (
                            snapshot.values.get("publish", {}).get("plan_hash")
                            if isinstance(snapshot.values.get("publish"), Mapping)
                            else None
                        )
                        if isinstance(publish_hash, str):
                            normalized_resume_payload["presented_hash"] = publish_hash
                    elif pending.approval_type == "human_input":
                        if isinstance(pending.request_payload_hash, str):
                            normalized_resume_payload["presented_hash"] = (
                                pending.request_payload_hash
                            )
                if self._resume_challenge_id(normalized_resume_payload) != pending.challenge_id:
                    return self._result_from_snapshot(run_id, thread_id, snapshot)
            lease_now = datetime.now(UTC)
            self._claim_run_lease(run, now=lease_now)
            self._graph.invoke(Command(resume=normalized_resume_payload), config=config)
            snapshot = cast(StateSnapshot, self._graph.get_state(config))
            previous_status = run.status
            run.status = self._status_from_snapshot(snapshot)
            run.current_stage = self._current_stage_from_snapshot(snapshot) or run.current_stage
            run.current_node = self._current_node_from_snapshot(snapshot)
            run.scope_revision = self._scope_revision_from_snapshot(snapshot) or run.scope_revision
            self._record_transition(
                session,
                run,
                from_status=previous_status,
                to_status=run.status,
                reason_code=self._reason_code_from_snapshot(snapshot),
                node_name=run.current_node,
                checkpoint_ref=self._checkpoint_id(snapshot),
            )
            self._release_run_lease(run, now=datetime.now(UTC))
            session.commit()
            return self._result_from_snapshot(run_id, thread_id, snapshot)

    def inspect(self, run_id: str) -> StateSnapshot | None:
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            if run.thread_id is None:
                return None
            return cast(StateSnapshot, self._graph.get_state(self._config(run.thread_id)))

    def recover_waiting_run_ids(self) -> list[str]:
        with self._session_factory() as session:
            runs = session.scalars(select(ReportRun).where(ReportRun.status == "waiting")).all()
            return [
                run.id
                for run in runs
                if run.thread_id
                and self._existing_checkpoint(self._config(run.thread_id)) is not None
            ]

    def recover_partial_failed_run_ids(self) -> list[str]:
        with self._session_factory() as session:
            plans = session.scalars(
                select(PublishPlan).where(
                    PublishPlan.status.in_(["approved", "executing", "partial_failed"])
                )
            ).all()
            run_ids: list[str] = []
            for plan in plans:
                operations = session.scalars(
                    select(SideEffectOperation)
                    .where(SideEffectOperation.publish_plan_id == plan.id)
                    .order_by(SideEffectOperation.sequence)
                ).all()
                if not operations:
                    continue
                if any(operation.status != "succeeded" for operation in operations):
                    if any(operation.status == "succeeded" for operation in operations) or any(
                        operation.status in {"running", "unknown"} for operation in operations
                    ):
                        run_ids.append(plan.run_id)
            return run_ids

    def cancel_run(
        self,
        run_id: str,
        *,
        reason: str,
        expected_status: str | None = None,
    ) -> dict[str, object]:
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            thread_id = self._ensure_run_identity(run)
            config = self._config(thread_id)
            snapshot = self._current_snapshot(config)
            current_stage = (
                self._current_stage_from_snapshot(snapshot) if snapshot else run.current_stage
            )
            current_node = (
                self._current_node_from_snapshot(snapshot) if snapshot else run.current_node
            )

            if run.status == "cancelled" or current_stage == "cancelled":
                return self._command_result(run, stage="cancelled", node="complete_run")
            if current_stage in {
                "blocked",
                "rejected",
                "partial_failed",
                "succeeded",
            } or run.status in {
                "blocked",
                "rejected",
                "partial_failed",
            }:
                raise ValueError("run is terminal")
            if expected_status is not None and expected_status not in {
                run.status,
                current_stage or "",
            }:
                raise ValueError("run status mismatch")

            now = datetime.now(UTC)
            self._claim_run_lease(run, now=now)
            self._cancel_pending_approvals(session, run_id, reason=reason, now=now)
            self._cancel_pending_publish_operations(session, run_id, reason=reason, now=now)

            checkpoint_ref = self._checkpoint_id(snapshot) if snapshot is not None else None
            if snapshot is not None:
                updated_config = self._graph.update_state(
                    config,
                    {
                        "cancel_requested": True,
                        "requested_action": "cancel_run",
                        "control": {
                            "requested_action": "cancel_run",
                            "resume_from": current_node or "load_project_config",
                            "cancel_requested": True,
                        },
                    },
                    as_node=current_node or "load_project_config",
                )
                self._graph.invoke(Command(goto="cancel_run"), config=updated_config)
                snapshot = cast(StateSnapshot, self._graph.get_state(updated_config))
                checkpoint_ref = self._checkpoint_id(snapshot)

            previous_status = run.status
            run.status = "cancelled"
            run.current_stage = "cancelled"
            run.current_node = "complete_run"
            self._record_transition(
                session,
                run,
                from_status=previous_status,
                to_status="cancelled",
                reason_code="run_cancelled",
                node_name="complete_run",
                checkpoint_ref=checkpoint_ref,
            )
            self._release_run_lease(run, now=now)
            session.commit()
            return self._command_result(run, stage="cancelled", node="complete_run", reason=reason)

    def safe_retry_run(
        self,
        run_id: str,
        *,
        reason: str,
        expected_status: str | None = None,
    ) -> dict[str, object]:
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            thread_id = self._ensure_run_identity(run)
            config = self._config(thread_id)
            snapshot = self._current_snapshot(config)
            current_stage = (
                self._current_stage_from_snapshot(snapshot) if snapshot else run.current_stage
            )

            if current_stage in {"cancelled", "rejected"} or run.status in {
                "cancelled",
                "rejected",
            }:
                raise ValueError("run is terminal")
            if expected_status is not None and expected_status not in {
                run.status,
                current_stage or "",
            }:
                raise ValueError("run status mismatch")

            publish_plan = self._load_approved_publish_plan(session, run)
            if publish_plan is None:
                raise ValueError("approved publish plan missing")
            if (
                run.approved_publish_plan_id is not None
                and run.approved_publish_plan_id != publish_plan.id
            ):
                raise ValueError("approved publish plan mismatch")
            if build_publish_plan_hash(publish_plan.canonical_plan) != publish_plan.plan_hash:
                raise ValueError("publish plan hash mismatch")
            approval = self._load_approved_publish_approval(session, run.id, publish_plan.plan_hash)
            if approval is None:
                raise ValueError("approved publish approval missing")

            retry_summary = self._publishing_service.verify_side_effects(
                run_id=run_id,
                publish_plan_ref=publish_plan.id,
                approved_plan_hash=publish_plan.plan_hash,
            )
            if retry_summary.status == "blocked":
                raise ValueError(
                    retry_summary.error_summary or retry_summary.error_code or "safe retry blocked"
                )

            operations = session.scalars(
                select(SideEffectOperation)
                .where(SideEffectOperation.publish_plan_id == publish_plan.id)
                .order_by(SideEffectOperation.sequence)
            ).all()
            if not operations:
                raise ValueError("publish operations missing")

            retry_sequences: list[int] = []
            for operation in operations:
                if operation.status == "succeeded":
                    continue
                if operation.status == "failed":
                    if operation.last_error_class not in RETRYABLE_ERROR_CLASSES:
                        raise ValueError("publish operation failure is not safe to retry")
                    retry_sequences.append(operation.sequence)
                    continue
                if operation.status == "unknown":
                    if operation.verification_status == "confirmed":
                        continue
                    retry_sequences.append(operation.sequence)
                    continue
                if operation.status in {"pending", "claimed", "running", "retry_pending"}:
                    retry_sequences.append(operation.sequence)

            now = datetime.now(UTC)
            self._claim_run_lease(run, now=now)
            if not retry_sequences:
                previous_status = run.status
                publish_plan.status = "completed"
                run.status = "completed"
                run.current_stage = "succeeded"
                run.current_node = "complete_run"
                self._record_transition(
                    session,
                    run,
                    from_status=previous_status,
                    to_status="completed",
                    reason_code="run_safe_retry_completed",
                    node_name="complete_run",
                    checkpoint_ref=self._checkpoint_id(snapshot) if snapshot is not None else None,
                )
                self._release_run_lease(run, now=now)
                session.commit()
                return self._command_result(
                    run, stage="succeeded", node="complete_run", reason=reason
                )

            if snapshot is None:
                raise ValueError("run has no checkpoint to resume")

            first_sequence = min(retry_sequences)
            for operation in operations:
                if operation.sequence < first_sequence:
                    continue
                if operation.status in {
                    "failed",
                    "unknown",
                    "pending",
                    "claimed",
                    "running",
                    "retry_pending",
                }:
                    operation.status = "retry_pending"
                    operation.verification_status = "not_checked"
                    operation.last_error_class = None
                    operation.last_error_summary = None

            publish_plan.status = "executing"
            first_node = self._publish_node_for_sequence(first_sequence)
            self._graph.invoke(Command(goto=first_node), config=config)
            snapshot = cast(StateSnapshot, self._graph.get_state(config))
            previous_status = run.status
            run.status = self._status_from_snapshot(snapshot)
            run.current_stage = self._current_stage_from_snapshot(snapshot) or run.current_stage
            run.current_node = self._current_node_from_snapshot(snapshot)
            run.scope_revision = self._scope_revision_from_snapshot(snapshot) or run.scope_revision
            self._record_transition(
                session,
                run,
                from_status=previous_status,
                to_status=run.status,
                reason_code="run_safe_retry_completed",
                node_name=run.current_node,
                checkpoint_ref=self._checkpoint_id(snapshot),
            )
            self._release_run_lease(run, now=now)
            session.commit()
            return self._command_result(
                run, stage=run.current_stage, node=run.current_node, reason=reason
            )

    def recover_expired_run_ids(self, *, now: datetime | None = None) -> list[str]:
        return self._lease_service.recover_expired_run_ids(now=now)

    def _config(self, thread_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": thread_id}}

    def _existing_checkpoint(self, config: dict[str, dict[str, str]]) -> CheckpointTuple | None:
        return cast(CheckpointTuple | None, self._checkpointer.get_tuple(config))

    def _load_run(self, session: Session, run_id: str) -> ReportRun:
        run = session.get(ReportRun, run_id)
        if run is None:
            raise ValueError(f"unknown run_id: {run_id}")
        return run

    def _load_project(self, session: Session, project_id: str) -> Project:
        project = session.get(Project, project_id)
        if project is None:
            raise ValueError(f"unknown project_id: {project_id}")
        return project

    def _ensure_run_identity(self, run: ReportRun) -> str:
        thread_id = run.thread_id or thread_id_for_run(run.id)
        run.thread_id = thread_id
        if not run.graph_version:
            run.graph_version = "weekly_report.v1"
        if not run.state_schema_version:
            run.state_schema_version = 1
        if not run.current_stage:
            run.current_stage = "created"
        return thread_id

    def _result_from_snapshot(
        self, run_id: str, thread_id: str, snapshot: StateSnapshot
    ) -> WorkflowExecutionResult:
        checkpoint_id = snapshot.config.get("configurable", {}).get("checkpoint_id")
        return WorkflowExecutionResult(
            run_id=run_id,
            thread_id=thread_id,
            status=self._status_from_snapshot(snapshot),
            checkpoint_id=checkpoint_id if isinstance(checkpoint_id, str) else None,
            snapshot=snapshot,
        )

    def _status_from_snapshot(self, snapshot: StateSnapshot) -> str:
        stage = self._current_stage_from_snapshot(snapshot)
        if stage == "waiting_confirmation":
            return "waiting"
        if stage == "waiting_publish_approval":
            return "waiting"
        if stage == "waiting_human_input":
            return "waiting"
        if stage in {
            "validated",
            "metrics_calculated",
            "report_generated",
            "report_rendered",
            "publish_approved",
            "publishing",
            "compensating",
            "succeeded",
        }:
            return "completed"
        if stage == "partial_failed":
            return "partial_failed"
        if stage == "blocked":
            return "blocked"
        if stage == "rejected":
            return "rejected"
        if stage == "cancelled":
            return "cancelled"
        return "waiting" if snapshot.interrupts else "completed"

    def _current_stage_from_snapshot(self, snapshot: StateSnapshot) -> str | None:
        value = snapshot.values.get("current_stage")
        return str(value) if isinstance(value, str) else None

    def _current_node_from_snapshot(self, snapshot: StateSnapshot) -> str | None:
        value = snapshot.values.get("current_node")
        return str(value) if isinstance(value, str) else None

    def _current_snapshot(self, config: dict[str, dict[str, str]]) -> StateSnapshot | None:
        if self._existing_checkpoint(config) is None:
            return None
        return cast(StateSnapshot, self._graph.get_state(config))

    def _checkpoint_id(self, snapshot: StateSnapshot) -> str | None:
        value = snapshot.config.get("configurable", {}).get("checkpoint_id")
        return value if isinstance(value, str) else None

    def _scope_revision_from_snapshot(self, snapshot: StateSnapshot) -> int | None:
        value = snapshot.values.get("scope_revision")
        return value if isinstance(value, int) else None

    def _reason_code_from_snapshot(self, snapshot: StateSnapshot, started: bool = False) -> str:
        stage = self._current_stage_from_snapshot(snapshot)
        if started:
            return "generation_confirmation_started"
        if stage == "waiting_confirmation":
            return "generation_confirmation_waiting"
        if stage == "waiting_human_input":
            return "human_input_waiting"
        if stage == "validated":
            return "generation_confirmation_approved"
        if stage == "building_publish_plan":
            return "publish_plan_building"
        if stage == "requesting_publish_confirmation":
            return "publish_confirmation_requesting"
        if stage == "waiting_publish_approval":
            return "publish_confirmation_waiting"
        if stage == "publish_approved":
            return "publish_confirmation_approved"
        if stage == "metrics_calculated":
            return "metrics_calculated"
        if stage == "report_generated":
            return "report_generated"
        if stage == "report_rendered":
            return "report_rendered"
        if stage in {"building_evidence", "generating_structured_report"}:
            return "report_generating"
        if stage in {"verifying_grounding", "rendering_report"}:
            return "report_grounding"
        if stage == "calculating_metrics":
            return "metrics_calculating"
        if stage == "publishing":
            return "side_effects_executing"
        if stage == "compensating":
            return "side_effects_compensating"
        if stage == "partial_failed":
            return "side_effects_partial_failed"
        if stage == "succeeded":
            return "side_effects_complete"
        if stage == "blocked":
            return "generation_confirmation_blocked"
        if stage == "rejected":
            return "generation_confirmation_rejected"
        if stage == "cancelled":
            return "generation_confirmation_cancelled"
        return "workflow_resumed"

    def _load_pending_approval(self, session: Session, run_id: str) -> HumanApproval | None:
        return session.scalar(
            select(HumanApproval).where(
                HumanApproval.run_id == run_id,
                HumanApproval.status == "pending",
            )
        )

    def _load_approved_publish_plan(self, session: Session, run: ReportRun) -> PublishPlan | None:
        if run.approved_publish_plan_id is not None:
            publish_plan = session.get(PublishPlan, run.approved_publish_plan_id)
            if publish_plan is not None:
                return publish_plan
        return session.scalar(
            select(PublishPlan)
            .where(
                PublishPlan.run_id == run.id,
                PublishPlan.status.in_(["approved", "executing", "partial_failed"]),
            )
            .order_by(PublishPlan.created_at.desc())
        )

    def _load_approved_publish_approval(
        self, session: Session, run_id: str, plan_hash: str
    ) -> HumanApproval | None:
        return session.scalar(
            select(HumanApproval).where(
                HumanApproval.run_id == run_id,
                HumanApproval.approval_type == "publish",
                HumanApproval.status == "approved",
                HumanApproval.plan_hash == plan_hash,
            )
        )

    def _cancel_pending_approvals(
        self, session: Session, run_id: str, *, reason: str, now: datetime
    ) -> None:
        approvals = session.scalars(
            select(HumanApproval).where(
                HumanApproval.run_id == run_id,
                HumanApproval.status == "pending",
            )
        ).all()
        for approval in approvals:
            approval.status = "cancelled"
            approval.decision = "cancel_run"
            approval.actor_id = "workflow-runtime"
            approval.actor_type = "system"
            approval.decided_at = now
            if approval.supplement is None:
                approval.supplement = {"reason": reason}

    def _cancel_pending_publish_operations(
        self, session: Session, run_id: str, *, reason: str, now: datetime
    ) -> None:
        publish_plan = session.scalar(
            select(PublishPlan)
            .where(PublishPlan.run_id == run_id)
            .order_by(PublishPlan.created_at.desc())
        )
        if publish_plan is None:
            return
        operations = session.scalars(
            select(SideEffectOperation)
            .where(SideEffectOperation.publish_plan_id == publish_plan.id)
            .order_by(SideEffectOperation.sequence)
        ).all()
        publish_plan.status = "cancelled"
        for operation in operations:
            if operation.status in {"pending", "claimed", "retry_pending"}:
                operation.status = "cancelled"
                operation.last_error_summary = reason
                operation.last_error_class = "cancelled"

    def _publish_node_for_sequence(self, sequence: int) -> str:
        return {
            1: "create_feishu_document",
            2: "send_group_summary",
            3: "archive_report_record",
        }.get(sequence, "archive_report_record")

    def _command_result(
        self,
        run: ReportRun,
        *,
        stage: str,
        node: str,
        reason: str = "",
    ) -> dict[str, object]:
        return {
            "run_id": run.id,
            "status": run.status,
            "current_stage": stage,
            "current_node": node,
            "reason": reason,
        }

    def _resume_challenge_id(self, resume_payload: Mapping[str, object]) -> str:
        value = resume_payload.get("challenge_id") or resume_payload.get("approval_ref")
        if not isinstance(value, str) or not value:
            raise ValueError("challenge_id is required")
        return value

    def _initial_state(self, run: ReportRun, project: Project) -> dict[str, object]:
        state = build_initial_state(run.id)
        state.update(
            {
                "project_id": run.project_id,
                "requester_id": "local-demo",
                "period_key": run.period_key,
                "period_start": run.period_start.isoformat(),
                "period_end": run.period_end.isoformat(),
                "project_timezone": project.timezone,
                "report_period": {
                    "start_at": run.period_start.isoformat(),
                    "end_at": run.period_end.isoformat(),
                    "timezone": project.timezone,
                },
                "scope_revision": run.scope_revision or 1,
                "approval_revision": 0,
                "requested_action": None,
                "resume_from": "load_project_config",
                "cancel_requested": False,
                "scope_override": None,
                "scope": {},
                "approval": {},
                "control": {
                    "requested_action": None,
                    "resume_from": "load_project_config",
                    "cancel_requested": False,
                    "scope_override": None,
                },
                "error": {},
            }
        )
        return state

    def _record_transition(
        self,
        session: Session,
        run: ReportRun,
        *,
        from_status: str,
        to_status: str,
        reason_code: str,
        node_name: str | None,
        checkpoint_ref: str | None,
    ) -> None:
        session.add(
            RunStatusHistory(
                run_id=run.id,
                from_status=from_status,
                to_status=to_status,
                reason_code=reason_code,
                actor_type="worker",
                actor_id="workflow-runtime",
                node_name=node_name,
                checkpoint_ref=checkpoint_ref,
            )
        )

    def _claim_run_lease(self, run: ReportRun, *, now: datetime) -> None:
        current_time = _as_utc(now)
        if run.lease_owner and run.lease_owner != self._worker_id:
            if run.lease_expires_at is None or _as_utc(run.lease_expires_at) > current_time:
                raise RunLeaseConflictError(f"run lease is held by {run.lease_owner}")
        run.lease_owner = self._worker_id
        run.lease_expires_at = current_time + timedelta(seconds=self._run_lease_seconds)
        run.heartbeat_at = current_time
        run.version = (run.version or 0) + 1

    def _release_run_lease(self, run: ReportRun, *, now: datetime) -> None:
        if run.lease_owner not in {None, self._worker_id}:
            raise RunLeaseConflictError(f"run lease is held by {run.lease_owner}")
        run.lease_owner = None
        run.lease_expires_at = None
        run.heartbeat_at = _as_utc(now)


class WorkflowWorker:
    def __init__(
        self,
        session_factory: SessionFactory,
        checkpointer: Any | None = None,
        collection_service: CollectionService | None = None,
        metrics_service: MetricsService | None = None,
        reporting_service: ReportingService | None = None,
        worker_id: str | None = None,
    ) -> None:
        self._runtime = WorkflowRuntime(
            session_factory,
            checkpointer,
            collection_service=collection_service,
            metrics_service=metrics_service,
            reporting_service=reporting_service,
            worker_id=worker_id,
        )

    def recover_waiting_runs(self) -> list[str]:
        return self._runtime.recover_waiting_run_ids()

    def recover_partial_failed_runs(self) -> list[str]:
        return self._runtime.recover_partial_failed_run_ids()

    def recover_expired_run_ids(self, *, now: datetime | None = None) -> list[str]:
        return self._runtime.recover_expired_run_ids(now=now)

    def resume(self, run_id: str, resume_payload: Mapping[str, object]) -> WorkflowExecutionResult:
        return self._runtime.resume(run_id, resume_payload)

    def inspect(self, run_id: str) -> StateSnapshot | None:
        return self._runtime.inspect(run_id)


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
