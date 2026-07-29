from __future__ import annotations

from datetime import date

from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.runtime import WorkflowRuntime
from app.db.models import Base, MetricSnapshot, Project, ReportRun, ToolExecution
from app.domain.runs import RunCreationService


def make_runtime() -> tuple[WorkflowRuntime, str, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        project = Project(name="Demo", timezone="Asia/Shanghai")
        session.add(project)
        session.flush()
        run = RunCreationService(session).create_run(
            project.id,
            "2026-W30",
            date(2026, 7, 20),
            date(2026, 7, 27),
        )
        session.commit()
        run_id = run.id
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    runtime = WorkflowRuntime(factory, MemorySaver())
    return runtime, run_id, factory


def _approval_payload(snapshot: object, action: str) -> dict[str, object]:
    values = snapshot.values  # type: ignore[attr-defined]
    approval = values["approval"]
    scope = values["scope"]
    return {
        "action": action,
        "challenge_id": approval["challenge_id"],
        "approval_revision": approval["approval_revision"],
        "presented_hash": scope["scope_hash"],
        "actor_id": "local-demo",
    }


def test_metrics_node_persists_snapshot_and_reuses_it_on_duplicate_resume() -> None:
    runtime, run_id, factory = make_runtime()

    started = runtime.start(run_id)
    first_resume = runtime.resume(run_id, _approval_payload(started.snapshot, "approve_generation"))
    duplicate_resume = runtime.resume(run_id, _approval_payload(started.snapshot, "approve_generation"))

    assert started.status == "waiting"
    assert first_resume.status == "completed"
    assert duplicate_resume.status == "completed"
    assert first_resume.snapshot.values["current_stage"] == "report_generated"  # type: ignore[index]
    assert first_resume.snapshot.values["metrics_ref"] == duplicate_resume.snapshot.values["metrics_ref"]  # type: ignore[index]
    assert first_resume.snapshot.values["report_version_ref"] == duplicate_resume.snapshot.values["report_version_ref"]  # type: ignore[index]

    with factory() as session:
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        metric_snapshots = session.scalars(
            select(MetricSnapshot).where(MetricSnapshot.run_id == run_id)
        ).all()
        tool_executions = session.scalars(
            select(ToolExecution).where(ToolExecution.run_id == run_id)
        ).all()

        assert run_row is not None
        assert run_row.status == "completed"
        assert run_row.current_stage == "report_generated"
        assert len(metric_snapshots) == 1
        assert metric_snapshots[0].definition_version == "minimal.v1"
        assert len(tool_executions) == 7
