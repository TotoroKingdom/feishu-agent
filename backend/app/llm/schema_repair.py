from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal, cast

from app.llm.policies import (
    sanitize_member_activity_breakdown,
    sanitize_prompt_text,
)
from app.reports.generation import (
    REPORT_CLAIM_IMPORTANCE_CRITICAL,
    REPORT_CLAIM_IMPORTANCE_NORMAL,
    REPORT_CLAIM_TYPE_FACT,
    REPORT_CLAIM_TYPE_INFERENCE,
    REPORT_CLAIM_TYPE_NEEDS_CONFIRMATION,
    build_structured_report_hash,
    build_structured_report_payload,
    validate_structured_report_payload,
)


@dataclass(frozen=True, slots=True)
class StructuredReportRepairContext:
    run_id: str
    period_start: date
    period_end: date
    metric_snapshot_ref: str
    evidence_set_ref: str
    data_snapshot_hash: str
    metric_snapshot_content_hash: str
    evidence_set_content_hash: str
    validation_status: str
    evidence_items: Sequence[Mapping[str, object]]
    metric_values: Mapping[str, int]
    member_activity_breakdown: Sequence[Mapping[str, object]] | None = None


@dataclass(frozen=True, slots=True)
class StructuredReportRepairResult:
    status: Literal["repaired", "blocked"]
    payload: dict[str, object] | None
    attempts: int
    error_code: str | None = None
    error_summary: str | None = None
    dropped_fields: tuple[str, ...] = ()


def repair_structured_report_payload(
    payload: Mapping[str, object],
    *,
    context: StructuredReportRepairContext,
    max_attempts: int = 2,
) -> StructuredReportRepairResult:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    canonical_report = _canonical_report(context)
    canonical_claim_values = cast(Sequence[Mapping[str, object]], canonical_report["claims"])
    allowed_claim_keys = [str(claim["claim_key"]) for claim in canonical_claim_values]
    allowed_evidence_keys = [str(item["evidence_key"]) for item in context.evidence_items]

    normalized_payload, dropped_fields = _normalize_payload(
        payload,
        canonical_report=canonical_report,
        allowed_claim_keys=allowed_claim_keys,
        allowed_evidence_keys=allowed_evidence_keys,
    )
    try:
        validated = validate_structured_report_payload(
            normalized_payload,
            expected_metric_values=context.metric_values,
            allowed_evidence_keys=allowed_evidence_keys,
            expected_data_snapshot_hash=context.data_snapshot_hash,
        )
    except ValueError as first_error:
        if max_attempts == 1:
            return StructuredReportRepairResult(
                status="blocked",
                payload=None,
                attempts=1,
                error_code="SCHEMA_REPAIR_LIMIT_EXCEEDED",
                error_summary=str(first_error),
                dropped_fields=dropped_fields,
            )

        try:
            validated = validate_structured_report_payload(
                canonical_report,
                expected_metric_values=context.metric_values,
                allowed_evidence_keys=allowed_evidence_keys,
                expected_data_snapshot_hash=context.data_snapshot_hash,
            )
        except ValueError as second_error:  # pragma: no cover - canonical path should pass
            return StructuredReportRepairResult(
                status="blocked",
                payload=None,
                attempts=2,
                error_code="SCHEMA_REPAIR_LIMIT_EXCEEDED",
                error_summary=str(second_error),
                dropped_fields=dropped_fields,
            )

        return StructuredReportRepairResult(
            status="repaired",
            payload=validated,
            attempts=2,
            dropped_fields=dropped_fields,
        )

    return StructuredReportRepairResult(
        status="repaired",
        payload=validated,
        attempts=1,
        dropped_fields=dropped_fields,
    )


def _canonical_report(context: StructuredReportRepairContext) -> dict[str, object]:
    report = build_structured_report_payload(
        run_id=context.run_id,
        period_start=context.period_start,
        period_end=context.period_end,
        metric_snapshot_ref=context.metric_snapshot_ref,
        evidence_set_ref=context.evidence_set_ref,
        data_snapshot_hash=context.data_snapshot_hash,
        metric_snapshot_content_hash=context.metric_snapshot_content_hash,
        evidence_set_content_hash=context.evidence_set_content_hash,
        validation_status=context.validation_status,
        evidence_items=context.evidence_items,
        metric_values=context.metric_values,
        member_activity_breakdown=context.member_activity_breakdown,
    )
    report["structured_hash"] = build_structured_report_hash(report)
    return report


def _normalize_payload(
    payload: Mapping[str, object],
    *,
    canonical_report: Mapping[str, object],
    allowed_claim_keys: Sequence[str],
    allowed_evidence_keys: Sequence[str],
) -> tuple[dict[str, object], tuple[str, ...]]:
    data: dict[str, object] = {}
    dropped_fields: list[str] = []
    raw_payload = dict(payload)

    for key in raw_payload:
        if key not in canonical_report:
            dropped_fields.append(key)

    for key, value in raw_payload.items():
        if key == "claims":
            claims = _normalize_claims(
                value, canonical_report, allowed_claim_keys, allowed_evidence_keys
            )
            if claims is not None:
                data["claims"] = claims
            continue
        if key == "evidence_keys":
            data["evidence_keys"] = _normalize_evidence_keys(value, allowed_evidence_keys)
            continue
        if key == "member_activity_breakdown":
            if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
                data["member_activity_breakdown"] = sanitize_member_activity_breakdown(
                    [item for item in value if isinstance(item, Mapping)]
                )
            continue
        if key == "summary":
            data["summary"] = sanitize_prompt_text(value, max_length=1024)
            continue
        if key == "report_title":
            data["report_title"] = sanitize_prompt_text(value, max_length=128)
            continue
        if key == "metrics":
            data["metrics"] = _normalize_metrics(value, canonical_report)
            continue
        if key == "source_summary":
            data["source_summary"] = _normalize_source_summary(value, canonical_report)
            continue
        if key in {
            "schema_version",
            "period_start",
            "period_end",
            "metric_snapshot_ref",
            "evidence_set_ref",
            "data_snapshot_hash",
            "definition_version",
            "validation_status",
        }:
            data[key] = sanitize_prompt_text(value, max_length=128)
            continue
        if key == "structured_hash":
            continue
        if key in data:
            data[key] = value

    data["structured_hash"] = build_structured_report_hash(data)
    return data, tuple(dropped_fields)


