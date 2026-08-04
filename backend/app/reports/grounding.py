from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

from app.reports.generation import (
    build_claim_evidence_map,
    build_claim_specs,
    build_structured_report_hash,
)

GROUNDING_VERSION: str = "minimal.v1"


@dataclass(slots=True)
class GroundingVerificationResult:
    status: Literal["pass", "blocked"]
    error_code: str | None = None
    error_summary: str | None = None
    claim_statuses: dict[str, str] | None = None
    grounded_claim_count: int = 0


def verify_structured_report_grounding(
    structured_report: Mapping[str, object],
    *,
    evidence_items: Sequence[Mapping[str, object]],
    period_start: date,
    period_end: date,
) -> GroundingVerificationResult:
    claims = _as_sequence(structured_report.get("claims"))
    if not claims:
        return GroundingVerificationResult(
            status="blocked",
            error_code="CLAIMS_MISSING",
            error_summary="Structured report has no claims to ground",
        )

    report_period_start = _as_date_text(structured_report.get("period_start"))
    report_period_end = _as_date_text(structured_report.get("period_end"))
    expected_period_start = period_start.isoformat()
    expected_period_end = period_end.isoformat()
    if report_period_start != expected_period_start or report_period_end != expected_period_end:
        return GroundingVerificationResult(
            status="blocked",
            error_code="REPORT_PERIOD_MISMATCH",
            error_summary="Structured report period does not match run period",
        )

    evidence_item_list = [dict(item) for item in evidence_items]
    if not evidence_item_list:
        return GroundingVerificationResult(
            status="blocked",
            error_code="EVIDENCE_ITEMS_MISSING",
            error_summary="Structured report has no evidence items",
        )

    evidence_by_key = {
        str(item.get("evidence_key")): item
        for item in evidence_item_list
        if str(item.get("evidence_key"))
    }
    if len(evidence_by_key) != len(evidence_item_list):
        return GroundingVerificationResult(
            status="blocked",
            error_code="DUPLICATE_EVIDENCE_KEYS",
            error_summary="Evidence items contain duplicate evidence keys",
        )
    for item in evidence_item_list:
        if _evidence_period_key(item, "period_start") != expected_period_start:
            return GroundingVerificationResult(
                status="blocked",
                error_code="PERIOD_MISMATCH",
                error_summary="Evidence item period_start does not match run period",
            )
        if _evidence_period_key(item, "period_end") != expected_period_end:
            return GroundingVerificationResult(
                status="blocked",
                error_code="PERIOD_MISMATCH",
                error_summary="Evidence item period_end does not match run period",
            )

    expected_metric_values = _as_metric_values(structured_report.get("metrics"))
    expected_claim_specs = build_claim_specs(
        evidence_item_list,
        expected_metric_values,
        period_start=period_start,
        period_end=period_end,
        member_activity_breakdown=_as_sequence(structured_report.get("member_activity_breakdown")),
    )
    expected_claim_map = {str(spec["claim_key"]): spec for spec in expected_claim_specs}
    report_claim_map = {str(claim.get("claim_key")): dict(claim) for claim in claims}

    if set(report_claim_map) != set(expected_claim_map):
        missing = sorted(set(expected_claim_map) - set(report_claim_map))
        extra = sorted(set(report_claim_map) - set(expected_claim_map))
        if extra:
            return GroundingVerificationResult(
                status="blocked",
                error_code="UNKNOWN_CLAIM_KEY",
                error_summary=f"Structured report contains unexpected claims: {extra}",
            )
        return GroundingVerificationResult(
            status="blocked",
            error_code="CLAIMS_MISSING",
            error_summary=f"Structured report is missing claims: {missing}",
        )

    claim_statuses: dict[str, str] = {}
    for claim_key, expected in expected_claim_map.items():
        claim = report_claim_map[claim_key]
        result = _verify_claim(
            claim_key=claim_key,
            claim=claim,
            expected=expected,
            evidence_by_key=evidence_by_key,
        )
        if result is not None:
            return result
        claim_statuses[claim_key] = _claim_status(expected)

    return GroundingVerificationResult(
        status="pass",
        claim_statuses=claim_statuses,
        grounded_claim_count=len(claim_statuses),
    )


