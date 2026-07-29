from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    NormalizedEntity,
    NormalizedSnapshot,
    ReportRun,
    SourceDataBatch,
    ToolExecution,
    ValidationResult,
    new_id,
)
from app.domain.source import (
    DEFAULT_FEISHU_RESOURCE_ID,
    DEFAULT_GITHUB_RESOURCE_ID,
    ENTITY_TYPE_FEISHU_RECORD,
    ENTITY_TYPE_GITHUB_ISSUE,
    MAX_SOURCE_BATCH_RECORDS,
    NORMALIZER_VERSION,
    SOURCE_TYPE_FEISHU_BITABLE,
    SOURCE_TYPE_GITHUB,
    VALIDATION_RULE_SET_VERSION,
    ValidationOutcome,
    build_batch_set_hash,
    canonical_json_hash,
)
from app.providers.fake import FakeFeishuProvider, FakeGitHubProvider
from app.reports.normalization import (
    build_snapshot_content_hash,
    build_source_batch_set_hash_from_batches,
    normalize_feishu_records,
    normalize_github_issue_records,
)
from app.reports.validation import validate_normalized_entities

SessionFactory = Callable[[], Session]


@dataclass(slots=True)
class CollectionStageOutcome:
    status: Literal["complete", "partial", "blocked"]
    error_code: str | None = None
    error_summary: str | None = None
    source_batch_ref: str | None = None
    normalized_snapshot_ref: str | None = None
    validation_result_ref: str | None = None


@dataclass(slots=True)
class CollectionProviders:
    feishu: FakeFeishuProvider = field(default_factory=FakeFeishuProvider)
    github: FakeGitHubProvider = field(default_factory=FakeGitHubProvider)


