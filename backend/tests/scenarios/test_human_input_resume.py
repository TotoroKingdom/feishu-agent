from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.runtime import WorkflowRuntime
from app.collection.service import CollectionProviders, CollectionService, CollectionStageOutcome
from app.core.config import Settings
from app.db.models import (
    Base,
    HumanApproval,
    NormalizedSnapshot,
    Project,
    ReportRun,
    ValidationResult,
    new_id,
)
from app.domain.runs import RunCreationService
from app.main import create_app
from app.providers.fake import FakeFeishuProvider, FakeGitHubProvider, FakeScenario


class HumanInputResumeCollectionService(CollectionService):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        super().__init__(
            session_factory,
            CollectionProviders(
                feishu=FakeFeishuProvider(FakeScenario.HAPPY),
                github=FakeGitHubProvider(FakeScenario.HAPPY),
            ),
        )
        self.collect_feishu_calls = 0
        self.collect_github_calls = 0
        self.normalize_calls = 0
        self.validate_calls = 0

    def collect_feishu_data(self, run_id: str, scope: dict[str, object]) -> CollectionStageOutcome:
        self.collect_feishu_calls += 1
        return super().collect_feishu_data(run_id, scope)

    def collect_github_data(self, run_id: str, scope: dict[str, object]) -> CollectionStageOutcome:
        self.collect_github_calls += 1
        return super().collect_github_data(run_id, scope)

    def normalize_data(self, run_id: str, scope: dict[str, object]) -> CollectionStageOutcome:
        self.normalize_calls += 1
        return super().normalize_data(run_id, scope)

    def validate_data(self, run_id: str, normalized_snapshot_id: str) -> CollectionStageOutcome:
        self.validate_calls += 1
        if self.validate_calls == 1:
            with self._session_factory() as session:
                snapshot = session.get(NormalizedSnapshot, normalized_snapshot_id)
                assert snapshot is not None
                existing = session.scalar(
                    select(ValidationResult).where(
                        ValidationResult.run_id == run_id,
                        ValidationResult.input_snapshot_hash == snapshot.content_hash,
                    )
                )
                if existing is None:
                    validation_result = ValidationResult(
                        id=new_id(),
                        run_id=run_id,
                        validation_pass=False,
                        data_quality_status="partial",
                        rule_set_version="human-input-test.v1",
                        critical_count=1,
                        warning_count=0,
                        missing_items=["github_username"],
                        conflicts=[],
                        warnings=[],
                        input_snapshot_hash=snapshot.content_hash,
                        created_at=datetime.now(UTC),
                    )
                    session.add(validation_result)
                    session.flush()
                    validation_result_id = validation_result.id
                else:
                    validation_result_id = existing.id
                session.commit()
            return CollectionStageOutcome(
                status="blocked",
                error_code="MISSING_CRITICAL_MEMBER_MAPPING",
                error_summary="missing github_username for member mapping",
                validation_result_ref=validation_result_id,
            )

        with self._session_factory() as session:
            approval = session.scalar(
                select(HumanApproval).where(
                    HumanApproval.run_id == run_id,
                    HumanApproval.approval_type == "human_input",
                    HumanApproval.status == "approved",
                )
            )
            assert approval is not None
            assert approval.supplement == {"github_username": "octocat"}

        return super().validate_data(run_id, normalized_snapshot_id)


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


def _make_environment() -> tuple[
    TestClient,
    WorkflowRuntime,
    sessionmaker[Session],
    HumanInputResumeCollectionService,
    MemorySaver,
    str,
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
            datetime(2026, 7, 20, tzinfo=UTC).date(),
            datetime(2026, 7, 27, tzinfo=UTC).date(),
        )
        session.commit()
        run_id = run.id
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    service = HumanInputResumeCollectionService(factory)
    saver = MemorySaver()
    runtime = WorkflowRuntime(factory, saver, collection_service=service)
    client = TestClient(
        create_app(
            settings=_settings(),
            session_factory=factory,
            workflow_runtime=runtime,
        )
    )
    return client, runtime, factory, service, saver, run_id


def _allow_actor(session_factory: sessionmaker[Session], challenge_id: str) -> None:
    with session_factory() as session:
        approval = session.scalar(
            select(HumanApproval).where(HumanApproval.challenge_id == challenge_id)
        )
        assert approval is not None
        approval.requested_from = ["ou_123", "tenant:ou_123"]
        session.commit()


