from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    EvidenceItem,
    EvidenceSet,
    MetricSnapshot,
    NormalizedEntity,
    NormalizedSnapshot,
    ReportClaim,
    ReportEvidence,
    ReportRun,
    ReportVersion,
    ToolExecution,
    ValidationResult,
    new_id,
)
from app.domain.metrics import METRICS_DEFINITION_VERSION
from app.domain.source import SOURCE_TYPE_FEISHU_BITABLE, SOURCE_TYPE_GITHUB, canonical_json_hash
from app.reports.generation import (
    REPORT_GENERATION_VERSION,
    REPORT_STATUS_DRAFT,
    build_evidence_item_content_hash,
    build_evidence_set_content_hash,
    build_structured_report_hash,
    build_structured_report_payload,
    validate_structured_report_payload,
)
from app.reports.metrics import extract_metric_values

SessionFactory = Callable[[], Session]


@dataclass(slots=True)
class ReportStageOutcome:
    status: Literal["complete", "blocked"]
    error_code: str | None = None
    error_summary: str | None = None
    evidence_set_ref: str | None = None
    report_version_ref: str | None = None


class ReportingService:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def build_evidence(self, run_id: str, metric_snapshot_id: str) -> ReportStageOutcome:
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            metric_snapshot = session.get(MetricSnapshot, metric_snapshot_id)
            if metric_snapshot is None:
                return ReportStageOutcome(
                    status="blocked",
                    error_code="METRIC_SNAPSHOT_MISSING",
                    error_summary="Metric snapshot not found",
                )
            normalized_snapshot = session.get(NormalizedSnapshot, metric_snapshot.normalized_snapshot_id)
            if normalized_snapshot is None:
                return ReportStageOutcome(
                    status="blocked",
                    error_code="NORMALIZED_SNAPSHOT_MISSING",
                    error_summary="Normalized snapshot not found",
                )
            entities = session.scalars(
                select(NormalizedEntity).where(
                    NormalizedEntity.normalized_snapshot_id == normalized_snapshot.id
                ).order_by(NormalizedEntity.source_type, NormalizedEntity.external_id)
            ).all()
            if not entities:
                return ReportStageOutcome(
                    status="blocked",
                    error_code="EVIDENCE_ENTITY_MISSING",
                    error_summary="No normalized entities available for evidence building",
                )

            evidence_items_payload = [
                _build_evidence_item_payload(
                    entity,
                    run=run,
                    metric_snapshot=metric_snapshot,
                )
                for entity in entities
            ]
            evidence_item_hashes = [str(item["content_hash"]) for item in evidence_items_payload]
            evidence_set_hash = build_evidence_set_content_hash(
                normalized_snapshot_id=normalized_snapshot.id,
                metric_snapshot_id=metric_snapshot.id,
                builder_version=REPORT_GENERATION_VERSION,
                evidence_item_hashes=evidence_item_hashes,
            )
            existing = session.scalar(
                select(EvidenceSet).where(
                    EvidenceSet.run_id == run_id,
                    EvidenceSet.content_hash == evidence_set_hash,
                )
            )
            if existing is None:
                evidence_set = EvidenceSet(
                    id=new_id(),
                    run_id=run_id,
                    normalized_snapshot_id=normalized_snapshot.id,
                    metric_snapshot_id=metric_snapshot.id,
                    builder_version=REPORT_GENERATION_VERSION,
                    content_hash=evidence_set_hash,
                )
                session.add(evidence_set)
                session.flush()
                for item in evidence_items_payload:
                    session.add(
                        EvidenceItem(
                            id=new_id(),
                            evidence_set_id=evidence_set.id,
                            evidence_key=str(item["evidence_key"]),
                            source_type=str(item["source_type"]),
                            source_resource_id=str(item["source_resource_id"]),
                            external_id=str(item["external_id"]),
                            url=_maybe_string(item.get("url")),
                            period_start=item.get("period_start"),
                            period_end=item.get("period_end"),
                            evidence_summary=_maybe_string(item.get("evidence_summary")),
                            confidence=float(item["confidence"]),
                            normalized_entity_id=_maybe_string(item.get("normalized_entity_id")),
                            content_hash=str(item["content_hash"]),
                        )
                    )
            else:
                evidence_set = existing
            self._record_tool_execution(
                session,
                run_id=run_id,
                node_execution_id="build_evidence",
                tool_name="reports.build_evidence",
                request_summary={"metric_snapshot_id": metric_snapshot_id},
                result_summary={
                    "content_hash": evidence_set_hash,
                    "evidence_item_count": len(evidence_items_payload),
                },
                data_ref=evidence_set.id,
                status="success",
                retryable=False,
            )
            session.commit()
            return ReportStageOutcome(status="complete", evidence_set_ref=evidence_set.id)

    def generate_structured_report(self, run_id: str, evidence_set_id: str) -> ReportStageOutcome:
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            evidence_set = session.get(EvidenceSet, evidence_set_id)
            if evidence_set is None:
                return ReportStageOutcome(
                    status="blocked",
                    error_code="EVIDENCE_SET_MISSING",
                    error_summary="Evidence set not found",
                )
            metric_snapshot = session.get(MetricSnapshot, evidence_set.metric_snapshot_id)
            normalized_snapshot = session.get(NormalizedSnapshot, evidence_set.normalized_snapshot_id)
            if metric_snapshot is None or normalized_snapshot is None:
                return ReportStageOutcome(
                    status="blocked",
                    error_code="SNAPSHOT_MISSING",
                    error_summary="Metric or normalized snapshot missing",
                )
            metric_values = extract_metric_values(metric_snapshot.metrics)
            validation_result = session.scalar(
                select(ValidationResult).where(
                    ValidationResult.run_id == run_id,
                    ValidationResult.input_snapshot_hash == normalized_snapshot.content_hash,
                )
            )
            if validation_result is None:
                return ReportStageOutcome(
                    status="blocked",
                    error_code="VALIDATION_RESULT_MISSING",
                    error_summary="Validation result not found",
                )

            evidence_items = session.scalars(
                select(EvidenceItem)
                .where(EvidenceItem.evidence_set_id == evidence_set.id)
                .order_by(EvidenceItem.evidence_key)
            ).all()
            evidence_item_payloads = [_evidence_item_to_payload(item) for item in evidence_items]
            data_snapshot_hash = canonical_json_hash(
                {
                    "metric_snapshot_content_hash": metric_snapshot.content_hash,
                    "evidence_set_content_hash": evidence_set.content_hash,
                }
            )
            structured_report = build_structured_report_payload(
                run_id=run.id,
                period_start=run.period_start,
                period_end=run.period_end,
                metric_snapshot_ref=metric_snapshot.id,
                evidence_set_ref=evidence_set.id,
                data_snapshot_hash=data_snapshot_hash,
                metric_snapshot_content_hash=metric_snapshot.content_hash,
                evidence_set_content_hash=evidence_set.content_hash,
                validation_status=validation_result.data_quality_status,
                evidence_items=evidence_item_payloads,
                metric_values=metric_values,
            )
            validated_report = validate_structured_report_payload(
                structured_report,
                expected_metric_values=metric_values,
                allowed_evidence_keys=[str(item["evidence_key"]) for item in evidence_item_payloads],
                expected_data_snapshot_hash=data_snapshot_hash,
            )
            structured_hash = build_structured_report_hash(validated_report)
            content_hash = canonical_json_hash(
                {
                    "structured_hash": structured_hash,
                    "data_snapshot_hash": data_snapshot_hash,
                    "definition_version": REPORT_GENERATION_VERSION,
                }
            )
            existing = session.scalar(
                select(ReportVersion).where(
                    ReportVersion.run_id == run_id,
                    ReportVersion.content_hash == content_hash,
                )
            )
            if existing is None:
                next_version = session.scalar(
                    select(func.coalesce(func.max(ReportVersion.version), 0)).where(
                        ReportVersion.run_id == run_id
                    )
                )
                report_version = ReportVersion(
                    id=new_id(),
                    run_id=run_id,
                    version=int(next_version or 0) + 1,
                    status=REPORT_STATUS_DRAFT,
                    structured_report=validated_report,
                    structured_hash=structured_hash,
                    rendered_content=None,
                    content_hash=content_hash,
                    data_snapshot_hash=data_snapshot_hash,
                    prompt_version_ids=[],
                    model_info={
                        "provider": "deterministic",
                        "model": "report-generator.minimal.v1",
                        "generation_version": REPORT_GENERATION_VERSION,
                    },
                    confidence=1.0
                    if validation_result.validation_pass
                    else 0.9,
                    data_quality_status=validation_result.data_quality_status,
                    verified_at=None,
                )
                session.add(report_version)
                session.flush()
                for claim_payload in validated_report["claims"]:
                    claim = ReportClaim(
                        id=new_id(),
                        report_version_id=report_version.id,
                        claim_key=str(claim_payload["claim_key"]),
                        content=str(claim_payload["content"]),
                        claim_type=str(claim_payload["claim_type"]),
                        importance=str(claim_payload["importance"]),
                        period_start=run.period_start,
                        period_end=run.period_end,
                        confidence=float(claim_payload["confidence"]),
                        grounding_status="unverified",
                    )
                    session.add(claim)
                    session.flush()
                    evidence_keys = [
                        str(value)
                        for value in claim_payload.get("evidence_keys", [])
                        if isinstance(value, str)
                    ]
                    for citation_order, evidence_key in enumerate(evidence_keys, start=1):
                        evidence_item = next(
                            item for item in evidence_items if item.evidence_key == evidence_key
                        )
                        session.add(
                            ReportEvidence(
                                id=new_id(),
                                claim_id=claim.id,
                                evidence_item_id=evidence_item.id,
                                citation_order=citation_order,
                                relevance_score=1.0,
                            )
                        )
            else:
                report_version = existing
            self._record_tool_execution(
                session,
                run_id=run_id,
                node_execution_id="generate_structured_report",
                tool_name="reports.generate_structured_report",
                request_summary={"evidence_set_id": evidence_set_id},
                result_summary={
                    "content_hash": content_hash,
                    "claim_count": len(validated_report["claims"]),
                },
                data_ref=report_version.id,
                status="success",
                retryable=False,
            )
            session.commit()
            return ReportStageOutcome(status="complete", report_version_ref=report_version.id)

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


