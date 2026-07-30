from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.approvals import canonical_json_hash
from app.db.models import (
    Base,
    Project,
    ReportArtifact,
    ReportVersion,
    SideEffectAttempt,
    SideEffectOperation,
    new_id,
)
from app.domain.runs import RunCreationService
from app.providers.fake import FakeEffectProvider, FakeScenario
from app.publishing.service import PublishingService
from app.side_effects.executor import SideEffectExecutor, build_operation_key


def _make_factory(tmp_path) -> tuple[sessionmaker[Session], str, str]:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'claims.sqlite3'}",
        connect_args={"check_same_thread": False},
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
        return factory, run.id, report_version.id


class CountingEffectProvider(FakeEffectProvider):
    def __init__(self) -> None:
        super().__init__(FakeScenario.HAPPY)
        self.calls = 0

    def create_feishu_document(self, report_id: str) -> dict[str, str]:
        self.calls += 1
        return super().create_feishu_document(report_id)


class BlockingEffectProvider(CountingEffectProvider):
    def __init__(self, started: threading.Event, release: threading.Event) -> None:
        super().__init__()
        self.started = started
        self.release = release

    def create_feishu_document(self, report_id: str) -> dict[str, str]:
        self.started.set()
        self.release.wait(5)
        return super().create_feishu_document(report_id)


def test_expired_running_operation_is_reclaimed_and_deduplicated(tmp_path) -> None:
    factory, run_id, report_version_id = _make_factory(tmp_path)
    publishing = PublishingService(factory)
    plan = publishing.build_publish_plan(run_id, report_version_id)
    assert plan.status == "complete"
    assert plan.publish_plan_ref is not None
    assert plan.plan_hash is not None

    with factory() as session:
        operation_spec = {
            "sequence": 1,
            "type": "create_feishu_document",
            "target": {
                "publish_group_ref": "feishu-publish-group-example",
                "report_version_ref": report_version_id,
            },
            "payload": {
                "rendered_report_ref": report_version_id,
                "rendered_content_hash": "rendered-hash",
            },
        }
        stale_started_at = datetime.now(UTC) - timedelta(hours=2)
        operation = SideEffectOperation(
            id=new_id(),
            publish_plan_id=plan.publish_plan_ref,
            run_id=run_id,
            sequence=1,
            operation_type="create_feishu_document",
            target_ref=str(operation_spec["target"]),
            target_hash=canonical_json_hash(operation_spec["target"]),
            payload_ref=str(operation_spec["payload"]),
            payload_hash=canonical_json_hash(operation_spec["payload"]),
            idempotency_key=build_operation_key(
                publish_plan_id=plan.publish_plan_ref,
                sequence=1,
                operation_type="create_feishu_document",
                target_hash=canonical_json_hash(operation_spec["target"]),
                payload_hash=canonical_json_hash(operation_spec["payload"]),
            ),
            status="running",
            attempt_count=1,
            external_resource_id=None,
            external_url=None,
            provider_request_id=None,
            verification_status="not_checked",
            last_error_class=None,
            last_error_summary=None,
            started_at=stale_started_at,
            completed_at=None,
            updated_at=stale_started_at,
            version=1,
        )
        session.add(operation)
        session.add(
            SideEffectAttempt(
                id=new_id(),
                operation_id=operation.id,
                attempt=1,
                status="started",
                request_summary={
                    "publish_plan_ref": plan.publish_plan_ref,
                    "run_id": run_id,
                    "sequence": 1,
                    "operation_type": "create_feishu_document",
                },
                provider_request_id=None,
                response_summary={},
                error_class=None,
                started_at=stale_started_at,
                ended_at=None,
            )
        )
        session.commit()

    provider = CountingEffectProvider()
    executor = SideEffectExecutor(factory, effect_provider=provider)

    first_result = executor.create_feishu_document(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    second_result = executor.create_feishu_document(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )

    assert provider.calls == 1
    assert first_result.status == "complete"
    assert second_result.status == "complete"
    assert first_result.operation_ref == second_result.operation_ref
    assert first_result.artifact_ref == second_result.artifact_ref

    with factory() as session:
        operations = session.scalars(
            select(SideEffectOperation)
            .where(SideEffectOperation.run_id == run_id)
            .order_by(SideEffectOperation.sequence)
        ).all()
        attempts = session.scalars(
            select(SideEffectAttempt)
            .join(SideEffectOperation)
            .where(SideEffectOperation.run_id == run_id)
            .order_by(SideEffectAttempt.attempt)
        ).all()
        artifacts = session.scalars(
            select(ReportArtifact)
            .join(SideEffectOperation)
            .where(SideEffectOperation.run_id == run_id)
            .order_by(SideEffectOperation.sequence)
        ).all()

        assert len(operations) == 1
        assert operations[0].status == "succeeded"
        assert operations[0].attempt_count == 2
        assert len(attempts) == 2
        assert [attempt.status for attempt in attempts] == ["started", "succeeded"]
        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == "feishu_document"


def test_active_running_operation_blocks_a_second_claim(tmp_path) -> None:
    factory, run_id, report_version_id = _make_factory(tmp_path)
    publishing = PublishingService(factory)
    plan = publishing.build_publish_plan(run_id, report_version_id)
    assert plan.status == "complete"
    assert plan.publish_plan_ref is not None
    assert plan.plan_hash is not None

    started = threading.Event()
    release = threading.Event()
    provider = BlockingEffectProvider(started, release)
    executor = SideEffectExecutor(factory, effect_provider=provider)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(
            executor.create_feishu_document,
            run_id=run_id,
            publish_plan_ref=plan.publish_plan_ref,
            approved_plan_hash=plan.plan_hash,
        )
        assert started.wait(5)

        second_future = pool.submit(
            executor.create_feishu_document,
            run_id=run_id,
            publish_plan_ref=plan.publish_plan_ref,
            approved_plan_hash=plan.plan_hash,
        )
        second_result = second_future.result(timeout=5)
        release.set()
        first_result = first_future.result(timeout=5)

    assert provider.calls == 1
    assert first_result.status == "complete"
    assert second_result.status == "blocked"
    assert second_result.error_code == "SIDE_EFFECT_OPERATION_IN_PROGRESS"

    with factory() as session:
        attempts = session.scalars(
            select(SideEffectAttempt)
            .join(SideEffectOperation)
            .where(SideEffectOperation.run_id == run_id)
            .order_by(SideEffectAttempt.attempt)
        ).all()

        assert len(attempts) == 1
        assert attempts[0].status == "succeeded"
