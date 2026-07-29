from datetime import date

from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.runtime import WorkflowRuntime, WorkflowWorker
from app.agent.state import thread_id_for_run
from app.db.models import Base, MetricSnapshot, Project, ReportRun
from app.domain.runs import RunCreationService


def make_runtime() -> tuple[
    WorkflowRuntime, WorkflowWorker, str, MemorySaver, sessionmaker[Session]
]:
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
    saver = MemorySaver()
    runtime = WorkflowRuntime(factory, saver)
    worker = WorkflowWorker(factory, saver)
    return runtime, worker, run_id, saver, factory


def _publish_payload(snapshot: object, action: str) -> dict[str, object]:
    values = snapshot.values  # type: ignore[attr-defined]
    approval = values["approval"]
    publish = values["publish"]
    return {
        "action": action,
        "challenge_id": approval["challenge_id"],
        "approval_revision": approval["approval_revision"],
        "presented_hash": publish["plan_hash"],
        "actor_id": "local-demo",
    }


def test_runtime_start_interrupt_resume_and_repeat_start_are_stable() -> None:
    runtime, _, run_id, _, factory = make_runtime()

    first = runtime.start(run_id)
    second = runtime.start(run_id)
    snapshot = runtime.inspect(run_id)
    resume_payload = {
        "action": "approve_generation",
        "challenge_id": first.snapshot.values["approval"]["challenge_id"],
        "approval_revision": first.snapshot.values["approval"]["approval_revision"],
        "presented_hash": first.snapshot.values["scope"]["scope_hash"],
        "actor_id": "local-demo",
    }
    waiting_publish = runtime.resume(run_id, resume_payload)
    publish_resume = runtime.resume(run_id, _publish_payload(waiting_publish.snapshot, "approve_publish"))
    completed = runtime.inspect(run_id)

    assert first.status == "waiting"
    assert first.thread_id == thread_id_for_run(run_id)
    assert first.checkpoint_id is not None
    assert second.checkpoint_id == first.checkpoint_id
    assert snapshot is not None
    assert snapshot.values["current_stage"] == "waiting_confirmation"
    assert waiting_publish.status == "waiting"
    assert waiting_publish.snapshot.values["current_stage"] == "waiting_publish_approval"  # type: ignore[index]
    assert publish_resume.status == "completed"
    assert completed is not None
    assert completed.values["current_stage"] == "publish_approved"
    assert completed.values["current_node"] == "complete_run"
    assert isinstance(completed.values["source_batch_refs"], list)
    assert len(completed.values["source_batch_refs"]) == 2
    assert all(isinstance(item, str) and item for item in completed.values["source_batch_refs"])
    assert isinstance(completed.values["normalized_snapshot_ref"], str)
    assert completed.values["normalized_snapshot_ref"]
    assert isinstance(completed.values["validation_result_ref"], str)
    assert completed.values["validation_result_ref"]
    assert isinstance(completed.values["metrics_ref"], str)
    assert completed.values["metrics_ref"]
    assert isinstance(completed.values["rendered_report_ref"], str)
    assert completed.values["rendered_report_ref"]

    with factory() as session:
        row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        metric_row = session.scalar(select(MetricSnapshot).where(MetricSnapshot.run_id == run_id))
        assert row is not None
        assert row.thread_id == thread_id_for_run(run_id)
        assert row.status == "completed"
        assert row.current_stage == "publish_approved"
        assert row.scope_revision == 1
        assert metric_row is not None


def test_worker_restart_finds_waiting_runs_and_resumes_them() -> None:
    runtime, worker, run_id, saver, factory = make_runtime()
    first = runtime.start(run_id)

    assert first.status == "waiting"
    assert worker.recover_waiting_runs() == [run_id]

    restarted_worker = WorkflowWorker(factory, saver)
    assert restarted_worker.recover_waiting_runs() == [run_id]

    resumed = restarted_worker.resume(
        run_id,
        {
            "action": "approve_generation",
            "challenge_id": first.snapshot.values["approval"]["challenge_id"],
            "approval_revision": first.snapshot.values["approval"]["approval_revision"],
            "presented_hash": first.snapshot.values["scope"]["scope_hash"],
            "actor_id": "local-demo",
        },
    )
    assert resumed.status == "waiting"
