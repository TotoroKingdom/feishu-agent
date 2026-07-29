from datetime import date

import pytest
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.runtime import WorkflowRuntime
from app.agent.state import thread_id_for_run
from app.db.models import Base, HumanApproval, Project, ReportRun
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


def _approval_payload(snapshot: object, action: str, **extra: object) -> dict[str, object]:
    values = snapshot.values  # type: ignore[attr-defined]
    approval = values["approval"]
    scope = values["scope"]
    payload: dict[str, object] = {
        "action": action,
        "challenge_id": approval["challenge_id"],
        "approval_revision": approval["approval_revision"],
        "presented_hash": scope["scope_hash"],
        "actor_id": "local-demo",
    }
    payload.update(extra)
    return payload


def test_generation_confirmation_approve_and_duplicate_resume_are_idempotent() -> None:
    runtime, run_id, factory = make_runtime()

    started = runtime.start(run_id)
    first_resume = runtime.resume(run_id, _approval_payload(started.snapshot, "approve_generation"))
    duplicate_resume = runtime.resume(run_id, _approval_payload(started.snapshot, "approve_generation"))

    assert started.status == "waiting"
    assert started.snapshot.values["current_stage"] == "waiting_confirmation"  # type: ignore[index]
    assert first_resume.status == "completed"
    assert first_resume.snapshot.values["current_stage"] == "validated"  # type: ignore[index]
    assert first_resume.snapshot.values["current_node"] == "complete_run"  # type: ignore[index]
    assert duplicate_resume.status == "completed"

    with factory() as session:
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        approvals = session.scalars(
            select(HumanApproval).where(HumanApproval.run_id == run_id).order_by(HumanApproval.revision)
        ).all()

        assert run_row is not None
        assert run_row.status == "completed"
        assert run_row.current_stage == "validated"
        assert run_row.scope_revision == 1
        assert len(approvals) == 1
        assert approvals[0].status == "approved"
        assert approvals[0].decision == "approve_generation"
        assert approvals[0].challenge_id == started.snapshot.values["approval"]["challenge_id"]  # type: ignore[index]


def test_generation_confirmation_modify_creates_new_revision_and_requeues_confirmation() -> None:
    runtime, run_id, factory = make_runtime()

    started = runtime.start(run_id)
    modified = runtime.resume(
        run_id,
        _approval_payload(
            started.snapshot,
            "modify_generation_scope",
            scope_override={
                "user_instructions": "focus on blockers",
                "selected_repository_ids": ["repo-1", "repo-2"],
            },
        ),
    )
    stale_repeat = runtime.resume(run_id, _approval_payload(started.snapshot, "approve_generation"))

    assert modified.status == "waiting"
    assert modified.snapshot.values["current_stage"] == "waiting_confirmation"  # type: ignore[index]
    assert modified.snapshot.values["scope_revision"] == 2  # type: ignore[index]
    assert modified.snapshot.values["approval"]["approval_revision"] == 2  # type: ignore[index]
    assert modified.snapshot.values["approval"]["status"] == "pending"  # type: ignore[index]
    assert modified.snapshot.values["scope"]["scope_hash"] != started.snapshot.values["scope"]["scope_hash"]  # type: ignore[index]
    assert stale_repeat.status == "waiting"

    with factory() as session:
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        approvals = session.scalars(
            select(HumanApproval).where(HumanApproval.run_id == run_id).order_by(HumanApproval.revision)
        ).all()

        assert run_row is not None
        assert run_row.status == "waiting"
        assert run_row.current_stage == "waiting_confirmation"
        assert run_row.scope_revision == 2
        assert [approval.status for approval in approvals] == ["superseded", "pending"]
        assert approvals[0].decision == "modify_generation_scope"
        assert approvals[1].revision == 2
        assert approvals[1].status == "pending"


@pytest.mark.parametrize(
    ("action", "expected_status", "expected_stage"),
    [
        ("reject_generation", "rejected", "rejected"),
        ("cancel_run", "cancelled", "cancelled"),
    ],
)
def test_generation_confirmation_terminal_actions(
    action: str, expected_status: str, expected_stage: str
) -> None:
    runtime, run_id, factory = make_runtime()

    started = runtime.start(run_id)
    result = runtime.resume(run_id, _approval_payload(started.snapshot, action))

    assert result.status == expected_status
    assert result.snapshot.values["current_stage"] == expected_stage  # type: ignore[index]

    with factory() as session:
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        approvals = session.scalars(select(HumanApproval).where(HumanApproval.run_id == run_id)).all()

        assert run_row is not None
        assert run_row.status == expected_status
        assert run_row.current_stage == expected_stage
        assert len(approvals) == 1
        assert approvals[0].status == expected_status
