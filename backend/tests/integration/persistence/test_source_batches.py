from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

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
from app.providers.fake import FakeFeishuProvider, FakeGitHubProvider


def make_service() -> tuple[CollectionService, str, sessionmaker[Session]]:
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
        feishu=FakeFeishuProvider(),
        github=FakeGitHubProvider(),
    )
    return CollectionService(factory, providers), run_id, factory


def test_collection_reuses_identical_batches_and_results() -> None:
    service, run_id, factory = make_service()
    scope = {
        "selected_repository_ids": ["github-repository-example"],
        "feishu_resource_refs": ["feishu-table-example"],
        "mapping_revision": "1",
    }

    feishu_first = service.collect_feishu_data(run_id, scope)
    feishu_second = service.collect_feishu_data(run_id, scope)
    github_first = service.collect_github_data(run_id, scope)
    github_second = service.collect_github_data(run_id, scope)
    snapshot_first = service.normalize_data(run_id, scope)
    snapshot_second = service.normalize_data(run_id, scope)
    validation_first = service.validate_data(run_id, snapshot_first.normalized_snapshot_ref or "")
    validation_second = service.validate_data(run_id, snapshot_first.normalized_snapshot_ref or "")

    assert feishu_first.source_batch_ref == feishu_second.source_batch_ref
    assert github_first.source_batch_ref == github_second.source_batch_ref
    assert snapshot_first.normalized_snapshot_ref == snapshot_second.normalized_snapshot_ref
    assert validation_first.validation_result_ref == validation_second.validation_result_ref

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
        assert len(source_batches) == 2
        assert len(normalized_snapshots) == 1
        assert len(normalized_entities) == 4
        assert len(validation_results) == 1
        assert len(tool_executions) == 4
