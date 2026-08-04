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
    SideEffectAttempt,
    SideEffectOperation,
)
from app.domain.runs import RunCreationService
from app.publishing.service import PublishingService
from app.side_effects.executor import SideEffectExecutor


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
        return factory, run.id, report_version.id, project.id


def test_side_effect_executor_is_idempotent_for_repeated_document_creation() -> None:
    factory, run_id, report_version_id, _ = _make_factory()
    publishing = PublishingService(factory)
    plan = publishing.build_publish_plan(run_id, report_version_id)
    assert plan.status == "complete"
    assert plan.publish_plan_ref is not None
    assert plan.plan_hash is not None

    executor = SideEffectExecutor(factory)
    first = executor.create_feishu_document(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    second = executor.create_feishu_document(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )

    assert first.status == "complete"
    assert second.status == "complete"
    assert first.operation_ref == second.operation_ref
    assert first.artifact_ref == second.artifact_ref

    with factory() as session:
        operations = session.scalars(select(SideEffectOperation)).all()
        attempts = session.scalars(select(SideEffectAttempt)).all()
        artifacts = session.scalars(select(ReportArtifact)).all()

        assert len(operations) == 1
        assert operations[0].status == "succeeded"
        assert len(attempts) == 1
        assert attempts[0].status == "succeeded"
        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == "feishu_document"


def test_side_effect_executor_runs_all_publish_operations_in_order() -> None:
    factory, run_id, report_version_id, _ = _make_factory()
    publishing = PublishingService(factory)
    plan = publishing.build_publish_plan(run_id, report_version_id)
    assert plan.status == "complete"
    assert plan.publish_plan_ref is not None
    assert plan.plan_hash is not None

    executor = SideEffectExecutor(factory)
    first = executor.create_feishu_document(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    second = executor.send_group_summary(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    third = executor.archive_report_record(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    verified = executor.verify_side_effects(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )

    assert first.status == "complete"
    assert second.status == "complete"
    assert third.status == "complete"
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

        assert [operation.sequence for operation in operations] == [1, 2, 3]
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
        assert all(artifact.verified_at is not None for artifact in artifacts)
