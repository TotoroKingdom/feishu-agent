from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from app.domain.source import canonical_json_hash
from app.llm.policies import sanitize_prompt_text

RENDERING_VERSION: Final[str] = "minimal.v1"

_METRIC_LABELS: Final[dict[str, str]] = {
    "github_issue_total_count": "New GitHub issues",
    "github_issue_open_count": "Open GitHub issues",
    "github_issue_closed_count": "Closed GitHub issues",
    "github_issue_overdue_count": "Overdue GitHub issues",
    "github_pr_total_count": "GitHub pull requests",
    "github_pr_merged_count": "Merged GitHub pull requests",
    "github_pr_long_review_count": "Long-review GitHub pull requests",
    "github_commit_count": "GitHub commits",
    "active_contributor_count": "Active contributors",
    "milestone_completion_rate": "Milestone completion rate (%)",
    "plan_task_completion_rate": "Plan task completion rate (%)",
}


@dataclass(slots=True)
class RenderedReport:
    rendered_content: str
    rendered_content_hash: str
    line_count: int


def render_verified_report(
    structured_report: Mapping[str, object],
    *,
    evidence_items: Sequence[Mapping[str, object]],
    report_version: int = 1,
) -> RenderedReport:
    report_title = sanitize_prompt_text(
        structured_report.get("report_title"), max_length=128
    ) or "Weekly Structured Report"
    summary = sanitize_prompt_text(structured_report.get("summary"), max_length=1024)
    period_start = sanitize_prompt_text(structured_report.get("period_start"), max_length=32)
    period_end = sanitize_prompt_text(structured_report.get("period_end"), max_length=32)
    metrics = _as_metrics(structured_report.get("metrics"))
    claims = _as_claims(structured_report.get("claims"))
    evidence_by_key = {
        str(item.get("evidence_key")): dict(item)
        for item in evidence_items
        if isinstance(item.get("evidence_key"), str)
    }

    lines: list[str] = [
        report_title,
        "=" * len(report_title),
        f"Period: {period_start} to {period_end}",
        "",
        "Summary",
        summary,
        "",
        "Metrics",
    ]
    for metric_key in sorted(metrics):
        metric_value = metrics[metric_key]
        lines.append(f"- {_metric_label(metric_key)}: {metric_value}")

    lines.extend(["", "Claims"])
    for index, claim in enumerate(claims, start=1):
        claim_key = sanitize_prompt_text(claim.get("claim_key"), max_length=128) or f"claim-{index}"
        claim_content = sanitize_prompt_text(claim.get("content"), max_length=512)
        claim_type = sanitize_prompt_text(claim.get("claim_type"), max_length=32) or "fact"
        importance = sanitize_prompt_text(claim.get("importance"), max_length=32) or "normal"
        evidence_keys = _claim_evidence_keys(claim)
        evidence_text = (
            "none"
            if not evidence_keys
            else ", ".join(
                _format_evidence_ref(evidence_key, evidence_by_key.get(evidence_key))
                for evidence_key in evidence_keys
            )
        )
        lines.append(f"{index}. [{importance}] {claim_content}")
        lines.append(f"   Claim key: {claim_key} ({claim_type})")
        lines.append(f"   Evidence: {evidence_text}")

    rendered_content = "\n".join(lines).rstrip() + "\n"
    rendered_content_hash = canonical_json_hash(
        {
            "rendering_version": RENDERING_VERSION,
            "report_version": report_version,
            "structured_hash": str(structured_report.get("structured_hash") or ""),
            "rendered_content": rendered_content,
        }
    )
    return RenderedReport(
        rendered_content=rendered_content,
        rendered_content_hash=rendered_content_hash,
        line_count=len(lines),
    )


def _as_metrics(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    metrics: dict[str, int] = {}
    for key, metric_value in value.items():
        if isinstance(metric_value, int):
            metrics[str(key)] = metric_value
    return metrics


def _as_claims(value: object) -> list[dict[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    claims: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, Mapping):
            claims.append(dict(item))
    return claims


def _claim_evidence_keys(claim: Mapping[str, object]) -> list[str]:
    values = claim.get("evidence_keys", [])
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return [sanitize_prompt_text(value, max_length=128) for value in values if isinstance(value, str) and value]


def _format_evidence_ref(evidence_key: str, evidence_item: Mapping[str, object] | None) -> str:
    if evidence_item is None:
        return evidence_key
    summary = sanitize_prompt_text(evidence_item.get("evidence_summary"), max_length=256)
    if summary:
        return f"{evidence_key} ({summary})"
    return evidence_key


def _metric_label(metric_key: str) -> str:
    label = _METRIC_LABELS.get(metric_key)
    if label is not None:
        return label
    return metric_key.replace("_", " ").title()