class CollectionService:
    def __init__(
        self,
        session_factory: SessionFactory,
        providers: CollectionProviders | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._providers = providers or CollectionProviders()

    def collect_feishu_data(self, run_id: str, scope: Mapping[str, object]) -> CollectionStageOutcome:
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            records = self._providers.feishu.read_records()
            fetch_status = self._fetch_status(records)
            payload = {"records": records}
            source_resource_id = _first_or_default(scope.get("feishu_resource_refs"), DEFAULT_FEISHU_RESOURCE_ID)
            batch = self._upsert_source_batch(
                session,
                run=run,
                source_type=SOURCE_TYPE_FEISHU_BITABLE,
                source_resource_id=source_resource_id,
                entity_type=ENTITY_TYPE_FEISHU_RECORD,
                page_no=1,
                payload=payload,
                record_count=len(records),
                fetch_status=fetch_status,
            )
            self._record_tool_execution(
                session,
                run_id=run_id,
                node_execution_id="collect_feishu_data",
                tool_name="feishu.read_records",
                request_summary={"source_resource_id": source_resource_id},
                result_summary={"record_count": len(records), "fetch_status": fetch_status},
                data_ref=batch.id,
                status="failed" if fetch_status == "failed" else "success",
                error_class="source_fetch_failed" if fetch_status == "failed" else None,
                error_code="source_fetch_failed" if fetch_status == "failed" else None,
                retryable=False,
            )
            session.commit()
            if fetch_status == "failed":
                return CollectionStageOutcome(
                    status="blocked",
                    error_code="FEISHU_FETCH_FAILED",
                    error_summary="Fake Feishu source returned a failed batch",
                    source_batch_ref=batch.id,
                )
            return CollectionStageOutcome(status=fetch_status, source_batch_ref=batch.id)

    def collect_github_data(self, run_id: str, scope: Mapping[str, object]) -> CollectionStageOutcome:
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            records = self._providers.github.read_issue_records()
            fetch_status = self._fetch_status(records)
            payload = {"records": records}
            source_resource_id = _first_or_default(
                scope.get("selected_repository_ids"), DEFAULT_GITHUB_RESOURCE_ID
            )
            batch = self._upsert_source_batch(
                session,
                run=run,
                source_type=SOURCE_TYPE_GITHUB,
                source_resource_id=source_resource_id,
                entity_type=ENTITY_TYPE_GITHUB_ISSUE,
                page_no=1,
                payload=payload,
                record_count=len(records),
                fetch_status=fetch_status,
            )
            self._record_tool_execution(
                session,
                run_id=run_id,
                node_execution_id="collect_github_data",
                tool_name="github.read_issue_records",
                request_summary={"source_resource_id": source_resource_id},
                result_summary={"record_count": len(records), "fetch_status": fetch_status},
                data_ref=batch.id,
                status="failed" if fetch_status == "failed" else "success",
                error_class="source_fetch_failed" if fetch_status == "failed" else None,
                error_code="source_fetch_failed" if fetch_status == "failed" else None,
                retryable=False,
            )
            session.commit()
            if fetch_status == "failed":
                return CollectionStageOutcome(
                    status="blocked",
                    error_code="GITHUB_FETCH_FAILED",
                    error_summary="Fake GitHub source returned a failed batch",
                    source_batch_ref=batch.id,
                )
            return CollectionStageOutcome(status=fetch_status, source_batch_ref=batch.id)

    def normalize_data(self, run_id: str, scope: Mapping[str, object]) -> CollectionStageOutcome:
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            batches = (
                session.scalars(
                    select(SourceDataBatch)
                    .where(
                        SourceDataBatch.run_id == run_id,
                        SourceDataBatch.fetch_status != "failed",
                    )
                    .order_by(SourceDataBatch.page_no, SourceDataBatch.fetched_at)
                )
                .all()
            )
            if not batches:
                return CollectionStageOutcome(
                    status="blocked",
                    error_code="SOURCE_BATCH_MISSING",
                    error_summary="No source batches available for normalization",
                )

            entity_rows: list[dict[str, object]] = []
            for batch in batches:
                records = list(batch.payload.get("records", []))
                if batch.source_type == SOURCE_TYPE_FEISHU_BITABLE:
                    entity_rows.extend(
                        normalize_feishu_records(
                            records,
                            source_batch_id=batch.id,
                            source_resource_id=batch.source_resource_id,
                            fetched_at=batch.fetched_at,
                            period_start=batch.period_start,
                            period_end=batch.period_end,
                        )
                    )
                elif batch.source_type == SOURCE_TYPE_GITHUB:
                    entity_rows.extend(
                        normalize_github_issue_records(
                            records,
                            source_batch_id=batch.id,
                            source_resource_id=batch.source_resource_id,
                            fetched_at=batch.fetched_at,
                            period_start=batch.period_start,
                            period_end=batch.period_end,
                        )
                    )

            source_batch_set_hash = build_source_batch_set_hash_from_batches(
                [
                    {
                        "payload_hash": batch.payload_hash,
                    }
                    for batch in batches
                ]
            )
            snapshot_hash = build_snapshot_content_hash(
                source_batch_set_hash=source_batch_set_hash,
                mapping_revision=str(scope.get("mapping_revision") or "1"),
                normalizer_version=NORMALIZER_VERSION,
                entities=entity_rows,
            )
            existing = session.scalar(
                select(NormalizedSnapshot).where(
                    NormalizedSnapshot.run_id == run_id,
                    NormalizedSnapshot.content_hash == snapshot_hash,
                )
            )
            if existing is None:
                snapshot = NormalizedSnapshot(
                    id=new_id(),
                    run_id=run_id,
                    source_batch_set_hash=source_batch_set_hash,
                    mapping_revision=str(scope.get("mapping_revision") or "1"),
                    normalizer_version=NORMALIZER_VERSION,
                    entity_count=len(entity_rows),
                    status=_normalized_status_from_rows(entity_rows),
                    content_hash=snapshot_hash,
                )
                session.add(snapshot)
                session.flush()
                for row in entity_rows:
                    session.add(
                        NormalizedEntity(
                            id=new_id(),
                            run_id=run_id,
                            normalized_snapshot_id=snapshot.id,
                            source_type=str(row["source_type"]),
                            entity_type=str(row["entity_type"]),
                            source_resource_id=str(row["source_resource_id"]),
                            external_id=str(row["external_id"]),
                            repository_id=_maybe_string(row.get("repository_id")),
                            url=_maybe_string(row.get("url")),
                            title=_maybe_string(row.get("title")),
                            state=_maybe_string(row.get("state")),
                            author_external_id=_maybe_string(row.get("author_external_id")),
                            assignee_external_ids=list(row.get("assignee_external_ids", [])),
                            labels=list(row.get("labels", [])),
                            milestone_external_id=_maybe_string(row.get("milestone_external_id")),
                            created_at_external=row.get("created_at_external"),
                            updated_at_external=row.get("updated_at_external"),
                            closed_at_external=row.get("closed_at_external"),
                            occurred_at=row.get("occurred_at"),
                            raw_batch_id=_maybe_string(row.get("raw_batch_id")),
                            raw_summary=_maybe_string(row.get("raw_summary")),
                            attributes=dict(row.get("attributes", {})),
                            content_hash=str(row["content_hash"]),
                            fetched_at=cast(datetime, row["fetched_at"]),
                        )
                    )
            else:
                snapshot = existing
            self._record_tool_execution(
                session,
                run_id=run_id,
                node_execution_id="normalize_data",
                tool_name="reports.normalize",
                request_summary={"source_batch_count": len(batches)},
                result_summary={"entity_count": len(entity_rows), "content_hash": snapshot_hash},
                data_ref=snapshot.id,
                status="success",
                retryable=False,
            )
            session.commit()
            return CollectionStageOutcome(
                status=_normalized_status_from_rows(entity_rows),
                normalized_snapshot_ref=snapshot.id,
            )

    def validate_data(self, run_id: str, normalized_snapshot_id: str) -> CollectionStageOutcome:
        with self._session_factory() as session:
            snapshot = session.get(NormalizedSnapshot, normalized_snapshot_id)
            if snapshot is None:
                return CollectionStageOutcome(
                    status="blocked",
                    error_code="NORMALIZED_SNAPSHOT_MISSING",
                    error_summary="Normalized snapshot not found",
                )
            entities = session.scalars(
                select(NormalizedEntity).where(
                    NormalizedEntity.normalized_snapshot_id == normalized_snapshot_id
                )
            ).all()
            entity_dicts = [_entity_to_dict(entity) for entity in entities]
            outcome = validate_normalized_entities(
                entity_dicts,
                input_snapshot_hash=snapshot.content_hash,
                rule_set_version=VALIDATION_RULE_SET_VERSION,
            )
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
                    validation_pass=outcome.validation_pass,
                    data_quality_status=outcome.data_quality_status,
                    rule_set_version=VALIDATION_RULE_SET_VERSION,
                    critical_count=outcome.critical_count,
                    warning_count=outcome.warning_count,
                    missing_items=list(outcome.missing_items),
                    conflicts=list(outcome.conflicts),
                    warnings=list(outcome.warnings),
                    input_snapshot_hash=outcome.input_snapshot_hash,
                )
                session.add(validation_result)
                session.flush()
            else:
                validation_result = existing
            self._record_tool_execution(
                session,
                run_id=run_id,
                node_execution_id="validate_data",
                tool_name="reports.validate",
                request_summary={"normalized_snapshot_id": normalized_snapshot_id},
                result_summary={
                    "validation_pass": outcome.validation_pass,
                    "data_quality_status": outcome.data_quality_status,
                    "critical_count": outcome.critical_count,
                    "warning_count": outcome.warning_count,
                },
                data_ref=validation_result.id,
                status="success" if outcome.validation_pass else "failed",
                error_class="validation_blocked" if not outcome.validation_pass else None,
                error_code="validation_blocked" if not outcome.validation_pass else None,
                retryable=False,
            )
            session.commit()
            return CollectionStageOutcome(
                status=outcome.data_quality_status,
                validation_result_ref=validation_result.id,
                error_code="VALIDATION_BLOCKED" if not outcome.validation_pass else None,
                error_summary="Validation blocked due to critical data quality issues"
                if not outcome.validation_pass
                else None,
            )

    def _load_run(self, session: Session, run_id: str) -> ReportRun:
        run = session.get(ReportRun, run_id)
        if run is None:
            raise ValueError(f"unknown run_id: {run_id}")
        return run

    def _upsert_source_batch(
        self,
        session: Session,
        *,
        run: ReportRun,
        source_type: str,
        source_resource_id: str,
        entity_type: str,
        page_no: int,
        payload: Mapping[str, object],
        record_count: int,
        fetch_status: Literal["complete", "partial", "failed"],
    ) -> SourceDataBatch:
        payload_hash = canonical_json_hash(payload)
        existing = session.scalar(
            select(SourceDataBatch).where(
                SourceDataBatch.run_id == run.id,
                SourceDataBatch.source_type == source_type,
                SourceDataBatch.source_resource_id == source_resource_id,
                SourceDataBatch.entity_type == entity_type,
                SourceDataBatch.page_no == page_no,
                SourceDataBatch.payload_hash == payload_hash,
            )
        )
        if existing is not None:
            return existing
        batch = SourceDataBatch(
            id=new_id(),
            run_id=run.id,
            source_type=source_type,
            source_resource_id=source_resource_id,
            entity_type=entity_type,
            page_no=page_no,
            cursor=None,
            period_start=run.period_start,
            period_end=run.period_end,
            payload=dict(payload),
            payload_hash=payload_hash,
            record_count=record_count,
            schema_version="minimal.v1",
            fetch_status=fetch_status,
            fetched_at=datetime.now(timezone.utc),
            expires_at=None,
        )
        session.add(batch)
        session.flush()
        return batch

    def _record_tool_execution(
        self,
        session: Session,
        *,
        run_id: str,
        node_execution_id: str,
        tool_name: str,
        request_summary: Mapping[str, object],
        result_summary: Mapping[str, object],
        data_ref: str | None,
        status: Literal["success", "failed", "unknown"],
        error_class: str | None = None,
        error_code: str | None = None,
        retryable: bool = False,
    ) -> ToolExecution:
        attempt = 1
        idempotency_key = canonical_json_hash(
            {
                "run_id": run_id,
                "node_execution_id": node_execution_id,
                "tool_name": tool_name,
                "request_summary": dict(request_summary),
                "result_summary": dict(result_summary),
                "data_ref": data_ref,
            }
        )
        existing = session.scalar(
            select(ToolExecution).where(
                ToolExecution.run_id == run_id,
                ToolExecution.idempotency_key == idempotency_key,
                ToolExecution.attempt == attempt,
            )
        )
        if existing is not None:
            return existing
        started_at = datetime.now(timezone.utc)
        record = ToolExecution(
            id=new_id(),
            run_id=run_id,
            node_execution_id=node_execution_id,
            tool_name=tool_name,
            tool_version="minimal.v1",
            attempt=attempt,
            idempotency_key=idempotency_key,
            request_summary=dict(request_summary),
            result_summary=dict(result_summary),
            data_ref=data_ref,
            provider_request_id=None,
            status=status,
            error_class=error_class,
            error_code=error_code,
            retryable=retryable,
            started_at=started_at,
            ended_at=started_at,
            duration_ms=0,
        )
        session.add(record)
        session.flush()
        return record

    def _fetch_status(self, records: Sequence[Mapping[str, object]]) -> Literal["complete", "partial", "failed"]:
        if len(records) > MAX_SOURCE_BATCH_RECORDS:
            return "failed"
        statuses = {
            str(record.get("status") or "").casefold()
            for record in records
            if isinstance(record, Mapping)
        }
        if "failed" in statuses:
            return "failed"
        if "unknown" in statuses:
            return "partial"
        return "complete"


