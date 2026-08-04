from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.metrics import METRIC_KEYS, METRICS_DEFINITION_VERSION
from app.domain.source import canonical_json_hash
from app.llm.policies import (
    sanitize_evidence_item_payload,
    sanitize_member_activity_breakdown,
    sanitize_prompt_identifier,
    sanitize_prompt_text,
)

REPORT_GENERATION_VERSION: Final[str] = "prd.v1"
REPORT_STATUS_DRAFT: Final[str] = "draft"
REPORT_CLAIM_TYPE_FACT: Final[str] = "fact"
REPORT_CLAIM_TYPE_INFERENCE: Final[str] = "inference"
REPORT_CLAIM_TYPE_NEEDS_CONFIRMATION: Final[str] = "needs_confirmation"
REPORT_CLAIM_IMPORTANCE_CRITICAL: Final[str] = "critical"
REPORT_CLAIM_IMPORTANCE_NORMAL: Final[str] = "normal"


class ReportClaimSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_key: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=512)
    claim_type: Literal["fact", "inference", "needs_confirmation"]
    importance: Literal["critical", "normal"]
    period_start: str = Field(min_length=1, max_length=32)
    period_end: str = Field(min_length=1, max_length=32)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_keys: list[str]


class StructuredReportSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1, max_length=32)
    report_title: str = Field(min_length=1, max_length=128)
    summary: str = Field(min_length=1, max_length=1024)
    period_start: str = Field(min_length=1, max_length=32)
    period_end: str = Field(min_length=1, max_length=32)
    metric_snapshot_ref: str = Field(min_length=1, max_length=128)
    evidence_set_ref: str = Field(min_length=1, max_length=128)
    data_snapshot_hash: str = Field(min_length=1, max_length=128)
    definition_version: str = Field(min_length=1, max_length=64)
    validation_status: str = Field(min_length=1, max_length=32)
    metrics: dict[str, int]
    claims: list[ReportClaimSchema]
    evidence_keys: list[str]
    source_summary: dict[str, int]
    member_activity_breakdown: list[dict[str, object]] = Field(default_factory=list)
    structured_hash: str = Field(min_length=1, max_length=64)


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
    member_activity_breakdown: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    allowed_metric_values = _normalize_metric_values(metric_values)
    evidence_item_list = [sanitize_evidence_item_payload(item) for item in evidence_items]
    evidence_keys = [str(item["evidence_key"]) for item in evidence_item_list]
    breakdown_list = sanitize_member_activity_breakdown(member_activity_breakdown or [])
    claim_specs = _build_claim_specs(
        evidence_item_list,
        allowed_metric_values,
        period_start=period_start,
        period_end=period_end,
        member_activity_breakdown=breakdown_list,
    )
    summary = _build_summary(allowed_metric_values, evidence_item_list, breakdown_list)
    payload: dict[str, object] = {
        "schema_version": REPORT_GENERATION_VERSION,
        "report_title": "Weekly Structured Report",
        "summary": sanitize_prompt_text(summary, max_length=1024),
        "period_start": sanitize_prompt_identifier(period_start.isoformat(), max_length=32),
        "period_end": sanitize_prompt_identifier(period_end.isoformat(), max_length=32),
        "metric_snapshot_ref": sanitize_prompt_identifier(metric_snapshot_ref, max_length=128),
        "evidence_set_ref": sanitize_prompt_identifier(evidence_set_ref, max_length=128),
        "data_snapshot_hash": sanitize_prompt_identifier(data_snapshot_hash, max_length=128),
        "definition_version": METRICS_DEFINITION_VERSION,
        "validation_status": sanitize_prompt_identifier(validation_status, max_length=32),
        "metrics": allowed_metric_values,
        "claims": claim_specs,
        "evidence_keys": evidence_keys,
        "source_summary": {
            "run_id_length": len(run_id),
            "metric_snapshot_content_hash_length": len(metric_snapshot_content_hash),
            "evidence_set_content_hash_length": len(evidence_set_content_hash),
            "evidence_item_count": len(evidence_item_list),
            "member_activity_breakdown_count": len(breakdown_list),
        },
        "member_activity_breakdown": breakdown_list,
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
    claim_keys = [claim.claim_key for claim in schema.claims]
    if len(claim_keys) != len(set(claim_keys)):
        raise ValueError("duplicate claim keys")
    for claim in schema.claims:
        if len(claim.evidence_keys) != len(set(claim.evidence_keys)):
            raise ValueError(f"duplicate evidence keys for claim {claim.claim_key}")
        if claim.period_start != schema.period_start or claim.period_end != schema.period_end:
            raise ValueError(f"claim {claim.claim_key} period does not match report period")
        unknown = set(claim.evidence_keys) - allowed_keys
        if unknown:
            raise ValueError(
                f"claim {claim.claim_key} references unknown evidence keys: {sorted(unknown)}"
            )
    expected_hash = build_structured_report_hash(schema.model_dump())
    if schema.structured_hash != expected_hash:
        raise ValueError("structured report hash mismatch")
    validated = schema.model_dump()
    validated["structured_hash"] = expected_hash
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
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    member_activity_breakdown: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    return _build_claim_specs(
        evidence_items,
        metric_values,
        period_start=period_start,
        period_end=period_end,
        member_activity_breakdown=member_activity_breakdown,
    )


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
    *,
    period_start: date | None,
    period_end: date | None,
    member_activity_breakdown: Sequence[Mapping[str, object]] | None,
) -> list[dict[str, object]]:
    period_start_text = _period_text(period_start, evidence_items, "period_start")
    period_end_text = _period_text(period_end, evidence_items, "period_end")
    feishu_items = [
        item for item in evidence_items if str(item.get("source_type")) == "feishu_bitable"
    ]
    github_items = [item for item in evidence_items if str(item.get("source_type")) == "github"]
    github_keys = [str(item["evidence_key"]) for item in github_items]
    feishu_keys = [str(item["evidence_key"]) for item in feishu_items]
    all_keys = [str(item["evidence_key"]) for item in evidence_items]
    breakdown_text = _format_member_activity_breakdown(member_activity_breakdown or [])

    claim_specs = [
        _claim_spec(
            claim_key="github_issue_summary",
            content=(
                "Weekly GitHub issues: "
                f"{metric_values.get('github_issue_total_count', 0)} total, "
                f"{metric_values.get('github_issue_open_count', 0)} open, "
                f"{metric_values.get('github_issue_closed_count', 0)} closed, "
                f"{metric_values.get('github_issue_overdue_count', 0)} overdue."
            ),
            claim_type=REPORT_CLAIM_TYPE_FACT,
            importance=REPORT_CLAIM_IMPORTANCE_CRITICAL,
            confidence=1.0,
            evidence_keys=github_keys,
            period_start=period_start_text,
            period_end=period_end_text,
        ),
        _claim_spec(
            claim_key="github_issue_open_count",
            content=(
                f"Weekly open GitHub issues: {metric_values.get('github_issue_open_count', 0)}."
            ),
            claim_type=REPORT_CLAIM_TYPE_FACT,
            importance=REPORT_CLAIM_IMPORTANCE_NORMAL,
            confidence=1.0,
            evidence_keys=github_keys,
            period_start=period_start_text,
            period_end=period_end_text,
        ),
        _claim_spec(
            claim_key="github_issue_closed_count",
            content=(
                f"Weekly closed GitHub issues: {metric_values.get('github_issue_closed_count', 0)}."
            ),
            claim_type=REPORT_CLAIM_TYPE_FACT,
            importance=REPORT_CLAIM_IMPORTANCE_NORMAL,
            confidence=1.0,
            evidence_keys=github_keys,
            period_start=period_start_text,
            period_end=period_end_text,
        ),
        _claim_spec(
            claim_key="github_issue_overdue_count",
            content=(
                "Weekly overdue GitHub issues: "
                f"{metric_values.get('github_issue_overdue_count', 0)}."
            ),
            claim_type=REPORT_CLAIM_TYPE_FACT,
            importance=REPORT_CLAIM_IMPORTANCE_NORMAL,
            confidence=1.0,
            evidence_keys=github_keys,
            period_start=period_start_text,
            period_end=period_end_text,
        ),
        _claim_spec(
            claim_key="github_pr_total_count",
            content=(
                f"Weekly GitHub pull requests: {metric_values.get('github_pr_total_count', 0)}."
            ),
            claim_type=REPORT_CLAIM_TYPE_FACT,
            importance=REPORT_CLAIM_IMPORTANCE_NORMAL,
            confidence=1.0,
            evidence_keys=github_keys,
            period_start=period_start_text,
            period_end=period_end_text,
        ),
        _claim_spec(
            claim_key="github_pr_merged_count",
            content=(
                "Weekly merged GitHub pull requests: "
                f"{metric_values.get('github_pr_merged_count', 0)}."
            ),
            claim_type=REPORT_CLAIM_TYPE_FACT,
            importance=REPORT_CLAIM_IMPORTANCE_NORMAL,
            confidence=1.0,
            evidence_keys=github_keys,
            period_start=period_start_text,
            period_end=period_end_text,
        ),
        _claim_spec(
            claim_key="github_pr_long_review_count",
            content=(
                "Weekly long-review GitHub pull requests: "
                f"{metric_values.get('github_pr_long_review_count', 0)}."
            ),
            claim_type=REPORT_CLAIM_TYPE_INFERENCE,
            importance=REPORT_CLAIM_IMPORTANCE_NORMAL,
            confidence=0.75,
            evidence_keys=github_keys,
            period_start=period_start_text,
            period_end=period_end_text,
        ),
        _claim_spec(
            claim_key="github_commit_count",
            content=f"Weekly GitHub commits: {metric_values.get('github_commit_count', 0)}.",
            claim_type=REPORT_CLAIM_TYPE_FACT,
            importance=REPORT_CLAIM_IMPORTANCE_NORMAL,
            confidence=1.0,
            evidence_keys=github_keys,
            period_start=period_start_text,
            period_end=period_end_text,
        ),
        _claim_spec(
            claim_key="active_contributor_count",
            content=(
                f"Weekly active contributors: {metric_values.get('active_contributor_count', 0)}."
            ),
            claim_type=REPORT_CLAIM_TYPE_FACT,
            importance=REPORT_CLAIM_IMPORTANCE_NORMAL,
            confidence=1.0,
            evidence_keys=all_keys,
            period_start=period_start_text,
            period_end=period_end_text,
        ),
        _claim_spec(
            claim_key="milestone_completion_rate",
            content=(
                "Weekly milestone completion rate: "
                f"{metric_values.get('milestone_completion_rate', 0)}%."
            ),
            claim_type=REPORT_CLAIM_TYPE_INFERENCE,
            importance=REPORT_CLAIM_IMPORTANCE_NORMAL,
            confidence=0.8,
            evidence_keys=github_keys,
            period_start=period_start_text,
            period_end=period_end_text,
        ),
        _claim_spec(
            claim_key="plan_task_completion_rate",
            content=(
                "Weekly plan task completion rate: "
                f"{metric_values.get('plan_task_completion_rate', 0)}%."
            ),
            claim_type=REPORT_CLAIM_TYPE_INFERENCE,
            importance=REPORT_CLAIM_IMPORTANCE_NORMAL,
            confidence=0.8,
            evidence_keys=feishu_keys,
            period_start=period_start_text,
            period_end=period_end_text,
        ),
        _claim_spec(
            claim_key="member_activity_breakdown",
            content=(
                "Member activity breakdown: "
                f"{breakdown_text or 'no member-level activity breakdown is available yet'}."
            ),
            claim_type=REPORT_CLAIM_TYPE_INFERENCE
            if breakdown_text
            else REPORT_CLAIM_TYPE_NEEDS_CONFIRMATION,
            importance=REPORT_CLAIM_IMPORTANCE_NORMAL,
            confidence=0.7 if breakdown_text else 0.45,
            evidence_keys=all_keys if all_keys else [],
            period_start=period_start_text,
            period_end=period_end_text,
        ),
    ]
    return claim_specs


