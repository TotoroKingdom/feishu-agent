from __future__ import annotations

import json
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.runtime import WorkflowRuntime
from app.approvals import canonical_json_hash
from app.core.config import Settings
from app.db.models import (
    Base,
    Project,
    PublishPlan,
    ReportArtifact,
    ReportRun,
    ReportVersion,
    SideEffectOperation,
    new_id,
)
from app.domain.runs import RunCreationService
from app.main import create_app
from app.providers.fake import FakeEffectProvider, FakeScenario
from app.publishing.service import PublishingService
from app.side_effects.executor import SideEffectExecutor, build_operation_key


class PartialFailureVerifierProvider(FakeEffectProvider):
    def __init__(self) -> None:
        super().__init__(FakeScenario.HAPPY)
        self._archive_query_calls = 0

    def create_feishu_document(self, report_id: str) -> dict[str, str]:
        return {
            "status": "success",
            "external_id": f"fake-document-{report_id}",
            "url": f"https://fake.feishu.local/doc/{report_id}",
            "provider_request_id": f"fake-request-document-{report_id}",
        }

    def send_group_summary(self, run_id: str) -> dict[str, str]:
        return {
            "status": "success",
            "external_id": f"fake-message-{run_id}",
            "url": f"https://fake.feishu.local/message/{run_id}",
            "provider_request_id": f"fake-request-message-{run_id}",
        }

    def upsert_bitable_archive(self, run_id: str) -> dict[str, str]:
        return {
            "status": "success",
            "external_id": f"fake-archive-{run_id}",
            "url": f"https://fake.feishu.local/archive/{run_id}",
            "provider_request_id": f"fake-request-archive-{run_id}",
        }

    def query_feishu_document(self, external_id: str, run_id: str) -> dict[str, str]:
        return {
            "status": "confirmed",
            "external_id": external_id,
            "run_id": run_id,
            "url": f"https://fake.feishu.local/doc/{run_id}",
        }

    def query_group_summary(self, external_id: str, run_id: str) -> dict[str, str]:
        return {
            "status": "confirmed",
            "external_id": external_id,
            "run_id": run_id,
            "url": f"https://fake.feishu.local/message/{run_id}",
        }

    def query_bitable_archive(self, external_id: str, run_id: str) -> dict[str, str]:
        self._archive_query_calls += 1
        if self._archive_query_calls == 1:
            return {
                "status": "not_found",
                "error_class": "resource_not_found",
                "error_summary": "archive is missing after publish",
                "external_id": external_id,
                "run_id": run_id,
            }
        return {
            "status": "confirmed",
            "external_id": external_id,
            "run_id": run_id,
            "url": f"https://fake.feishu.local/archive/{run_id}",
        }


def _make_client(
    provider: FakeEffectProvider,
) -> tuple[TestClient, sessionmaker[Session], WorkflowRuntime, str, str]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    with factory() as session:
        project = Project(name="Demo", timezone="Asia/Shanghai")
        session.add(project)
        session.flush()
        run = RunCreationService(session).create_run(
            project.id,
            "2026-W30",
            date(2026, 7, 20),
            date(2026, 7, 27),
        )
        report_version = ReportVersion(
            run_id=run.id,
            version=1,
            status="verified",
            structured_report={"summary": "ok"},
            structured_hash="structured-hash",
            rendered_content="rendered report",
            content_hash="rendered-hash",
            data_snapshot_hash="snapshot-hash",
            prompt_version_ids=["prompt-v1"],
            model_info={"provider": "fake"},
            confidence=0.95,
            data_quality_status="complete",
            verified_at=datetime.now(UTC),
        )
        session.add(report_version)
        session.commit()

    runtime = WorkflowRuntime(
        factory,
        MemorySaver(),
        publishing_service=PublishingService(factory, effect_provider=provider),
    )
    client = TestClient(
        create_app(
            settings=Settings(_env_file=None, app_profile="local-demo"),
            session_factory=factory,
            workflow_runtime=runtime,
        )
    )
    with factory() as session:
        run_id = session.scalar(select(ReportRun.id).order_by(ReportRun.created_at.desc()))
        report_version_id = session.scalar(
            select(ReportVersion.id).order_by(ReportVersion.created_at.desc())
        )
    assert run_id is not None
    assert report_version_id is not None
    return client, factory, runtime, run_id, report_version_id


def _approve_generation(snapshot: object) -> dict[str, object]:
    values = snapshot.values  # type: ignore[attr-defined]
    approval = values["approval"]
    scope = values["scope"]
    return {
        "action": "approve_generation",
        "challenge_id": approval["challenge_id"],
        "approval_revision": approval["approval_revision"],
        "presented_hash": scope["scope_hash"],
        "actor_id": "local-demo",
    }


