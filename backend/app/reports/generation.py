from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, Field, ValidationError

from app.domain.metrics import METRIC_KEYS, METRICS_DEFINITION_VERSION
from app.domain.source import canonical_json_hash

REPORT_GENERATION_VERSION: Final[str] = "minimal.v1"
REPORT_STATUS_DRAFT: Final[str] = "draft"
REPORT_CLAIM_TYPE_FACT: Final[str] = "fact"
REPORT_CLAIM_IMPORTANCE_CRITICAL: Final[str] = "critical"
REPORT_CLAIM_IMPORTANCE_NORMAL: Final[str] = "normal"


class ReportClaimSchema(BaseModel):
    claim_key: str = Field(min_length=1)
    content: str = Field(min_length=1)
    claim_type: Literal["fact", "inference", "needs_confirmation"]
    importance: Literal["critical", "normal"]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_keys: list[str]


class StructuredReportSchema(BaseModel):
    schema_version: str = Field(min_length=1)
    report_title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    period_start: str = Field(min_length=1)
    period_end: str = Field(min_length=1)
    metric_snapshot_ref: str = Field(min_length=1)
    evidence_set_ref: str = Field(min_length=1)
    data_snapshot_hash: str = Field(min_length=1)
    definition_version: str = Field(min_length=1)
    validation_status: str = Field(min_length=1)
    metrics: dict[str, int]
    claims: list[ReportClaimSchema]
    evidence_keys: list[str]
    source_summary: dict[str, int]


def build_structured_report_payload(
    *,
    run_id: str,
    period_start: date,
    period_end: date,
    metric_snapshot_ref: str,
    evidence_set_ref: str,
    data_snapshot_hash: str,
    metric_snapshot_content_hash: str,
    evidence_set_content_hash: str,
    validation_status: str,
    evidence_items: Sequence[Mapping[str, object]],
    metric_values: Mapping[str, int],
) -> dict[str, object]:
    allowed_metric_values = _normalize_metric_values(metric_values)
    evidence_item_list = [dict(item) for item in evidence_items]
    evidence_keys = [str(item["evidence_key"]) for item in evidence_item_list]
    claim_specs = _build_claim_specs(evidence_item_list, allowed_metric_values)
    summary = _build_summary(allowed_metric_values, evidence_item_list)
    payload: dict[str, object] = {
        "schema_version": REPORT_GENERATION_VERSION,
        "report_title": "Weekly Structured Report",
        "summary": summary,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "metric_snapshot_ref": metric_snapshot_ref,
        "evidence_set_ref": evidence_set_ref,
        "data_snapshot_hash": data_snapshot_hash,
        "definition_version": METRICS_DEFINITION_VERSION,
        "validation_status": validation_status,
        "metrics": allowed_metric_values,
        "claims": claim_specs,
        "evidence_keys": evidence_keys,
        "source_summary": {
            "run_id_length": len(run_id),
            "metric_snapshot_content_hash_length": len(metric_snapshot_content_hash),
            "evidence_set_content_hash_length": len(evidence_set_content_hash),
            "evidence_item_count": len(evidence_item_list),
        },
    }
    payload["structured_hash"] = build_structured_report_hash(payload)
    return payload


def validate_structured_report_payload(
    payload: Mapping[str, object],
    *,
    expected_metric_values: Mapping[str, int],
    allowed_evidence_keys: Sequence[str],
    expected_data_snapshot_hash: str,
) -> dict[str, object]:
    try:
        schema = StructuredReportSchema.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - validation exercised in tests
        raise ValueError(str(exc)) from exc

    normalized_expected_metrics = _normalize_metric_values(expected_metric_values)
    if schema.metrics != normalized_expected_metrics:
        raise ValueError("structured report metrics do not match metric snapshot")
    if schema.data_snapshot_hash != expected_data_snapshot_hash:
        raise ValueError("structured report data snapshot hash mismatch")

    allowed_keys = set(allowed_evidence_keys)
    if not allowed_keys:
        raise ValueError("structured report requires evidence keys")
    for claim in schema.claims:
        if not claim.evidence_keys:
            raise ValueError(f"claim {claim.claim_key} requires evidence")
        unknown = set(claim.evidence_keys) - allowed_keys
        if unknown:
            raise ValueError(
                f"claim {claim.claim_key} references unknown evidence keys: {sorted(unknown)}"
            )
    validated = schema.model_dump()
    validated["structured_hash"] = build_structured_report_hash(validated)
    return validated


def build_structured_report_hash(payload: Mapping[str, object]) -> str:
    normalized = dict(payload)
    normalized.pop("structured_hash", None)
    return canonical_json_hash(normalized)


