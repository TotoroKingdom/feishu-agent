from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from langgraph.checkpoint.base import CheckpointTuple
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, StateSnapshot
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.graph import build_workflow_graph
from app.agent.state import build_initial_state, thread_id_for_run
from app.db.models import ReportRun, RunStatusHistory

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
    ) -> None:
        self._session_factory = session_factory
        self._checkpointer: Any = checkpointer or MemorySaver()
        self._graph = build_workflow_graph(self._checkpointer)

    def start(self, run_id: str) -> WorkflowExecutionResult:
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            thread_id = self._ensure_run_identity(run)
            config = self._config(thread_id)
            existing = self._existing_checkpoint(config)
            if existing is not None:
                snapshot = cast(StateSnapshot, self._graph.get_state(config))
                return self._result_from_snapshot(run_id, thread_id, snapshot)
            session.flush()
            self._graph.invoke(build_initial_state(run_id), config=config)
            snapshot = cast(StateSnapshot, self._graph.get_state(config))
            self._record_transition(
                session,
                run,
                from_status=run.status,
                to_status=self._status_from_snapshot(snapshot),
                reason_code="workflow_started",
                node_name="bootstrap_run",
                checkpoint_ref=self._checkpoint_id(snapshot),
            )
            run.status = self._status_from_snapshot(snapshot)
            run.current_stage = self._current_stage_from_snapshot(snapshot) or run.current_stage
            run.current_node = self._current_node_from_snapshot(snapshot)
            session.commit()
            return self._result_from_snapshot(run_id, thread_id, snapshot)

    def resume(self, run_id: str, resume_payload: Mapping[str, object]) -> WorkflowExecutionResult:
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            thread_id = self._ensure_run_identity(run)
            config = self._config(thread_id)
            if self._existing_checkpoint(config) is None:
                raise ValueError("run has no checkpoint to resume")
            self._graph.invoke(Command(resume=dict(resume_payload)), config=config)
            snapshot = cast(StateSnapshot, self._graph.get_state(config))
            previous_status = run.status
            run.status = self._status_from_snapshot(snapshot)
            run.current_stage = self._current_stage_from_snapshot(snapshot) or run.current_stage
            run.current_node = self._current_node_from_snapshot(snapshot)
            self._record_transition(
                session,
                run,
                from_status=previous_status,
                to_status=run.status,
                reason_code="workflow_resumed",
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
    ) -> None:
        self._runtime = WorkflowRuntime(session_factory, checkpointer)

    def recover_waiting_runs(self) -> list[str]:
        return self._runtime.recover_waiting_run_ids()

    def resume(self, run_id: str, resume_payload: Mapping[str, object]) -> WorkflowExecutionResult:
        return self._runtime.resume(run_id, resume_payload)

    def inspect(self, run_id: str) -> StateSnapshot | None:
        return self._runtime.inspect(run_id)