def _claim_spec(
    *,
    claim_key: str,
    content: str,
    claim_type: str,
    importance: str,
    confidence: float,
    evidence_keys: Sequence[str],
    period_start: str,
    period_end: str,
) -> dict[str, object]:
    normalized_evidence_keys: list[str] = []
    seen_keys: set[str] = set()
    for key in evidence_keys:
        normalized_key = sanitize_prompt_identifier(key, max_length=128)
        if not normalized_key or normalized_key in seen_keys:
            continue
        seen_keys.add(normalized_key)
        normalized_evidence_keys.append(normalized_key)
    final_claim_type = claim_type
    final_confidence = confidence
    if not normalized_evidence_keys and importance != REPORT_CLAIM_IMPORTANCE_CRITICAL:
        final_claim_type = REPORT_CLAIM_TYPE_NEEDS_CONFIRMATION
        final_confidence = min(final_confidence, 0.45)
    return {
        "claim_key": sanitize_prompt_identifier(claim_key, max_length=128),
        "content": sanitize_prompt_text(content, max_length=512),
        "claim_type": final_claim_type,
        "importance": importance,
        "period_start": sanitize_prompt_identifier(period_start, max_length=32),
        "period_end": sanitize_prompt_identifier(period_end, max_length=32),
        "confidence": final_confidence,
        "evidence_keys": normalized_evidence_keys,
    }