def _build_evidence_item_payload(
    entity: NormalizedEntity,
    *,
    run: ReportRun,
    metric_snapshot: MetricSnapshot,
) -> dict[str, object]:
    is_overdue = _is_overdue_entity(entity, run.period_end)
    payload: dict[str, object] = {
        "evidence_key": f"{entity.source_type}:{entity.external_id}",
        "source_type": entity.source_type,
        "source_resource_id": entity.source_resource_id,
        "external_id": entity.external_id,
        "url": entity.url,
        "period_start": _date_to_utc(run.period_start),
        "period_end": _date_to_utc(run.period_end),
        "evidence_summary": entity.raw_summary or entity.title or entity.external_id,
        "confidence": 1.0 if entity.source_type == SOURCE_TYPE_FEISHU_BITABLE else 0.95,
        "normalized_entity_id": entity.id,
        "content_hash": build_evidence_item_content_hash(
            {
                "source_type": entity.source_type,
                "source_resource_id": entity.source_resource_id,
                "external_id": entity.external_id,
                "url": entity.url,
                "period_start": run.period_start.isoformat(),
                "period_end": run.period_end.isoformat(),
                "evidence_summary": entity.raw_summary or entity.title or entity.external_id,
                "confidence": 1.0 if entity.source_type == SOURCE_TYPE_FEISHU_BITABLE else 0.95,
                "normalized_entity_id": entity.id,
                "is_overdue": is_overdue,
                "metric_snapshot_id": metric_snapshot.id,
            }
        ),
        "state": entity.state,
        "is_overdue": is_overdue,
    }
    return payload


