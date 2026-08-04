from __future__ import annotations

from datetime import UTC, date, datetime

from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.runtime import WorkflowRuntime
from app.collection.service import CollectionProviders, CollectionService, CollectionStageOutcome
from app.db.models import (
    Base,
    DiagnosisRecord,
    NormalizedSnapshot,
    Project,
    ReportRun,
    ValidationResult,
    new_id,
)
from app.domain.runs import RunCreationService
from app.providers.fake import FakeFeishuProvider, FakeGitHubProvider, FakeScenario
from app.reporting.service import ReportingService, ReportStageOutcome


class FlakyGitHubCollectionService(CollectionService):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        super().__init__(
            session_factory,
            CollectionProviders(
                feishu=FakeFeishuProvider(FakeScenario.HAPPY),
                github=FakeGitHubProvider(FakeScenario.HAPPY),
            ),
        )
        self._github_attempts = 0

    def collect_github_data(self, run_id: str, scope: dict[str, object]) -> CollectionStageOutcome:
        self._github_attempts += 1
        if self._github_attempts == 1:
            return CollectionStageOutcome(
                status="blocked",
                error_code="GITHUB_TIMEOUT",
                error_summary="github timeout",
            )
        return super().collect_github_data(run_id, scope)


class NonKeyValidationCollectionService(CollectionService):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        super().__init__(
            session_factory,
            CollectionProviders(
                feishu=FakeFeishuProvider(FakeScenario.HAPPY),
                github=FakeGitHubProvider(FakeScenario.HAPPY),
            ),
        )

    def validate_data(self, run_id: str, normalized_snapshot_id: str) -> CollectionStageOutcome:
        with self._session_factory() as session:
            snapshot = session.get(NormalizedSnapshot, normalized_snapshot_id)
            if snapshot is None:
                raise ValueError("normalized snapshot missing")
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
                    rule_set_version="diagnostic-test.v1",
                    critical_count=0,
                    warning_count=1,
                    missing_items=["optional_field"],
                    conflicts=[],
                    warnings=["optional field is missing"],
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
            error_code="MISSING_NON_KEY_FIELD",
            error_summary="optional field is missing",
            validation_result_ref=validation_result_id,
        )


class FlakyReportingService(ReportingService):
    def __init__(self, session_factory: sessionmaker[Session], *, error_code: str) -> None:
        super().__init__(session_factory)
        self._error_code = error_code
        self._attempts = 0

    def generate_structured_report(
        self,
        run_id: str,
        evidence_set_id: str,
        *,
        force_new_version: bool = False,
    ) -> ReportStageOutcome:
        self._attempts += 1
        if self._attempts == 1 or self._error_code == "REPORT_TIMEOUT":
            if self._error_code == "REPORT_TIMEOUT" or self._attempts == 1:
                return ReportStageOutcome(
                    status="blocked",
                    error_code=self._error_code,
                    error_summary=f"{self._error_code.lower()} on attempt {self._attempts}",
                )
        return super().generate_structured_report(
            run_id,
            evidence_set_id,
            force_new_version=force_new_version,
        )


def _make_runtime(
    *,
    collection_service_factory: type[CollectionService] | None = None,
    reporting_service_factory: type[ReportingService] | None = None,
) -> tuple[WorkflowRuntime, str, sessionmaker[Session]]:
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
    collection_service = (
        collection_service_factory(factory) if collection_service_factory is not None else None
    )
    reporting_service = (
        reporting_service_factory(factory) if reporting_service_factory is not None else None
    )
    runtime = WorkflowRuntime(
        factory,
        MemorySaver(),
        collection_service=collection_service,
        reporting_service=reporting_service,
    )
    return runtime, run_id, factory


def _approval_payload(snapshot: object, action: str) -> dict[str, object]:
    values = snapshot.values  # type: ignore[attr-defined]
    approval = values["approval"]
    scope = values["scope"]
    return {
        "action": action,
        "challenge_id": approval["challenge_id"],
        "approval_revision": approval["approval_revision"],
        "presented_hash": scope["scope_hash"],
        "actor_id": "local-demo",
    }


