from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from langgraph.checkpoint.base import CheckpointTuple
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, StateSnapshot
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collection.service import CollectionService
from app.approvals import GenerationApprovalStore
from app.agent.graph import build_workflow_graph
from app.agent.state import build_initial_state, thread_id_for_run
from app.db.models import HumanApproval, Project, ReportRun, RunStatusHistory
from app.metrics.service import MetricsService
from app.publishing.service import PublishingService
from app.reporting.service import ReportingService

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
        collection_service: CollectionService | None = None,
        metrics_service: MetricsService | None = None,
        reporting_service: ReportingService | None = None,
        publishing_service: PublishingService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._approval_store = GenerationApprovalStore(session_factory)
        self._collection_service = collection_service or CollectionService(session_factory)
        self._metrics_service = metrics_service or MetricsService(session_factory)
        self._reporting_service = reporting_service or ReportingService(session_factory)
        self._publishing_service = publishing_service or PublishingService(session_factory)
        self._checkpointer: Any = checkpointer or MemorySaver()
        self._graph = build_workflow_graph(
            self._checkpointer,
            self._approval_store,
            self._collection_service,
            self._metrics_service,
            self._reporting_service,
            self._publishing_service,
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
                if "challenge_id" not in normalized_resume_payload and "approval_ref" not in normalized_resume_payload:
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
                if self._resume_challenge_id(normalized_resume_payload) != pending.challenge_id:
                    return self._result_from_snapshot(run_id, thread_id, snapshot)
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
        if stage in {
            "validated",
            "metrics_calculated",
            "report_generated",
            "report_rendered",
            "publish_approved",
            "publishing",
            "succeeded",
        }:
            return "completed"
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


class WorkflowWorker:
    def __init__(
        self,
        session_factory: SessionFactory,
        checkpointer: Any | None = None,
        collection_service: CollectionService | None = None,
        metrics_service: MetricsService | None = None,
        reporting_service: ReportingService | None = None,
    ) -> None:
        self._runtime = WorkflowRuntime(
            session_factory,
            checkpointer,
            collection_service,
            metrics_service,
            reporting_service,
        )

    def recover_waiting_runs(self) -> list[str]:
        return self._runtime.recover_waiting_run_ids()

    def resume(self, run_id: str, resume_payload: Mapping[str, object]) -> WorkflowExecutionResult:
        return self._runtime.resume(run_id, resume_payload)

    def inspect(self, run_id: str) -> StateSnapshot | None:
        return self._runtime.inspect(run_id)