def _evidence_item_to_payload(item: EvidenceItem) -> dict[str, object]:
    return {
        "evidence_key": item.evidence_key,
        "source_type": item.source_type,
        "source_resource_id": item.source_resource_id,
        "external_id": item.external_id,
        "url": item.url,
        "period_start": item.period_start,
        "period_end": item.period_end,
        "evidence_summary": item.evidence_summary,
        "confidence": item.confidence,
        "normalized_entity_id": item.normalized_entity_id,
        "content_hash": item.content_hash,
        "state": None,
        "is_overdue": False,
    }


def _is_overdue_entity(entity: NormalizedEntity, period_end: datetime) -> bool:
    if entity.source_type != SOURCE_TYPE_GITHUB:
        return False
    if str(entity.state or "").casefold() != "open":
        return False
    updated_at = entity.updated_at_external or entity.occurred_at
    if updated_at is None:
        return False
    updated_at_utc = (
        updated_at.astimezone(timezone.utc)
        if updated_at.tzinfo
        else updated_at.replace(tzinfo=timezone.utc)
    )
    period_end_utc = (
        period_end.astimezone(timezone.utc)
        if isinstance(period_end, datetime) and period_end.tzinfo
        else datetime(period_end.year, period_end.month, period_end.day, tzinfo=timezone.utc)
    )
    return updated_at_utc < period_end_utc - timedelta(days=7)


def _maybe_string(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)


def _date_to_utc(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
