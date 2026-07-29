from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.collection.service import CollectionProviders, CollectionService
from app.db.models import Base, Project, ReportRun, SourceDataBatch, ToolExecution
from app.domain.runs import RunCreationService
from app.providers.fake import FakeGitHubProvider
from app.providers.feishu.bitable import (
    FeishuBitableFieldMapping,
    FeishuBitableMissingFieldError,
    FeishuBitableReader,
    FeishuBitableRecordLimitError,
    FeishuBitableTypeChangedError,
)

RESOURCE_ID = "feishu-table-example"


@dataclass(slots=True)
class FakeBitableClient:
    schema_by_resource: dict[str, dict[str, object]]
    pages_by_resource: dict[str, list[list[dict[str, object]]]]

    def get_table_schema(self, resource_id: str) -> dict[str, object]:
        return self.schema_by_resource[resource_id]

    def list_records(
        self, resource_id: str, *, page_token: str | None = None, page_size: int = 500
    ) -> dict[str, object]:
        pages = self.pages_by_resource[resource_id]
        index = int(page_token) if page_token is not None else 0
        items = pages[index]
        next_index = index + 1
        has_more = next_index < len(pages)
        return {
            "items": items,
            "has_more": has_more,
            "next_page_token": str(next_index) if has_more else None,
            "page_size": page_size,
        }


def test_bitable_reader_paginates_and_converts_supported_fields() -> None:
    client = FakeBitableClient(
        schema_by_resource={
            RESOURCE_ID: {
                "fields": [
                    {"id": "external_id", "name": "external_id", "type": "text"},
                    {"id": "title", "name": "title", "type": "text"},
                    {"id": "status", "name": "status", "type": "single_select"},
                    {"id": "author", "name": "author", "type": "person"},
                    {"id": "occurred_at", "name": "occurred_at", "type": "date"},
                ]
            }
        },
        pages_by_resource={
            RESOURCE_ID: [
                [
                    {
                        "fields": {
                            "fld_external_id": "feishu-1",
                            "fld_title": "Milestone ready",
                            "fld_status": {"name": "done"},
                            "fld_author": [{"id": "user-a"}],
                            "fld_occurred_at": date(2026, 7, 22),
                        }
                    }
                ],
                [
                    {
                        "fields": {
                            "fld_external_id": "feishu-2",
                            "fld_title": "Team update",
                            "fld_status": {"name": "blocked"},
                            "fld_author": [{"id": "user-b"}],
                            "fld_occurred_at": "2026-07-23",
                        }
                    }
                ],
            ]
        },
    )
    reader = FeishuBitableReader(
        client,
        mappings_by_resource={
            RESOURCE_ID: [
                FeishuBitableFieldMapping(
                    logical_field="external_id",
                    external_field_id="fld_external_id",
                    external_field_name="external_id",
                    external_field_type="text",
                    converter="text",
                    required_level="critical",
                ),
                FeishuBitableFieldMapping(
                    logical_field="title",
                    external_field_id="fld_title",
                    external_field_name="title",
                    external_field_type="text",
                    converter="text",
                    required_level="required",
                ),
                FeishuBitableFieldMapping(
                    logical_field="status",
                    external_field_id="fld_status",
                    external_field_name="status",
                    external_field_type="single_select",
                    converter="enum",
                    required_level="required",
                    mapping_options={"value_map": {"done": "success", "blocked": "failed"}},
                ),
                FeishuBitableFieldMapping(
                    logical_field="author_external_id",
                    external_field_id="fld_author",
                    external_field_name="author",
                    external_field_type="person",
                    converter="person",
                    required_level="required",
                ),
                FeishuBitableFieldMapping(
                    logical_field="occurred_at",
                    external_field_id="fld_occurred_at",
                    external_field_name="occurred_at",
                    external_field_type="date",
                    converter="date",
                    required_level="critical",
                ),
            ]
        },
    )

    pages = reader.read_pages({"feishu_resource_refs": [RESOURCE_ID]})
    records = reader.read_records({"feishu_resource_refs": [RESOURCE_ID]})

    assert len(pages) == 2
    assert pages[0].schema_hash == pages[1].schema_hash
    assert pages[0].page_no == 1
    assert pages[1].page_no == 2
    assert pages[0].records[0]["author_external_id"] == "user-a"
    assert pages[0].records[0]["status"] == "success"
    assert pages[0].records[0]["state"] == "success"
    assert pages[0].records[0]["occurred_at"] == "2026-07-22T00:00:00+00:00"
    assert pages[1].records[0]["author_external_id"] == "user-b"
    assert pages[1].records[0]["status"] == "failed"
    assert len(records) == 2


def test_bitable_reader_blocks_when_required_field_is_missing() -> None:
    client = FakeBitableClient(
        schema_by_resource={
            RESOURCE_ID: {
                "fields": [
                    {"id": "fld_external_id", "name": "external_id", "type": "text"},
                    {"id": "fld_title", "name": "title", "type": "text"},
                    {"id": "fld_status", "name": "status", "type": "single_select"},
                    {"id": "fld_author", "name": "author", "type": "person"},
                ]
            }
        },
        pages_by_resource={RESOURCE_ID: [[]]},
    )
    reader = FeishuBitableReader(
        client,
        mappings_by_resource={
            RESOURCE_ID: [
                FeishuBitableFieldMapping(
                    logical_field="occurred_at",
                    external_field_id="fld_occurred_at",
                    external_field_name="occurred_at",
                    external_field_type="date",
                    converter="date",
                    required_level="critical",
                )
            ]
        },
    )

    with pytest.raises(FeishuBitableMissingFieldError):
        reader.read_pages({"feishu_resource_refs": [RESOURCE_ID]})


