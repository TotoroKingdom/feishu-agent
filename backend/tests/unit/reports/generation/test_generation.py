from __future__ import annotations

from datetime import date

import pytest

from app.reports.generation import (
    build_claim_evidence_map,
    build_structured_report_hash,
    build_structured_report_payload,
    validate_structured_report_payload,
)


def test_structured_report_payload_validates_and_preserves_metrics() -> None:
    evidence_items = _evidence_items()
    metric_values = _metric_values()
    member_activity_breakdown = _member_activity_breakdown()

    payload = build_structured_report_payload(
        run_id="run-123",
        period_start=_period_start(),
        period_end=_period_end(),
        metric_snapshot_ref="metric-snapshot-1",
        evidence_set_ref="evidence-set-1",
        data_snapshot_hash="data-snapshot-hash",
        metric_snapshot_content_hash="metric-snapshot-hash",
        evidence_set_content_hash="evidence-set-hash",
        validation_status="complete",
        evidence_items=evidence_items,
        metric_values=metric_values,
        member_activity_breakdown=member_activity_breakdown,
    )
    validated = validate_structured_report_payload(
        payload,
        expected_metric_values=metric_values,
        allowed_evidence_keys=[item["evidence_key"] for item in evidence_items],
        expected_data_snapshot_hash="data-snapshot-hash",
    )

    assert validated["metrics"] == metric_values
    assert validated["structured_hash"] == build_structured_report_hash(validated)
    assert validated["member_activity_breakdown"] == member_activity_breakdown
    assert validated["claims"][0]["period_start"] == _period_start().isoformat()
    assert validated["claims"][0]["period_end"] == _period_end().isoformat()
    assert build_claim_evidence_map(validated["claims"])["github_issue_summary"] == [
        "github:issue-1",
        "github:issue-2",
    ]


def test_structured_report_payload_rejects_metric_tampering() -> None:
    evidence_items = _evidence_items()
    metric_values = _metric_values()
    payload = build_structured_report_payload(
        run_id="run-123",
        period_start=_period_start(),
        period_end=_period_end(),
        metric_snapshot_ref="metric-snapshot-1",
        evidence_set_ref="evidence-set-1",
        data_snapshot_hash="data-snapshot-hash",
        metric_snapshot_content_hash="metric-snapshot-hash",
        evidence_set_content_hash="evidence-set-hash",
        validation_status="complete",
        evidence_items=evidence_items,
        metric_values=metric_values,
        member_activity_breakdown=_member_activity_breakdown(),
    )
    payload["metrics"]["github_issue_total_count"] = 99  # type: ignore[index]

    with pytest.raises(ValueError, match="metrics do not match"):
        validate_structured_report_payload(
            payload,
            expected_metric_values=metric_values,
            allowed_evidence_keys=[item["evidence_key"] for item in evidence_items],
            expected_data_snapshot_hash="data-snapshot-hash",
        )


def test_structured_report_payload_rejects_unknown_evidence_keys() -> None:
    evidence_items = _evidence_items()
    metric_values = _metric_values()
    payload = build_structured_report_payload(
        run_id="run-123",
        period_start=_period_start(),
        period_end=_period_end(),
        metric_snapshot_ref="metric-snapshot-1",
        evidence_set_ref="evidence-set-1",
        data_snapshot_hash="data-snapshot-hash",
        metric_snapshot_content_hash="metric-snapshot-hash",
        evidence_set_content_hash="evidence-set-hash",
        validation_status="complete",
        evidence_items=evidence_items,
        metric_values=metric_values,
        member_activity_breakdown=_member_activity_breakdown(),
    )
    payload["claims"][0]["evidence_keys"] = ["unknown-evidence"]  # type: ignore[index]

    with pytest.raises(ValueError, match="unknown evidence keys"):
        validate_structured_report_payload(
            payload,
            expected_metric_values=metric_values,
            allowed_evidence_keys=[item["evidence_key"] for item in evidence_items],
            expected_data_snapshot_hash="data-snapshot-hash",
        )


def _metric_values() -> dict[str, int]:
    return {
        "github_issue_total_count": 2,
        "github_issue_open_count": 1,
        "github_issue_closed_count": 1,
        "github_issue_overdue_count": 0,
        "github_pr_total_count": 1,
        "github_pr_merged_count": 1,
        "github_pr_long_review_count": 0,
        "github_commit_count": 3,
        "active_contributor_count": 4,
        "milestone_completion_rate": 50,
        "plan_task_completion_rate": 100,
    }


def _member_activity_breakdown() -> list[dict[str, object]]:
    return [
        {
            "member_id": "contributor-a",
            "task_count": 0,
            "issue_count": 1,
            "overdue_issue_count": 0,
            "pull_request_count": 0,
            "commit_count": 1,
            "review_count": 0,
            "total_activity_count": 2,
        },
        {
            "member_id": "contributor-b",
            "task_count": 1,
            "issue_count": 0,
            "overdue_issue_count": 0,
            "pull_request_count": 1,
            "commit_count": 0,
            "review_count": 0,
            "total_activity_count": 2,
        },
    ]


def _evidence_items() -> list[dict[str, object]]:
    return [
        {
            "evidence_key": "feishu:record-1",
            "source_type": "feishu_bitable",
            "source_resource_id": "feishu-table-example",
            "external_id": "record-1",
            "url": None,
            "period_start": "2026-07-20T00:00:00+00:00",
            "period_end": "2026-07-27T00:00:00+00:00",
            "evidence_summary": "Feishu 1",
            "confidence": 1.0,
            "normalized_entity_id": "entity-feishu-1",
            "content_hash": "hash-feishu-1",
            "state": "success",
            "is_overdue": False,
        },
        {
            "evidence_key": "feishu:record-2",
            "source_type": "feishu_bitable",
            "source_resource_id": "feishu-table-example",
            "external_id": "record-2",
            "url": None,
            "period_start": "2026-07-20T00:00:00+00:00",
            "period_end": "2026-07-27T00:00:00+00:00",
            "evidence_summary": "Feishu 2",
            "confidence": 1.0,
            "normalized_entity_id": "entity-feishu-2",
            "content_hash": "hash-feishu-2",
            "state": "success",
            "is_overdue": False,
        },
        {
            "evidence_key": "github:issue-1",
            "source_type": "github",
            "source_resource_id": "github-repository-example",
            "external_id": "issue-1",
            "url": "https://example.test/issues/1",
            "period_start": "2026-07-20T00:00:00+00:00",
            "period_end": "2026-07-27T00:00:00+00:00",
            "evidence_summary": "Issue 1",
            "confidence": 0.95,
            "normalized_entity_id": "entity-github-1",
            "content_hash": "hash-github-1",
            "state": "open",
            "is_overdue": False,
        },
        {
            "evidence_key": "github:issue-2",
            "source_type": "github",
            "source_resource_id": "github-repository-example",
            "external_id": "issue-2",
            "url": "https://example.test/issues/2",
            "period_start": "2026-07-20T00:00:00+00:00",
            "period_end": "2026-07-27T00:00:00+00:00",
            "evidence_summary": "Issue 2",
            "confidence": 0.95,
            "normalized_entity_id": "entity-github-2",
            "content_hash": "hash-github-2",
            "state": "closed",
            "is_overdue": False,
        },
    ]


def _period_start() -> date:
    return date(2026, 7, 20)


def _period_end() -> date:
    return date(2026, 7, 27)