def _entity_to_dict(entity: NormalizedEntity) -> dict[str, object]:
    return {
        "source_type": entity.source_type,
        "entity_type": entity.entity_type,
        "source_resource_id": entity.source_resource_id,
        "external_id": entity.external_id,
        "repository_id": entity.repository_id,
        "url": entity.url,
        "title": entity.title,
        "state": entity.state,
        "author_external_id": entity.author_external_id,
        "assignee_external_ids": list(entity.assignee_external_ids),
        "labels": list(entity.labels),
        "milestone_external_id": entity.milestone_external_id,
        "created_at_external": entity.created_at_external,
        "updated_at_external": entity.updated_at_external,
        "closed_at_external": entity.closed_at_external,
        "occurred_at": entity.occurred_at,
        "raw_batch_id": entity.raw_batch_id,
        "raw_summary": entity.raw_summary,
        "attributes": dict(entity.attributes),
        "content_hash": entity.content_hash,
        "fetched_at": entity.fetched_at,
    }


def _first_or_default(value: object, default: str) -> str:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) and value:
        first = value[0]
        if isinstance(first, str) and first:
            return first
    if isinstance(value, str) and value:
        return value
    return default


def _maybe_string(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)


def _normalized_status_from_rows(rows: Sequence[Mapping[str, object]]) -> Literal["complete", "partial", "failed"]:
    if not rows:
        return "partial"
    warnings = 0
    for row in rows:
        if not row.get("title"):
            warnings += 1
    return "partial" if warnings else "complete"
