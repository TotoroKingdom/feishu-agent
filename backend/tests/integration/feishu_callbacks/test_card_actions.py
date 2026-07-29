from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.runtime import WorkflowRuntime
from app.core.config import Settings
from app.db.models import Base, CallbackEvent, HumanApproval, Project, ReportRun
from app.domain.runs import RunCreationService
from app.main import create_app


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        app_profile="local-demo",
        feishu_provider="real",
        feishu_app_id="cli-test-app",
        feishu_app_secret=SecretStr("secret"),
        feishu_verification_token=SecretStr("token"),
        feishu_allowed_actor_refs=["ou_123", "tenant:ou_123"],
    )


def _make_environment() -> tuple[TestClient, WorkflowRuntime, sessionmaker[Session], str]:
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
            datetime(2026, 7, 20, tzinfo=UTC).date(),
            datetime(2026, 7, 27, tzinfo=UTC).date(),
        )
        session.commit()
        run_id = run.id
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    runtime = WorkflowRuntime(factory, MemorySaver())
    client = TestClient(
        create_app(
            settings=_settings(),
            session_factory=factory,
            workflow_runtime=runtime,
        )
    )
    return client, runtime, factory, run_id


def _allow_actor(session_factory: sessionmaker[Session], challenge_id: str) -> None:
    with session_factory() as session:
        approval = session.scalar(
            select(HumanApproval).where(HumanApproval.challenge_id == challenge_id)
        )
        assert approval is not None
        approval.requested_from = ["ou_123", "tenant:ou_123"]
        session.commit()


def test_feishu_event_challenge_echoes_challenge_when_token_is_valid() -> None:
    client, _, _, _ = _make_environment()

    response = client.post(
        "/api/v1/feishu/events",
        json={"challenge": "challenge-1"},
        headers={"X-Feishu-Verification-Token": "token"},
    )

    assert response.status_code == 200
    assert response.json() == {"challenge": "challenge-1"}


def test_card_action_resumes_workflow_and_deduplicates_repeated_events() -> None:
    client, runtime, factory, run_id = _make_environment()

    started = runtime.start(run_id)
    generation_challenge = started.snapshot.values["approval"]["challenge_id"]  # type: ignore[index]
    generation_revision = started.snapshot.values["approval"]["approval_revision"]  # type: ignore[index]
    generation_scope_hash = started.snapshot.values["scope"]["scope_hash"]  # type: ignore[index]
    _allow_actor(factory, generation_challenge)

    generation_response = client.post(
        "/api/v1/feishu/card-actions",
        headers={"X-Feishu-Verification-Token": "token"},
        json={
            "external_event_id": "evt-generation-1",
            "actor": {"open_id": "ou_123", "tenant_key": "tenant"},
            "action": {
                "action_type": "approve_generation",
                "challenge_id": generation_challenge,
                "run_id": run_id,
                "approval_revision": generation_revision,
                "payload": {},
                "presented_hash": generation_scope_hash,
            },
            "occurred_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        },
    )

    assert generation_response.status_code == 200
    assert generation_response.json()["data"]["duplicate"] is False
    assert generation_response.json()["data"]["workflow_status"] == "waiting"

    waiting_publish = runtime.inspect(run_id)
    assert waiting_publish is not None
    publish_challenge = waiting_publish.values["approval"]["challenge_id"]  # type: ignore[index]
    publish_revision = waiting_publish.values["approval"]["approval_revision"]  # type: ignore[index]
    publish_plan_hash = waiting_publish.values["publish"]["plan_hash"]  # type: ignore[index]
    _allow_actor(factory, publish_challenge)

    publish_response = client.post(
        "/api/v1/feishu/card-actions",
        headers={"X-Feishu-Verification-Token": "token"},
        json={
            "external_event_id": "evt-publish-1",
            "actor": {"open_id": "ou_123", "tenant_key": "tenant"},
            "action": {
                "action_type": "approve_publish",
                "challenge_id": publish_challenge,
                "run_id": run_id,
                "approval_revision": publish_revision,
                "payload": {},
                "presented_hash": publish_plan_hash,
            },
            "occurred_at": datetime.now(UTC).isoformat(),
        },
    )

    duplicate_publish_response = client.post(
        "/api/v1/feishu/card-actions",
        headers={"X-Feishu-Verification-Token": "token"},
        json={
            "external_event_id": "evt-publish-1",
            "actor": {"open_id": "ou_123", "tenant_key": "tenant"},
            "action": {
                "action_type": "approve_publish",
                "challenge_id": publish_challenge,
                "run_id": run_id,
                "approval_revision": publish_revision,
                "payload": {},
                "presented_hash": publish_plan_hash,
            },
            "occurred_at": datetime.now(UTC).isoformat(),
        },
    )

    assert publish_response.status_code == 200
    assert publish_response.json()["data"]["duplicate"] is False
    assert publish_response.json()["data"]["workflow_status"] == "completed"
    assert duplicate_publish_response.status_code == 200
    assert duplicate_publish_response.json()["data"]["duplicate"] is True

    with factory() as session:
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        approvals = session.scalars(
            select(HumanApproval)
            .where(HumanApproval.run_id == run_id)
            .order_by(HumanApproval.revision)
        ).all()
        events = session.scalars(
            select(CallbackEvent).where(CallbackEvent.run_id == run_id).order_by(CallbackEvent.id)
        ).all()

        assert run_row is not None
        assert run_row.status == "completed"
        assert run_row.current_stage == "succeeded"
        assert [approval.status for approval in approvals] == ["approved", "approved"]
        assert len(events) == 2
        assert all(event.status == "processed" for event in events)