def _approve_publish(snapshot: object) -> dict[str, object]:
    values = snapshot.values  # type: ignore[attr-defined]
    approval = values["approval"]
    publish = values["publish"]
    return {
        "action": "approve_publish",
        "challenge_id": approval["challenge_id"],
        "approval_revision": approval["approval_revision"],
        "presented_hash": publish["plan_hash"],
        "actor_id": "local-demo",
    }


def _seed_permanent_failure_state(
    factory: sessionmaker[Session], run_id: str, report_version_id: str
) -> None:
    publishing = PublishingService(factory)
    executor = SideEffectExecutor(factory, effect_provider=FakeEffectProvider())
    plan = publishing.build_publish_plan(run_id, report_version_id)
    assert plan.status == "complete"
    assert plan.publish_plan_ref is not None
    assert plan.plan_hash is not None

    created = executor.create_feishu_document(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    assert created.status == "complete"

    with factory() as session:
        publish_plan = session.get(PublishPlan, plan.publish_plan_ref)
        assert publish_plan is not None
        operation_specs = publish_plan.canonical_plan["operations"]
        report_run = session.get(ReportRun, run_id)
        assert report_run is not None

        publish_plan.status = "partial_failed"
        report_run.status = "partial_failed"
        report_run.current_stage = "partial_failed"
        report_run.current_node = "complete_run"
        report_run.approved_publish_plan_id = publish_plan.id

        operation_two_spec = operation_specs[1]
        operation_two_target = json.dumps(
            operation_two_spec["target"], ensure_ascii=False, sort_keys=True
        )
        operation_two_payload = json.dumps(
            operation_two_spec["payload"], ensure_ascii=False, sort_keys=True
        )
        operation_two = SideEffectOperation(
            id=new_id(),
            publish_plan_id=publish_plan.id,
            run_id=run_id,
            sequence=2,
            operation_type=str(operation_two_spec["type"]),
            target_ref=operation_two_target,
            target_hash=canonical_json_hash(operation_two_spec["target"]),
            payload_ref=operation_two_payload,
            payload_hash=canonical_json_hash(operation_two_spec["payload"]),
            idempotency_key=build_operation_key(
                publish_plan_id=publish_plan.id,
                sequence=2,
                operation_type=str(operation_two_spec["type"]),
                target_hash=canonical_json_hash(operation_two_spec["target"]),
                payload_hash=canonical_json_hash(operation_two_spec["payload"]),
            ),
            status="failed",
            attempt_count=1,
            external_resource_id=None,
            external_url=None,
            provider_request_id=None,
            verification_status="not_checked",
            last_error_class="permission_denied",
            last_error_summary="permission denied",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            version=1,
        )
        session.add(operation_two)
        session.commit()


def test_safe_retry_replays_retryable_failed_operation_without_duplicate_artifacts() -> None:
    provider = PartialFailureVerifierProvider()
    client, factory, runtime, run_id, _ = _make_client(provider)

    first = runtime.start(run_id)
    waiting_publish = runtime.resume(run_id, _approve_generation(first.snapshot))
    finished = runtime.resume(run_id, _approve_publish(waiting_publish.snapshot))

    assert finished.status == "partial_failed"

    response = client.post(
        f"/api/v1/admin/runs/{run_id}/safe-retry",
        json={"reason": "retry archive verification"},
    )

    assert response.status_code == 202

    with factory() as session:
        run = session.get(ReportRun, run_id)
        operations = session.scalars(
            select(SideEffectOperation)
            .where(SideEffectOperation.run_id == run_id)
            .order_by(SideEffectOperation.sequence)
        ).all()
        artifacts = session.scalars(
            select(ReportArtifact).where(ReportArtifact.run_id == run_id)
        ).all()

        assert run is not None
        assert run.status == "completed"
        assert run.current_stage == "succeeded"
        assert [operation.status for operation in operations] == [
            "succeeded",
            "succeeded",
            "succeeded",
        ]
        assert len(artifacts) == 3


def test_safe_retry_rejects_permanent_failure() -> None:
    provider = PartialFailureVerifierProvider()
    client, factory, _, run_id, report_version_id = _make_client(provider)

    _seed_permanent_failure_state(factory, run_id, report_version_id)

    response = client.post(
        f"/api/v1/admin/runs/{run_id}/safe-retry",
        json={"reason": "retry permission failure"},
    )

    assert response.status_code == 409
    with factory() as session:
        run = session.get(ReportRun, run_id)
        assert run is not None
        assert run.status == "partial_failed"
        assert run.current_stage == "partial_failed"