def _normalize_claims(
    value: object,
    canonical_report: Mapping[str, object],
    allowed_claim_keys: Sequence[str],
    allowed_evidence_keys: Sequence[str],
) -> list[dict[str, object]] | None:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return None

    raw_claims = [dict(item) for item in value if isinstance(item, Mapping)]
    raw_by_key: dict[str, dict[str, object]] = {}
    for item in raw_claims:
        claim_key = item.get("claim_key")
        if not isinstance(claim_key, str) or not claim_key:
            continue
        if claim_key in raw_by_key:
            return None
        raw_by_key[claim_key] = item
    if any(claim_key not in raw_by_key for claim_key in allowed_claim_keys):
        return None

    canonical_claims = [
        dict(item)
        for item in cast(Sequence[object], canonical_report.get("claims", []))
        if isinstance(item, Mapping)
    ]
    canonical_by_key = {
        str(item.get("claim_key")): item
        for item in canonical_claims
        if isinstance(item.get("claim_key"), str) and item.get("claim_key")
    }

    normalized: list[dict[str, object]] = []
    for claim_key in allowed_claim_keys:
        canonical_claim = canonical_by_key.get(claim_key)
        raw_claim = raw_by_key.get(claim_key)
        if canonical_claim is None or raw_claim is None:
            continue
        normalized_claim = dict(canonical_claim)
        normalized_claim["claim_key"] = sanitize_prompt_text(claim_key, max_length=128)
        normalized_claim["content"] = sanitize_prompt_text(raw_claim.get("content"), max_length=512)
        claim_type = sanitize_prompt_text(raw_claim.get("claim_type"), max_length=32)
        if claim_type in {
            REPORT_CLAIM_TYPE_FACT,
            REPORT_CLAIM_TYPE_INFERENCE,
            REPORT_CLAIM_TYPE_NEEDS_CONFIRMATION,
        }:
            normalized_claim["claim_type"] = claim_type
        importance = sanitize_prompt_text(raw_claim.get("importance"), max_length=32)
        if importance in {REPORT_CLAIM_IMPORTANCE_CRITICAL, REPORT_CLAIM_IMPORTANCE_NORMAL}:
            normalized_claim["importance"] = importance
        period_start = sanitize_prompt_text(raw_claim.get("period_start"), max_length=32)
        if period_start:
            normalized_claim["period_start"] = period_start
        period_end = sanitize_prompt_text(raw_claim.get("period_end"), max_length=32)
        if period_end:
            normalized_claim["period_end"] = period_end
        confidence = _normalize_confidence(
            raw_claim.get("confidence"), normalized_claim.get("confidence")
        )
        normalized_claim["confidence"] = confidence
        normalized_claim["evidence_keys"] = _normalize_evidence_keys(
            raw_claim.get("evidence_keys"),
            allowed_evidence_keys,
        )
        normalized.append(normalized_claim)

    return normalized


def _normalize_metrics(value: object, canonical_report: Mapping[str, object]) -> dict[str, int]:
    canonical_metrics = canonical_report.get("metrics")
    canonical_metric_map = dict(canonical_metrics) if isinstance(canonical_metrics, Mapping) else {}
    if not isinstance(value, Mapping):
        return canonical_metric_map
    metrics: dict[str, int] = {}
    for key, canonical_value in canonical_metric_map.items():
        raw_value = value.get(key)
        metrics[key] = _coerce_int(raw_value, canonical_value)
    return metrics


def _normalize_source_summary(
    value: object,
    canonical_report: Mapping[str, object],
) -> dict[str, int]:
    canonical_summary = canonical_report.get("source_summary")
    canonical_summary_map = (
        dict(canonical_summary) if isinstance(canonical_summary, Mapping) else {}
    )
    if not isinstance(value, Mapping):
        return canonical_summary_map
    summary: dict[str, int] = {}
    for key, canonical_value in canonical_summary_map.items():
        summary[key] = _coerce_int(value.get(key), canonical_value)
    return summary


def _normalize_evidence_keys(
    value: object,
    allowed_evidence_keys: Sequence[str],
) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    allowed = set(allowed_evidence_keys)
    seen: set[str] = set()
    keys: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = sanitize_prompt_text(item, max_length=128)
        if normalized not in allowed or normalized in seen:
            continue
        seen.add(normalized)
        keys.append(normalized)
    return keys


def _normalize_confidence(value: object, fallback: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        try:
            return max(0.0, min(1.0, float(value.strip())))
        except ValueError:
            pass
    if isinstance(fallback, int | float):
        return max(0.0, min(1.0, float(fallback)))
    return 0.0


def _coerce_int(value: object, fallback: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            pass
    if isinstance(fallback, int):
        return fallback
    if isinstance(fallback, float):
        return int(round(fallback))
    return 0
