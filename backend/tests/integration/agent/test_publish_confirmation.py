from __future__ import annotations

from datetime import date

from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.runtime import WorkflowRuntime
from app.db.models import Base, HumanApproval, Project, PublishPlan, ReportRun, ReportVersion, ToolExecution
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


def _generation_payload(snapshot: object, action: str) -> dict[str, object]:
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


def _publish_payload(snapshot: object, action: str, **extra: object) -> dict[str, object]:
    values = snapshot.values  # type: ignore[attr-defined]
    approval = values["approval"]
    publish = values["publish"]
    payload: dict[str, object] = {
        "action": action,
        "challenge_id": approval["challenge_id"],
        "approval_revision": approval["approval_revision"],
        "presented_hash": publish["plan_hash"],
        "actor_id": "local-demo",
    }
    payload.update(extra)
    return payload


def test_publish_confirmation_happy_path_waits_then_completes() -> None:
    runtime, run_id, factory = make_runtime()

    started = runtime.start(run_id)
    waiting = runtime.resume(run_id, _generation_payload(started.snapshot, "approve_generation"))
    completed = runtime.resume(run_id, _publish_payload(waiting.snapshot, "approve_publish"))
    duplicate = runtime.resume(run_id, _publish_payload(waiting.snapshot, "approve_publish"))

    assert started.status == "waiting"
    assert waiting.status == "waiting"
    assert waiting.snapshot.values["current_stage"] == "waiting_publish_approval"  # type: ignore[index]
    assert waiting.snapshot.values["current_node"] == "wait_publish_confirmation"  # type: ignore[index]
    assert waiting.snapshot.values["publish_plan_ref"]  # type: ignore[index]
    assert waiting.snapshot.values["publish"]["plan_hash"]  # type: ignore[index]

    assert completed.status == "completed"
    assert duplicate.status == "completed"
    assert completed.snapshot.values["current_stage"] == "publish_approved"  # type: ignore[index]
    assert completed.snapshot.values["current_node"] == "complete_run"  # type: ignore[index]
    assert completed.snapshot.values["publish_plan_ref"] == duplicate.snapshot.values["publish_plan_ref"]  # type: ignore[index]

    with factory() as session:
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        publish_plan = session.scalar(select(PublishPlan).where(PublishPlan.run_id == run_id))
        approvals = session.scalars(
            select(HumanApproval).where(HumanApproval.run_id == run_id).order_by(HumanApproval.created_at)
        ).all()
        report_version = session.scalar(select(ReportVersion).where(ReportVersion.run_id == run_id))
        tool_executions = session.scalars(select(ToolExecution).where(ToolExecution.run_id == run_id)).all()

        assert run_row is not None
        assert run_row.status == "completed"
        assert run_row.current_stage == "publish_approved"
        assert publish_plan is not None
        assert publish_plan.status == "approved"
        assert run_row.approved_publish_plan_id == publish_plan.id
        assert report_version is not None
        assert len(approvals) == 2
        assert [approval.approval_type for approval in approvals] == ["generation", "publish"]
        assert approvals[1].status == "approved"
        assert len(tool_executions) == 10


def test_publish_confirmation_hash_change_reissues_pending_approval() -> None:
    runtime, run_id, factory = make_runtime()

    started = runtime.start(run_id)
    waiting = runtime.resume(run_id, _generation_payload(started.snapshot, "approve_generation"))

    old_plan_hash = waiting.snapshot.values["publish"]["plan_hash"]  # type: ignore[index]
    reissued = runtime.resume(
        run_id,
        _publish_payload(
            waiting.snapshot,
            "approve_publish",
            presented_hash="tampered-hash",
        ),
    )

    assert reissued.status == "waiting"
    assert reissued.snapshot.values["current_stage"] == "waiting_publish_approval"  # type: ignore[index]
    assert reissued.snapshot.values["approval"]["approval_revision"] == 2  # type: ignore[index]
    assert reissued.snapshot.values["publish"]["plan_hash"] == old_plan_hash  # type: ignore[index]

    with factory() as session:
        plans = session.scalars(select(PublishPlan).where(PublishPlan.run_id == run_id)).all()
        approvals = session.scalars(
            select(HumanApproval).where(HumanApproval.run_id == run_id, HumanApproval.approval_type == "publish")
        ).all()

        assert len(plans) == 1
        assert plans[0].status == "pending_approval"
        assert len(approvals) == 2
        assert approvals[0].status == "superseded"
        assert approvals[1].status == "pending"
