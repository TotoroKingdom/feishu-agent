from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.runtime import WorkflowWorker
from app.db.models import Base, Project, ReportVersion, SideEffectOperation
from app.domain.runs import RunCreationService
from app.publishing.service import PublishingService
from app.runtime.leases import RunLeaseConflictError, RunLeaseService


def _make_factory() -> tuple[sessionmaker[Session], str, str, str]:
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
            datetime(2026, 7, 20, tzinfo=UTC).date(),
            datetime(2026, 7, 27, tzinfo=UTC).date(),
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
        return factory, project.id, run.id, report_version.id


def test_run_lease_blocks_second_worker_until_expiry_and_advances_fencing_token() -> None:
    factory, project_id, run_id, report_version_id = _make_factory()
    lease_service = RunLeaseService(factory, lease_seconds=30, operation_lease_seconds=30)
    worker_a = "worker-a"
    worker_b = "worker-b"
    started_at = datetime(2026, 7, 31, 10, 0, tzinfo=UTC)

    acquired = lease_service.acquire_run_lease(run_id, worker_id=worker_a, now=started_at)
    assert acquired.lease_owner == worker_a
    assert acquired.version == 2
    assert acquired.lease_expires_at == started_at + timedelta(seconds=30)

    heartbeat = lease_service.heartbeat_run_lease(
        run_id, worker_id=worker_a, now=started_at + timedelta(seconds=10)
    )
    assert heartbeat.version == 3
    assert heartbeat.lease_expires_at == started_at + timedelta(seconds=40)

    with pytest.raises(RunLeaseConflictError):
        lease_service.acquire_run_lease(
            run_id,
            worker_id=worker_b,
            now=started_at + timedelta(seconds=11),
        )

    expired = lease_service.recover_expired_run_ids(now=started_at + timedelta(seconds=45))
    assert expired == [run_id]

    reclaimed = lease_service.acquire_run_lease(
        run_id,
        worker_id=worker_b,
        now=started_at + timedelta(seconds=45),
    )
    assert reclaimed.lease_owner == worker_b
    assert reclaimed.version == 4

    worker = WorkflowWorker(factory, worker_id="worker-c")
    assert worker.recover_expired_run_ids(now=started_at + timedelta(seconds=45)) == []

    publishing = PublishingService(factory)
    plan = publishing.build_publish_plan(run_id, report_version_id)
    assert plan.status == "complete"
    assert plan.publish_plan_ref is not None
    assert plan.plan_hash is not None

    with factory() as session:
        operation = SideEffectOperation(
            id="op-lease",
            publish_plan_id=plan.publish_plan_ref,
            run_id=run_id,
            sequence=1,
            operation_type="create_feishu_document",
            target_ref="target-ref",
            target_hash="target-hash",
            payload_ref="payload-ref",
            payload_hash="payload-hash",
            idempotency_key="op-lease-key",
            status="running",
            attempt_count=1,
            external_resource_id=None,
            external_url=None,
            provider_request_id=None,
            verification_status="not_checked",
            last_error_class=None,
            last_error_summary=None,
            lease_owner=worker_a,
            lease_expires_at=started_at + timedelta(seconds=30),
            heartbeat_at=started_at,
            started_at=started_at,
            completed_at=None,
            updated_at=started_at,
            version=1,
        )
        session.add(operation)
        session.commit()

    operation_snapshot = lease_service.heartbeat_operation_lease(
        "op-lease",
        worker_id=worker_a,
        now=started_at + timedelta(seconds=12),
    )
    assert operation_snapshot.version == 2
    assert operation_snapshot.lease_expires_at == started_at + timedelta(seconds=42)
    with pytest.raises(RunLeaseConflictError):
        lease_service.heartbeat_operation_lease(
            "op-lease",
            worker_id=worker_b,
            now=started_at + timedelta(seconds=12),
        )

    stale_operations = lease_service.recover_expired_operation_ids(
        now=started_at + timedelta(seconds=50)
    )
    assert stale_operations == ["op-lease"]