def build_grounded_render_payload(
    structured_report: Mapping[str, object],
    *,
    evidence_items: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    evidence_item_list = [dict(item) for item in evidence_items]
    claim_map = build_claim_evidence_map(_as_sequence(structured_report.get("claims")))
    return {
        "structured_hash": build_structured_report_hash(structured_report),
        "report_title": str(structured_report.get("report_title") or "Weekly Structured Report"),
        "summary": str(structured_report.get("summary") or ""),
        "period_start": str(structured_report.get("period_start") or ""),
        "period_end": str(structured_report.get("period_end") or ""),
        "metrics": dict(_as_mapping(structured_report.get("metrics"))),
        "claims": [dict(claim) for claim in _as_sequence(structured_report.get("claims"))],
        "claim_evidence_map": claim_map,
        "evidence_items": evidence_item_list,
    }


def _verify_claim(
    *,
    claim_key: str,
    claim: Mapping[str, object],
    expected: Mapping[str, object],
    evidence_by_key: Mapping[str, Mapping[str, object]],
) -> GroundingVerificationResult | None:
    if str(claim.get("claim_type")) != str(expected.get("claim_type")):
        return GroundingVerificationResult(
            status="blocked",
            error_code="CLAIM_TYPE_MISMATCH",
            error_summary=f"Claim type mismatch for {claim_key}",
        )
    if str(claim.get("importance")) != str(expected.get("importance")):
        return GroundingVerificationResult(
            status="blocked",
            error_code="CLAIM_IMPORTANCE_MISMATCH",
            error_summary=f"Claim importance mismatch for {claim_key}",
        )
    if _claim_period_text(claim, "period_start") != _claim_period_text(expected, "period_start"):
        return GroundingVerificationResult(
            status="blocked",
            error_code="CLAIM_PERIOD_MISMATCH",
            error_summary=f"Claim period mismatch for {claim_key}",
        )
    if _claim_period_text(claim, "period_end") != _claim_period_text(expected, "period_end"):
        return GroundingVerificationResult(
            status="blocked",
            error_code="CLAIM_PERIOD_MISMATCH",
            error_summary=f"Claim period mismatch for {claim_key}",
        )
    if str(claim.get("content")) != str(expected.get("content")):
        return GroundingVerificationResult(
            status="blocked",
            error_code="CLAIM_CONTENT_MISMATCH",
            error_summary=f"Claim content mismatch for {claim_key}",
        )

    claim_evidence_keys = _claim_evidence_keys(claim)
    expected_evidence_keys = [
        str(value) for value in expected.get("evidence_keys", []) if isinstance(value, str)
    ]
    if claim_evidence_keys != expected_evidence_keys:
        return GroundingVerificationResult(
            status="blocked",
            error_code="CLAIM_EVIDENCE_MISMATCH",
            error_summary=f"Claim evidence mismatch for {claim_key}",
        )
    if str(expected.get("importance")) == "critical" and not claim_evidence_keys:
        return GroundingVerificationResult(
            status="blocked",
            error_code="GROUNDING_CRITICAL_CLAIM_UNGROUNDED",
            error_summary=f"Critical claim {claim_key} has no supporting evidence",
        )

    for evidence_key in claim_evidence_keys:
        evidence_item = evidence_by_key.get(evidence_key)
        if evidence_item is None:
            return GroundingVerificationResult(
                status="blocked",
                error_code="UNKNOWN_EVIDENCE_KEY",
                error_summary=f"Claim {claim_key} references unknown evidence key {evidence_key}",
            )
    return None


def _claim_evidence_keys(claim: Mapping[str, object]) -> list[str]:
    values = claim.get("evidence_keys", [])
    if not isinstance(values, Sequence) or isinstance(values, str | bytes | bytearray):
        return []
    return [str(value) for value in values if isinstance(value, str) and value]


def _evidence_period_key(item: Mapping[str, object], key: str) -> str:
    value = item.get(key)
    if isinstance(value, str):
        return value[:10]
    if isinstance(value, datetime):
        return (
            value.astimezone(UTC).date().isoformat() if value.tzinfo else value.date().isoformat()
        )
    if isinstance(value, date):
        return value.isoformat()
    return ""


def _as_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _as_metric_values(value: object) -> dict[str, int]:
    metrics = _as_mapping(value)
    normalized: dict[str, int] = {}
    for key, metric_value in metrics.items():
        if isinstance(metric_value, int):
            normalized[str(key)] = metric_value
    return normalized


def _as_sequence(value: object) -> Sequence[Mapping[str, object]]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _as_date_text(value: object) -> str:
    if isinstance(value, str):
        return value[:10]
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return ""


def _claim_period_text(claim: Mapping[str, object], key: str) -> str:
    value = claim.get(key)
    if isinstance(value, str):
        return value[:10]
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return ""


def _claim_status(expected: Mapping[str, object]) -> str:
    if str(expected.get("claim_type")) == "needs_confirmation":
        return "downgraded"
    return "verified"
