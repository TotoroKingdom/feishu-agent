from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Project, ReportVersion, SideEffectOperation
from app.domain.runs import RunCreationService
from app.providers.fake import FakeEffectProvider, FakeScenario
from app.publishing.service import PublishingService
from app.side_effects.executor import SideEffectExecutor
from app.side_effects.verifier import SideEffectVerifier


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


class ConfirmedQueryProvider:
    def query_feishu_document(self, external_id: str, run_id: str) -> dict[str, str]:
        return {
            "status": "confirmed",
            "external_id": external_id,
            "run_id": run_id,
            "url": f"https://fake.feishu.local/doc/{run_id}",
        }


class NotFoundQueryProvider:
    def query_feishu_document(self, external_id: str, run_id: str) -> dict[str, str]:
        return {
            "status": "not_found",
            "error_class": "resource_not_found",
            "external_id": external_id,
            "run_id": run_id,
        }


class TimeoutThenConfirmedQueryProvider:
    def __init__(self) -> None:
        self._calls = 0

    def query_feishu_document(self, external_id: str, run_id: str) -> dict[str, str]:
        self._calls += 1
        if self._calls == 1:
            return {
                "status": "unknown",
                "error_class": "timeout",
                "error_summary": "verification timed out",
                "external_id": external_id,
                "run_id": run_id,
            }
        return {
            "status": "confirmed",
            "external_id": external_id,
            "run_id": run_id,
            "url": f"https://fake.feishu.local/doc/{run_id}",
        }


class NoQueryProvider:
    pass


@pytest.mark.parametrize(
    ("provider", "expected_status", "expected_verification_status", "expected_operation_status"),
    [
        (ConfirmedQueryProvider(), "confirmed", "confirmed", "succeeded"),
        (NotFoundQueryProvider(), "not_found", "not_found", "unknown"),
    ],
)
def test_verifier_maps_query_results_to_operation_state(
    provider: object,
    expected_status: str,
    expected_verification_status: str,
    expected_operation_status: str,
) -> None:
    factory, run_id, report_version_id = _make_factory()
    publishing = PublishingService(factory)
    plan = publishing.build_publish_plan(run_id, report_version_id)
    assert plan.status == "complete"
    assert plan.publish_plan_ref is not None
    assert plan.plan_hash is not None

    executor = SideEffectExecutor(factory, effect_provider=FakeEffectProvider(FakeScenario.HAPPY))
    created = executor.create_feishu_document(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    assert created.status == "complete"
    assert created.operation_ref is not None

    verifier = SideEffectVerifier(factory, effect_provider=provider)
    outcome = verifier.verify(operation_id=created.operation_ref)

    assert outcome.status == expected_status

    with factory() as session:
        operation = session.get(SideEffectOperation, created.operation_ref)
        assert operation is not None
        assert operation.status == expected_operation_status
        assert operation.verification_status == expected_verification_status


def test_verifier_treats_timeout_as_inconclusive_and_allows_retry() -> None:
    factory, run_id, report_version_id = _make_factory()
    publishing = PublishingService(factory)
    plan = publishing.build_publish_plan(run_id, report_version_id)
    assert plan.status == "complete"
    assert plan.publish_plan_ref is not None
    assert plan.plan_hash is not None

    executor = SideEffectExecutor(factory, effect_provider=FakeEffectProvider(FakeScenario.HAPPY))
    created = executor.create_feishu_document(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    assert created.status == "complete"
    assert created.operation_ref is not None

    provider = TimeoutThenConfirmedQueryProvider()
    verifier = SideEffectVerifier(factory, effect_provider=provider)

    first = verifier.verify(operation_id=created.operation_ref)
    assert first.status == "inconclusive"

    second = verifier.verify(operation_id=created.operation_ref)
    assert second.status == "confirmed"

    with factory() as session:
        operation = session.get(SideEffectOperation, created.operation_ref)
        assert operation is not None
        assert operation.status == "succeeded"
        assert operation.verification_status == "confirmed"


def test_verifier_returns_inconclusive_when_query_capability_is_missing() -> None:
    factory, run_id, report_version_id = _make_factory()
    publishing = PublishingService(factory)
    plan = publishing.build_publish_plan(run_id, report_version_id)
    assert plan.status == "complete"
    assert plan.publish_plan_ref is not None
    assert plan.plan_hash is not None

    executor = SideEffectExecutor(factory, effect_provider=FakeEffectProvider(FakeScenario.HAPPY))
    created = executor.create_feishu_document(
        run_id=run_id,
        publish_plan_ref=plan.publish_plan_ref,
        approved_plan_hash=plan.plan_hash,
    )
    assert created.status == "complete"
    assert created.operation_ref is not None

    verifier = SideEffectVerifier(factory, effect_provider=NoQueryProvider())
    outcome = verifier.verify(operation_id=created.operation_ref)

    assert outcome.status == "inconclusive"

    with factory() as session:
        operation = session.get(SideEffectOperation, created.operation_ref)
        assert operation is not None
        assert operation.status == "unknown"
        assert operation.verification_status == "inconclusive"