def _run_to_publish_or_finish(runtime: WorkflowRuntime, run_id: str) -> object:
    started = runtime.start(run_id)
    return runtime.resume(run_id, _approval_payload(started.snapshot, "approve_generation"))


def test_single_repo_timeout_is_retried_and_completes() -> None:
    runtime, run_id, factory = _make_runtime(
        collection_service_factory=FlakyGitHubCollectionService,
    )

    result = _run_to_publish_or_finish(runtime, run_id)
    snapshot = result.snapshot

    assert result.status == "waiting"
    assert snapshot.values["current_stage"] == "waiting_publish_approval"  # type: ignore[index]
    assert snapshot.values["diagnosis"]["retry_counters"]["collect_github_data:timeout"] == 1  # type: ignore[index]
    assert len(snapshot.values["diagnosis"]["diagnosis_record_refs"]) == 1  # type: ignore[index]

    with factory() as session:
        records = session.scalars(
            select(DiagnosisRecord).where(DiagnosisRecord.run_id == run_id)
        ).all()
        assert len(records) == 1
        assert records[0].planned_action == "retry_current_node"
        run = session.get(ReportRun, run_id)
        assert run is not None
        assert run.status == "waiting"


def test_non_key_validation_issue_degrades_and_completes() -> None:
    runtime, run_id, factory = _make_runtime(
        collection_service_factory=NonKeyValidationCollectionService,
    )

    started = runtime.start(run_id)
    result = runtime.resume(run_id, _approval_payload(started.snapshot, "approve_generation"))

    assert result.status == "waiting"
    assert result.snapshot.values["diagnosis"]["retry_counters"]["validate_data:missing"] == 1  # type: ignore[index]
    assert result.snapshot.values["diagnosis"]["next_repair_action"] == "degrade_and_continue"  # type: ignore[index]

    with factory() as session:
        records = session.scalars(
            select(DiagnosisRecord).where(DiagnosisRecord.run_id == run_id)
        ).all()
        assert len(records) == 1
        assert records[0].planned_action == "degrade_and_continue"


def test_unknown_error_falls_back_to_blocked() -> None:
    def reporting_factory(session_factory: sessionmaker[Session]) -> FlakyReportingService:
        return FlakyReportingService(session_factory, error_code="TOTALLY_UNKNOWN")

    runtime, run_id, factory = _make_runtime(
        reporting_service_factory=reporting_factory,
    )

    started = runtime.start(run_id)
    result = runtime.resume(run_id, _approval_payload(started.snapshot, "approve_generation"))

    assert result.status == "blocked"
    assert result.snapshot.values["error_code"] == "TOTALLY_UNKNOWN"  # type: ignore[index]
    assert (
        result.snapshot.values["diagnosis"]["retry_counters"]["generate_structured_report:unknown"]
        == 1
    )  # type: ignore[index]

    with factory() as session:
        records = session.scalars(
            select(DiagnosisRecord).where(DiagnosisRecord.run_id == run_id)
        ).all()
        assert len(records) == 1
        assert records[0].planned_action == "abort_run"


def test_retry_budget_stops_after_three_attempts() -> None:
    def reporting_factory(session_factory: sessionmaker[Session]) -> FlakyReportingService:
        return FlakyReportingService(session_factory, error_code="REPORT_TIMEOUT")

    runtime, run_id, factory = _make_runtime(
        reporting_service_factory=reporting_factory,
    )

    started = runtime.start(run_id)
    result = runtime.resume(run_id, _approval_payload(started.snapshot, "approve_generation"))

    assert result.status == "blocked"
    assert (
        result.snapshot.values["diagnosis"]["retry_counters"]["generate_structured_report:timeout"]
        == 3
    )  # type: ignore[index]
    assert len(result.snapshot.values["diagnosis"]["diagnosis_record_refs"]) == 3  # type: ignore[index]

    with factory() as session:
        records = session.scalars(
            select(DiagnosisRecord).where(DiagnosisRecord.run_id == run_id)
        ).all()
        assert len(records) == 3
        assert records[-1].planned_action == "abort_run"
