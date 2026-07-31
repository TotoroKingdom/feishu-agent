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
from app.providers.fake import FakeEffectProvider
from app.publishing.service import PublishingService
from app.side_effects.executor import SideEffectExecutor, build_operation_key
from tests.admin_auth import authenticate_admin


def _make_client() -> tuple[TestClient, sessionmaker[Session], WorkflowRuntime, str, str]:
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

    runtime = WorkflowRuntime(factory, MemorySaver())
    client = TestClient(
        create_app(
            settings=Settings(_env_file=None, app_profile="local-demo"),
            session_factory=factory,
            workflow_runtime=runtime,
        )
    )
    authenticate_admin(client)
    with factory() as session:
        run_id = session.scalar(select(ReportRun.id).order_by(ReportRun.created_at.desc()))
        report_version_id = session.scalar(
            select(ReportVersion.id).order_by(ReportVersion.created_at.desc())
        )
    assert run_id is not None
    assert report_version_id is not None
    return client, factory, runtime, run_id, report_version_id


def _seed_waiting_run(runtime: WorkflowRuntime, run_id: str) -> None:
    started = runtime.start(run_id)
    assert started.status == "waiting"
    assert started.snapshot.values["current_stage"] == "waiting_confirmation"  # type: ignore[index]


def _seed_publishing_run(
    factory: sessionmaker[Session], run_id: str, report_version_id: str
) -> None:
    publishing = PublishingService(factory)
    executor = SideEffectExecutor(factory, effect_provider=FakeEffectProvider())
    with factory() as session:
        run = session.get(ReportRun, run_id)
        report_version = session.get(ReportVersion, report_version_id)
        assert run is not None
        assert report_version is not None
    plan = publishing.build_publish_plan(run_id, report_version_id)
    assert plan.status == "complete"
    assert plan.publish_plan_ref is not None
    assert plan.plan_hash is not None

    first = executor.create_feishu_document(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    assert first.status == "complete"
    assert first.operation_ref is not None

    with factory() as session:
        publish_plan = session.get(PublishPlan, plan.publish_plan_ref)
        assert publish_plan is not None
        publish_plan.status = "executing"
        run = session.get(ReportRun, run_id)
        assert run is not None
        run.status = "completed"
        run.current_stage = "publishing"
        run.current_node = "send_group_summary"
        run.approved_publish_plan_id = publish_plan.id
        operation_specs = publish_plan.canonical_plan["operations"]
        for sequence in (2, 3):
            operation_spec = operation_specs[sequence - 1]
            operation = SideEffectOperation(
                id=new_id(),
                publish_plan_id=publish_plan.id,
                run_id=run_id,
                sequence=sequence,
                operation_type=str(operation_spec["type"]),
                target_ref=json.dumps(
                    operation_spec["target"],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                target_hash=canonical_json_hash(operation_spec["target"]),
                payload_ref=json.dumps(
                    operation_spec["payload"],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                payload_hash=canonical_json_hash(operation_spec["payload"]),
                idempotency_key=build_operation_key(
                    publish_plan_id=publish_plan.id,
                    sequence=sequence,
                    operation_type=str(operation_spec["type"]),
                    target_hash=canonical_json_hash(operation_spec["target"]),
                    payload_hash=canonical_json_hash(operation_spec["payload"]),
                ),
                status="pending",
                attempt_count=0,
                external_resource_id=None,
                external_url=None,
                provider_request_id=None,
                verification_status="not_checked",
                last_error_class=None,
                last_error_summary=None,
                started_at=None,
                completed_at=None,
                version=1,
            )
            session.add(operation)
        session.commit()

    with factory() as session:
        artifacts = session.scalars(
            select(ReportArtifact).where(ReportArtifact.run_id == run_id)
        ).all()
        operations = session.scalars(
            select(SideEffectOperation)
            .where(SideEffectOperation.run_id == run_id)
            .order_by(SideEffectOperation.sequence)
        ).all()
        assert len(artifacts) == 1
        assert len(operations) == 3


def test_cancel_run_marks_waiting_run_cancelled() -> None:
    client, _, runtime, run_id, _ = _make_client()
    _seed_waiting_run(runtime, run_id)

    response = client.post(
        f"/api/v1/admin/runs/{run_id}/cancel",
        json={"reason": "stop now", "expected_status": "waiting"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["data"]["run_id"] == run_id
    assert payload["data"]["current_stage"] == "cancelled"

    repeat = client.post(
        f"/api/v1/admin/runs/{run_id}/cancel",
        json={"reason": "stop now", "expected_status": "cancelled"},
    )

    assert repeat.status_code == 202
    assert repeat.json()["data"]["current_stage"] == "cancelled"


def test_cancel_run_cancels_pending_publish_operations() -> None:
    client, factory, runtime, run_id, report_version_id = _make_client()
    _seed_publishing_run(factory, run_id, report_version_id)

    response = client.post(
        f"/api/v1/admin/runs/{run_id}/cancel",
        json={"reason": "stop publish", "expected_status": "completed"},
    )

    assert response.status_code == 202

    with factory() as session:
        run = session.get(ReportRun, run_id)
        publish_plan = session.scalar(select(PublishPlan).where(PublishPlan.run_id == run_id))
        operations = session.scalars(
            select(SideEffectOperation)
            .where(SideEffectOperation.run_id == run_id)
            .order_by(SideEffectOperation.sequence)
        ).all()

        assert run is not None
        assert run.status == "cancelled"
        assert run.current_stage == "cancelled"
        assert publish_plan is not None
        assert publish_plan.status == "cancelled"
        assert [operation.status for operation in operations] == [
            "succeeded",
            "cancelled",
            "cancelled",
        ]
