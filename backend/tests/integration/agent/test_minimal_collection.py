from __future__ import annotations

from datetime import date

from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.runtime import WorkflowRuntime
from app.collection.service import CollectionProviders, CollectionService
from app.db.models import (
    Base,
    NormalizedEntity,
    NormalizedSnapshot,
    Project,
    ReportRun,
    SourceDataBatch,
    ToolExecution,
    ValidationResult,
)
from app.domain.runs import RunCreationService
from app.providers.fake import FakeFeishuProvider, FakeGitHubProvider, FakeScenario


def make_runtime(
    feishu_scenario: FakeScenario = FakeScenario.HAPPY,
    github_scenario: FakeScenario = FakeScenario.HAPPY,
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
    providers = CollectionProviders(
        feishu=FakeFeishuProvider(feishu_scenario),
        github=FakeGitHubProvider(github_scenario),
    )
    collection_service = CollectionService(factory, providers)
    runtime = WorkflowRuntime(factory, MemorySaver(), collection_service=collection_service)
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


def test_happy_path_collects_normalizes_and_validates() -> None:
    runtime, run_id, factory = make_runtime()

    started = runtime.start(run_id)
    result = runtime.resume(run_id, _approval_payload(started.snapshot, "approve_generation"))
    snapshot = result.snapshot

    assert started.status == "waiting"
    assert result.status == "completed"
    assert snapshot.values["current_stage"] == "validated"  # type: ignore[index]
    assert snapshot.values["current_node"] == "complete_run"  # type: ignore[index]
    assert isinstance(snapshot.values["source_batch_refs"], list)
    assert len(snapshot.values["source_batch_refs"]) == 2
    assert snapshot.values["normalized_snapshot_ref"]  # type: ignore[index]
    assert snapshot.values["validation_result_ref"]  # type: ignore[index]

    with factory() as session:
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        source_batches = session.scalars(
            select(SourceDataBatch).where(SourceDataBatch.run_id == run_id)
        ).all()
        normalized_snapshots = session.scalars(
            select(NormalizedSnapshot).where(NormalizedSnapshot.run_id == run_id)
        ).all()
        normalized_entities = session.scalars(
            select(NormalizedEntity).where(NormalizedEntity.run_id == run_id)
        ).all()
        validation_results = session.scalars(
            select(ValidationResult).where(ValidationResult.run_id == run_id)
        ).all()
        tool_executions = session.scalars(
            select(ToolExecution).where(ToolExecution.run_id == run_id)
        ).all()

        assert run_row is not None
        assert run_row.status == "completed"
        assert run_row.current_stage == "validated"
        assert len(source_batches) == 2
        assert {batch.fetch_status for batch in source_batches} == {"complete"}
        assert len(normalized_snapshots) == 1
        assert normalized_snapshots[0].entity_count == 4
        assert len(normalized_entities) == 4
        assert len(validation_results) == 1
        assert validation_results[0].validation_pass is True
        assert validation_results[0].data_quality_status == "complete"
        assert len(tool_executions) == 4


def test_failed_source_batch_blocks_the_run() -> None:
    runtime, run_id, factory = make_runtime(feishu_scenario=FakeScenario.PARTIAL_FAILURE)

    started = runtime.start(run_id)
    result = runtime.resume(run_id, _approval_payload(started.snapshot, "approve_generation"))
    snapshot = result.snapshot

    assert started.status == "waiting"
    assert result.status == "blocked"
    assert snapshot.values["current_stage"] == "blocked"  # type: ignore[index]
    assert snapshot.values["current_node"] == "collect_feishu_data"  # type: ignore[index]
    assert snapshot.values["error_code"] == "FEISHU_FETCH_FAILED"  # type: ignore[index]
    assert isinstance(snapshot.values["source_batch_refs"], list)
    assert len(snapshot.values["source_batch_refs"]) == 1
    assert snapshot.values["normalized_snapshot_ref"] is None  # type: ignore[index]
    assert snapshot.values["validation_result_ref"] is None  # type: ignore[index]

    with factory() as session:
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        source_batches = session.scalars(
            select(SourceDataBatch).where(SourceDataBatch.run_id == run_id)
        ).all()
        normalized_snapshots = session.scalars(
            select(NormalizedSnapshot).where(NormalizedSnapshot.run_id == run_id)
        ).all()
        validation_results = session.scalars(
            select(ValidationResult).where(ValidationResult.run_id == run_id)
        ).all()
        tool_executions = session.scalars(
            select(ToolExecution).where(ToolExecution.run_id == run_id)
        ).all()

        assert run_row is not None
        assert run_row.status == "blocked"
        assert run_row.current_stage == "blocked"
        assert len(source_batches) == 1
        assert len(normalized_snapshots) == 0
        assert len(validation_results) == 0
        assert len(tool_executions) == 1