def build_claim_evidence_map(claims: Sequence[Mapping[str, object]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for claim in claims:
        claim_key = str(claim["claim_key"])
        evidence_keys = [
            str(value)
            for value in claim.get("evidence_keys", [])
            if isinstance(value, str) and value
        ]
        mapping[claim_key] = evidence_keys
    return mapping


def build_claim_specs(
    evidence_items: Sequence[Mapping[str, object]],
    metric_values: Mapping[str, int],
) -> list[dict[str, object]]:
    return _build_claim_specs(evidence_items, metric_values)


def build_evidence_set_content_hash(
    *,
    normalized_snapshot_id: str,
    metric_snapshot_id: str,
    builder_version: str,
    evidence_item_hashes: Sequence[str],
) -> str:
    return canonical_json_hash(
        {
            "normalized_snapshot_id": normalized_snapshot_id,
            "metric_snapshot_id": metric_snapshot_id,
            "builder_version": builder_version,
            "evidence_item_hashes": sorted(evidence_item_hashes),
        }
    )


def build_evidence_item_content_hash(payload: Mapping[str, object]) -> str:
    normalized = dict(payload)
    normalized.pop("content_hash", None)
    return canonical_json_hash(normalized)


def _build_claim_specs(
    evidence_items: Sequence[Mapping[str, object]],
    metric_values: Mapping[str, int],
) -> list[dict[str, object]]:
    feishu_items = [item for item in evidence_items if str(item.get("source_type")) == "feishu_bitable"]
    github_items = [item for item in evidence_items if str(item.get("source_type")) == "github"]
    open_github_items = [
        item for item in github_items if str(item.get("state") or "").casefold() == "open"
    ]
    overdue_github_items = [
        item
        for item in github_items
        if str(item.get("state") or "").casefold() == "open" and bool(item.get("is_overdue"))
    ]
    claim_specs = [
        {
            "claim_key": "feishu_update_count",
            "content": f"Weekly Feishu updates: {len(feishu_items)} records.",
            "claim_type": REPORT_CLAIM_TYPE_FACT,
            "importance": REPORT_CLAIM_IMPORTANCE_NORMAL,
            "confidence": 1.0,
            "evidence_keys": [str(item["evidence_key"]) for item in feishu_items],
        },
        {
            "claim_key": "github_issue_summary",
            "content": (
                f"Weekly GitHub issues: {metric_values.get('github_issue_total_count', 0)} total, "
                f"{metric_values.get('github_issue_open_count', 0)} open, "
                f"{metric_values.get('github_issue_closed_count', 0)} closed."
            ),
            "claim_type": REPORT_CLAIM_TYPE_FACT,
            "importance": REPORT_CLAIM_IMPORTANCE_CRITICAL,
            "confidence": 1.0,
            "evidence_keys": [str(item["evidence_key"]) for item in github_items],
        },
        {
            "claim_key": "github_overdue_issue_count",
            "content": (
                f"Weekly overdue GitHub issues: {metric_values.get('github_issue_overdue_count', 0)}."
            ),
            "claim_type": REPORT_CLAIM_TYPE_FACT,
            "importance": REPORT_CLAIM_IMPORTANCE_NORMAL,
            "confidence": 1.0,
            "evidence_keys": [
                str(item["evidence_key"])
                for item in (overdue_github_items or open_github_items or github_items)
            ],
        },
        {
            "claim_key": "active_contributor_count",
            "content": (
                f"Weekly active contributors: {metric_values.get('active_contributor_count', 0)}."
            ),
            "claim_type": REPORT_CLAIM_TYPE_FACT,
            "importance": REPORT_CLAIM_IMPORTANCE_NORMAL,
            "confidence": 1.0,
            "evidence_keys": [str(item["evidence_key"]) for item in evidence_items],
        },
    ]
    return claim_specs


def _build_summary(metric_values: Mapping[str, int], evidence_items: Sequence[Mapping[str, object]]) -> str:
    feishu_count = sum(
        1 for item in evidence_items if str(item.get("source_type")) == "feishu_bitable"
    )
    github_count = sum(1 for item in evidence_items if str(item.get("source_type")) == "github")
    return (
        f"Weekly structured report covers {len(evidence_items)} evidence items, "
        f"{feishu_count} Feishu updates, "
        f"{github_count} GitHub issues, "
        f"and {metric_values.get('active_contributor_count', 0)} active contributors."
    )


def _normalize_metric_values(metric_values: Mapping[str, int]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key in METRIC_KEYS:
        value = metric_values.get(key)
        if not isinstance(value, int):
            raise ValueError(f"metric value for {key} must be int")
        normalized[key] = value
    return normalized