def _approve_generation(
    client: TestClient,
    runtime: WorkflowRuntime,
    session_factory: sessionmaker[Session],
    run_id: str,
) -> object:
    started = runtime.start(run_id)
    generation_snapshot = started.snapshot
    generation_challenge = generation_snapshot.values["approval"]["challenge_id"]  # type: ignore[index]
    generation_revision = generation_snapshot.values["approval"]["approval_revision"]  # type: ignore[index]
    generation_scope_hash = generation_snapshot.values["scope"]["scope_hash"]  # type: ignore[index]
    _allow_actor(session_factory, generation_challenge)

    response = client.post(
        "/api/v1/feishu/card-actions",
        headers={"X-Feishu-Verification-Token": "token"},
        json={
            "external_event_id": f"evt-generation-{run_id}",
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
    assert response.status_code == 200
    assert response.json()["data"]["workflow_status"] == "waiting"
    return runtime.inspect(run_id)


def _submit_human_input(
    client: TestClient,
    session_factory: sessionmaker[Session],
    run_id: str,
    snapshot: object,
    *,
    external_event_id: str,
    payload: dict[str, object],
) -> tuple[int, dict[str, object]]:
    values = snapshot.values  # type: ignore[attr-defined]
    approval = values["approval"]
    challenge_id = approval["challenge_id"]
    _allow_actor(session_factory, challenge_id)
    response = client.post(
        "/api/v1/feishu/card-actions",
        headers={"X-Feishu-Verification-Token": "token"},
        json={
            "external_event_id": external_event_id,
            "actor": {"open_id": "ou_123", "tenant_key": "tenant"},
            "action": {
                "action_type": "submit_human_input",
                "challenge_id": challenge_id,
                "run_id": run_id,
                "approval_revision": approval["approval_revision"],
                "payload": payload,
                "presented_hash": approval["request_payload_hash"],
            },
            "occurred_at": datetime.now(UTC).isoformat(),
        },
    )
    return response.status_code, response.json()


def test_human_input_rejects_invalid_payload_and_accepts_valid_supplement() -> None:
    client, runtime, factory, _, _, run_id = _make_environment()

    waiting_snapshot = _approve_generation(client, runtime, factory, run_id)
    human_input_approval = waiting_snapshot.values["approval"]  # type: ignore[index]

    invalid_status, invalid_body = _submit_human_input(
        client,
        factory,
        run_id,
        waiting_snapshot,
        external_event_id="evt-human-input-invalid",
        payload={},
    )
    assert invalid_status == 400
    assert "supplement" in invalid_body["detail"]

    with factory() as session:
        approval = session.scalar(
            select(HumanApproval).where(
                HumanApproval.challenge_id == human_input_approval["challenge_id"]
            )
        )
        assert approval is not None
        assert approval.status == "pending"
        assert approval.supplement is None

    valid_status, valid_body = _submit_human_input(
        client,
        factory,
        run_id,
        waiting_snapshot,
        external_event_id="evt-human-input-valid",
        payload={"github_username": "octocat"},
    )
    assert valid_status == 200
    assert valid_body["data"]["workflow_status"] == "waiting"

    with factory() as session:
        approval = session.scalar(
            select(HumanApproval).where(
                HumanApproval.challenge_id == human_input_approval["challenge_id"]
            )
        )
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        assert approval is not None
        assert approval.status == "approved"
        assert approval.supplement == {"github_username": "octocat"}
        assert run_row is not None
        assert run_row.current_stage == "waiting_publish_approval"


def test_human_input_duplicate_and_stale_callbacks_are_rejected() -> None:
    client, runtime, factory, _, _, run_id = _make_environment()

    waiting_snapshot = _approve_generation(client, runtime, factory, run_id)

    first_status, first_body = _submit_human_input(
        client,
        factory,
        run_id,
        waiting_snapshot,
        external_event_id="evt-human-input-dup",
        payload={"github_username": "octocat"},
    )
    assert first_status == 200
    assert first_body["data"]["duplicate"] is False

    duplicate_status, duplicate_body = _submit_human_input(
        client,
        factory,
        run_id,
        waiting_snapshot,
        external_event_id="evt-human-input-dup",
        payload={"github_username": "octocat"},
    )
    assert duplicate_status == 200
    assert duplicate_body["data"]["duplicate"] is True

    stale_status, stale_body = _submit_human_input(
        client,
        factory,
        run_id,
        waiting_snapshot,
        external_event_id="evt-human-input-stale",
        payload={"github_username": "octocat"},
    )
    assert stale_status == 200
    assert stale_body["data"]["duplicate"] is True


def test_human_input_waiting_state_survives_restart_and_does_not_restart_from_beginning() -> None:
    client, runtime, factory, service, saver, run_id = _make_environment()

    waiting_snapshot = _approve_generation(client, runtime, factory, run_id)
    restarted_runtime = WorkflowRuntime(factory, saver, collection_service=service)
    client.app.state.workflow_runtime = restarted_runtime

    restarted_snapshot = restarted_runtime.inspect(run_id)
    assert restarted_snapshot is not None
    assert restarted_snapshot.values["current_stage"] == "waiting_human_input"  # type: ignore[index]
    assert restarted_snapshot.values["current_node"] == "wait_human_input"  # type: ignore[index]

    valid_status, valid_body = _submit_human_input(
        client,
        factory,
        run_id,
        waiting_snapshot,
        external_event_id="evt-human-input-restart",
        payload={"github_username": "octocat"},
    )
    assert valid_status == 200
    assert valid_body["data"]["workflow_status"] == "waiting"

    assert service.collect_feishu_calls == 1
    assert service.collect_github_calls == 1
    assert service.normalize_calls == 1
    assert service.validate_calls == 2

    snapshot = restarted_runtime.inspect(run_id)
    assert snapshot is not None
    assert snapshot.values["current_stage"] == "waiting_publish_approval"  # type: ignore[index]
    assert snapshot.values["current_node"] == "wait_publish_confirmation"  # type: ignore[index]

    with factory() as session:
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        assert run_row is not None
        assert run_row.status == "waiting"
        assert run_row.current_stage == "waiting_publish_approval"