def _build_summary(
    metric_values: Mapping[str, int],
    evidence_items: Sequence[Mapping[str, object]],
    member_activity_breakdown: Sequence[Mapping[str, object]],
) -> str:
    feishu_count = sum(
        1 for item in evidence_items if str(item.get("source_type")) == "feishu_bitable"
    )
    github_count = sum(1 for item in evidence_items if str(item.get("source_type")) == "github")
    member_count = len(member_activity_breakdown)
    return (
        f"Weekly structured report covers {len(evidence_items)} evidence items, "
        f"{feishu_count} Feishu records, "
        f"{github_count} GitHub records, "
        f"{metric_values.get('github_issue_total_count', 0)} issues, "
        f"{metric_values.get('github_pr_total_count', 0)} pull requests, "
        f"and {member_count} tracked contributors."
    )


def _format_member_activity_breakdown(
    member_activity_breakdown: Sequence[Mapping[str, object]],
) -> str:
    if not member_activity_breakdown:
        return ""
    parts: list[str] = []
    for item in member_activity_breakdown[:5]:
        member_id = sanitize_prompt_identifier(item.get("member_id"), max_length=80) or "unknown"
        task_count = _int_value(item.get("task_count"))
        issue_count = _int_value(item.get("issue_count"))
        overdue_count = _int_value(item.get("overdue_issue_count"))
        pr_count = _int_value(item.get("pull_request_count"))
        commit_count = _int_value(item.get("commit_count"))
        review_count = _int_value(item.get("review_count"))
        parts.append(
            f"{member_id}: tasks {task_count}, issues {issue_count}, overdue {overdue_count}, "
            f"PRs {pr_count}, commits {commit_count}, reviews {review_count}"
        )
    if len(member_activity_breakdown) > 5:
        parts.append(f"+{len(member_activity_breakdown) - 5} more")
    return "; ".join(parts)


def _period_text(
    explicit_value: date | None,
    evidence_items: Sequence[Mapping[str, object]],
    key: str,
) -> str:
    if explicit_value is not None:
        return sanitize_prompt_identifier(explicit_value.isoformat(), max_length=32)
    for item in evidence_items:
        value = item.get(key)
        if isinstance(value, str) and value:
            return sanitize_prompt_identifier(value[:10], max_length=32)
    return ""


def _normalize_metric_values(metric_values: Mapping[str, int]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key in METRIC_KEYS:
        value = metric_values.get(key)
        if not isinstance(value, int):
            raise ValueError(f"metric value for {key} must be int")
        normalized[key] = value
    return normalized


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0
