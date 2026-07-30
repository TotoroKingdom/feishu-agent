from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    Base,
    Project,
    ReportArtifact,
    ReportVersion,
    SideEffectOperation,
)
from app.domain.runs import RunCreationService
from app.providers.fake import FakeEffectProvider, FakeScenario
from app.publishing.service import PublishingService
from app.side_effects.executor import SideEffectExecutor


def _make_factory() -> tuple[sessionmaker[Session], str, str]:
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
        return factory, run.id, report_version.id


def test_publish_operations_enforce_dependencies_and_persist_artifacts() -> None:
    factory, run_id, report_version_id = _make_factory()
    publishing = PublishingService(factory)
    plan = publishing.build_publish_plan(run_id, report_version_id)
    assert plan.status == "complete"
    assert plan.publish_plan_ref is not None
    assert plan.plan_hash is not None

    executor = SideEffectExecutor(factory)

    summary_before = executor.send_group_summary(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    assert summary_before.status == "blocked"
    assert summary_before.error_code == "SIDE_EFFECT_DEPENDENCY_MISSING"
    assert summary_before.current_node == "send_group_summary"

    created = executor.create_feishu_document(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    assert created.status == "complete"
    assert created.operation_ref is not None
    assert created.artifact_ref is not None
    assert created.external_id == f"fake-document-{report_version_id}"
    assert created.external_url == f"https://fake.feishu.local/doc/{report_version_id}"

    archive_before = executor.archive_report_record(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    assert archive_before.status == "blocked"
    assert archive_before.error_code == "SIDE_EFFECT_DEPENDENCY_MISSING"
    assert archive_before.current_node == "upsert_bitable_archive"

    summary = executor.send_group_summary(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    assert summary.status == "complete"
    assert summary.operation_ref is not None
    assert summary.artifact_ref is not None
    assert summary.external_id == f"fake-message-{run_id}"
    assert summary.external_url == f"https://fake.feishu.local/message/{run_id}"

    archive = executor.archive_report_record(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    assert archive.status == "complete"
    assert archive.operation_ref is not None
    assert archive.artifact_ref is not None
    assert archive.external_id == f"fake-archive-{run_id}"
    assert archive.external_url == f"https://fake.feishu.local/archive/{run_id}"

    verified = executor.verify_side_effects(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    assert verified.status == "complete"
    assert verified.current_node == "complete_run"
    assert verified.side_effect_status == "verified"

    with factory() as session:
        operations = session.scalars(
            select(SideEffectOperation)
            .where(SideEffectOperation.run_id == run_id)
            .order_by(SideEffectOperation.sequence)
        ).all()
        artifacts = session.scalars(
            select(ReportArtifact)
            .join(SideEffectOperation)
            .where(SideEffectOperation.run_id == run_id)
            .order_by(SideEffectOperation.sequence)
        ).all()

        assert [operation.status for operation in operations] == [
            "succeeded",
            "succeeded",
            "succeeded",
        ]
        assert [artifact.artifact_type for artifact in artifacts] == [
            "feishu_document",
            "group_message",
            "bitable_archive",
        ]
        assert [artifact.external_id for artifact in artifacts] == [
            f"fake-document-{report_version_id}",
            f"fake-message-{run_id}",
            f"fake-archive-{run_id}",
        ]
        assert [artifact.url for artifact in artifacts] == [
            f"https://fake.feishu.local/doc/{report_version_id}",
            f"https://fake.feishu.local/message/{run_id}",
            f"https://fake.feishu.local/archive/{run_id}",
        ]
        assert all(artifact.content_hash for artifact in artifacts)
        assert all(artifact.verified_at is not None for artifact in artifacts)


def test_publish_operation_failures_are_blocked_and_do_not_unblock_following_steps() -> None:
    factory, run_id, report_version_id = _make_factory()
    publishing = PublishingService(factory)
    plan = publishing.build_publish_plan(run_id, report_version_id)
    assert plan.status == "complete"
    assert plan.publish_plan_ref is not None
    assert plan.plan_hash is not None

    class FailingSummaryProvider(FakeEffectProvider):
        def __init__(self) -> None:
            super().__init__(FakeScenario.HAPPY)

        def send_group_summary(self, run_id: str) -> dict[str, str]:
            return {
                "status": "failed",
                "external_id": f"fake-message-{run_id}",
                "url": f"https://fake.feishu.local/message/{run_id}",
                "error_class": "message_send_failed",
                "error_summary": "message delivery failed",
            }

    executor = SideEffectExecutor(factory, effect_provider=FailingSummaryProvider())
    created = executor.create_feishu_document(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    assert created.status == "complete"

    failed_summary = executor.send_group_summary(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    assert failed_summary.status == "blocked"
    assert failed_summary.error_code == "SIDE_EFFECT_OPERATION_FAILED"
    assert failed_summary.current_stage == "blocked"
    assert failed_summary.current_node == "archive_report_record"

    blocked_archive = executor.archive_report_record(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    assert blocked_archive.status == "blocked"
    assert blocked_archive.error_code == "SIDE_EFFECT_DEPENDENCY_INCOMPLETE"

    with factory() as session:
        operations = session.scalars(
            select(SideEffectOperation)
            .where(SideEffectOperation.run_id == run_id)
            .order_by(SideEffectOperation.sequence)
        ).all()
        assert [operation.status for operation in operations] == ["succeeded", "failed"]
