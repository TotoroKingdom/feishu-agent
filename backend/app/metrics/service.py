from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MetricSnapshot, NormalizedEntity, NormalizedSnapshot, ReportRun, ToolExecution, new_id
from app.domain.metrics import METRICS_DEFINITION_VERSION
from app.domain.source import canonical_json_hash
from app.reports.metrics import build_metric_snapshot_content_hash, calculate_metric_payload

SessionFactory = Callable[[], Session]


@dataclass(slots=True)
class MetricStageOutcome:
    status: Literal["complete", "blocked"]
    error_code: str | None = None
    error_summary: str | None = None
    metrics_ref: str | None = None


class MetricsService:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def calculate_metrics(self, run_id: str, normalized_snapshot_id: str) -> MetricStageOutcome:
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            snapshot = session.get(NormalizedSnapshot, normalized_snapshot_id)
            if snapshot is None:
                return MetricStageOutcome(
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
            payload = calculate_metric_payload(
                entity_dicts,
                period_start=run.period_start,
                period_end=run.period_end,
                definition_version=METRICS_DEFINITION_VERSION,
            )
            content_hash = build_metric_snapshot_content_hash(payload)
            existing = session.scalar(
                select(MetricSnapshot).where(
                    MetricSnapshot.run_id == run_id,
                    MetricSnapshot.normalized_snapshot_id == normalized_snapshot_id,
                    MetricSnapshot.definition_version == METRICS_DEFINITION_VERSION,
                    MetricSnapshot.content_hash == content_hash,
                )
            )
            if existing is None:
                metric_snapshot = MetricSnapshot(
                    id=new_id(),
                    run_id=run_id,
                    normalized_snapshot_id=normalized_snapshot_id,
                    definition_version=METRICS_DEFINITION_VERSION,
                    period_start=_to_utc_datetime(run.period_start),
                    period_end=_to_utc_datetime(run.period_end),
                    metrics=dict(payload),
                    content_hash=content_hash,
                )
                session.add(metric_snapshot)
                session.flush()
            else:
                metric_snapshot = existing
            self._record_tool_execution(
                session,
                run_id=run_id,
                node_execution_id="calculate_metrics",
                tool_name="reports.calculate_metrics",
                request_summary={"normalized_snapshot_id": normalized_snapshot_id},
                result_summary={
                    "content_hash": content_hash,
                    "metric_keys": list(payload.get("metric_keys", [])),
                },
                data_ref=metric_snapshot.id,
                status="success",
                retryable=False,
            )
            session.commit()
            return MetricStageOutcome(status="complete", metrics_ref=metric_snapshot.id)

    def _load_run(self, session: Session, run_id: str) -> ReportRun:
        run = session.get(ReportRun, run_id)
        if run is None:
            raise ValueError(f"unknown run_id: {run_id}")
        return run

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


def _to_utc_datetime(value: date | datetime) -> datetime:
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