def test_bitable_reader_blocks_on_field_type_change() -> None:
    client = FakeBitableClient(
        schema_by_resource={
            RESOURCE_ID: {
                "fields": [
                    {"id": "fld_status", "name": "status", "type": "text"},
                ]
            }
        },
        pages_by_resource={RESOURCE_ID: [[]]},
    )
    reader = FeishuBitableReader(
        client,
        mappings_by_resource={
            RESOURCE_ID: [
                FeishuBitableFieldMapping(
                    logical_field="status",
                    external_field_id="fld_status",
                    external_field_name="status",
                    external_field_type="single_select",
                    converter="enum",
                    required_level="required",
                )
            ]
        },
    )

    with pytest.raises(FeishuBitableTypeChangedError):
        reader.read_pages({"feishu_resource_refs": [RESOURCE_ID]})


def test_bitable_reader_blocks_on_record_limit() -> None:
    client = FakeBitableClient(
        schema_by_resource={
            RESOURCE_ID: {
                "fields": [
                    {"id": "fld_external_id", "name": "external_id", "type": "text"},
                ]
            }
        },
        pages_by_resource={
            RESOURCE_ID: [
                [{"fields": {"fld_external_id": "feishu-1"}}],
                [{"fields": {"fld_external_id": "feishu-2"}}],
                [{"fields": {"fld_external_id": "feishu-3"}}],
            ]
        },
    )
    reader = FeishuBitableReader(
        client,
        mappings_by_resource={
            RESOURCE_ID: [
                FeishuBitableFieldMapping(
                    logical_field="external_id",
                    external_field_id="fld_external_id",
                    external_field_name="external_id",
                    external_field_type="text",
                    converter="text",
                    required_level="critical",
                )
            ]
        },
        max_records=2,
    )

    with pytest.raises(FeishuBitableRecordLimitError):
        reader.read_pages({"feishu_resource_refs": [RESOURCE_ID]})


def test_collection_service_persists_multiple_feishu_pages() -> None:
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
    client = FakeBitableClient(
        schema_by_resource={
            RESOURCE_ID: {
                "fields": [
                    {"id": "external_id", "name": "external_id", "type": "text"},
                    {"id": "title", "name": "title", "type": "text"},
                    {"id": "status", "name": "status", "type": "single_select"},
                    {"id": "author", "name": "author", "type": "person"},
                    {"id": "occurred_at", "name": "occurred_at", "type": "date"},
                ]
            }
        },
        pages_by_resource={
            RESOURCE_ID: [
                [
                    {
                        "fields": {
                            "external_id": "feishu-1",
                            "title": "Milestone ready",
                            "status": {"name": "done"},
                            "author": [{"id": "user-a"}],
                            "occurred_at": "2026-07-22",
                        }
                    }
                ],
                [
                    {
                        "fields": {
                            "external_id": "feishu-2",
                            "title": "Team update",
                            "status": {"name": "done"},
                            "author": [{"id": "user-b"}],
                            "occurred_at": "2026-07-23",
                        }
                    }
                ],
            ]
        },
    )
    reader = FeishuBitableReader(client)
    service = CollectionService(
        factory,
        CollectionProviders(feishu=reader, github=FakeGitHubProvider()),
    )
    scope = {
        "selected_repository_ids": ["github-repository-example"],
        "feishu_resource_refs": [RESOURCE_ID],
        "mapping_revision": "1",
    }

    outcome = service.collect_feishu_data(run_id, scope)

    assert outcome.status == "complete"
    assert outcome.source_batch_ref is not None

    with factory() as session:
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        source_batches = session.scalars(
            select(SourceDataBatch).where(SourceDataBatch.run_id == run_id)
        ).all()
        tool_executions = session.scalars(
            select(ToolExecution).where(ToolExecution.run_id == run_id)
        ).all()

        assert run_row is not None
        assert len(source_batches) == 2
        assert [batch.page_no for batch in source_batches] == [1, 2]
        assert source_batches[0].payload["schema_hash"] == source_batches[1].payload["schema_hash"]
        assert len(tool_executions) == 1
        assert tool_executions[0].result_summary["page_count"] == 2
        assert tool_executions[0].result_summary["record_count"] == 2


def test_collection_service_blocks_on_schema_change() -> None:
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
    client = FakeBitableClient(
        schema_by_resource={
            RESOURCE_ID: {
                "fields": [
                    {"id": "fld_status", "name": "status", "type": "text"},
                ]
            }
        },
        pages_by_resource={RESOURCE_ID: [[]]},
    )
    reader = FeishuBitableReader(
        client,
        mappings_by_resource={
            RESOURCE_ID: [
                FeishuBitableFieldMapping(
                    logical_field="status",
                    external_field_id="fld_status",
                    external_field_name="status",
                    external_field_type="single_select",
                    converter="enum",
                    required_level="critical",
                )
            ]
        },
    )
    service = CollectionService(
        factory,
        CollectionProviders(feishu=reader, github=FakeGitHubProvider()),
    )
    scope = {
        "selected_repository_ids": ["github-repository-example"],
        "feishu_resource_refs": [RESOURCE_ID],
        "mapping_revision": "1",
    }

    outcome = service.collect_feishu_data(run_id, scope)

    assert outcome.status == "blocked"
    assert outcome.error_code == "FEISHU_SCHEMA_CHANGED"
    assert outcome.source_batch_ref is None

    with factory() as session:
        batches = session.scalars(
            select(SourceDataBatch).where(SourceDataBatch.run_id == run_id)
        ).all()
        tool_executions = session.scalars(
            select(ToolExecution).where(ToolExecution.run_id == run_id)
        ).all()

        assert batches == []
        assert len(tool_executions) == 1
        assert tool_executions[0].status == "failed"
