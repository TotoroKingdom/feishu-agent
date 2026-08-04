from __future__ import annotations

from datetime import date

from app.reports.generation import (
    build_structured_report_payload,
    validate_structured_report_payload,
)
from app.reports.grounding import verify_structured_report_grounding


def test_grounding_quality_golden_passes() -> None:
    validated, evidence_items = _validated_report()
    result = verify_structured_report_grounding(
        validated,
        evidence_items=evidence_items,
        period_start=_period_start(),
        period_end=_period_end(),
    )

    assert result.status == "pass"
    assert result.grounded_claim_count == 12


def test_grounding_quality_conflict_blocks_tampered_claim() -> None:
    validated, evidence_items = _validated_report()
    validated["claims"][1]["content"] = "Tampered content"  # type: ignore[index]

    result = verify_structured_report_grounding(
        validated,
        evidence_items=evidence_items,
        period_start=_period_start(),
        period_end=_period_end(),
    )

    assert result.status == "blocked"
    assert result.error_code == "CLAIM_CONTENT_MISMATCH"


def test_grounding_quality_partial_data_downgrades_noncritical_claims() -> None:
    validated, evidence_items = _validated_report(include_feishu=False)
    result = verify_structured_report_grounding(
        validated,
        evidence_items=evidence_items,
        period_start=_period_start(),
        period_end=_period_end(),
    )

    assert result.status == "pass"
    assert result.claim_statuses is not None
    assert result.claim_statuses["plan_task_completion_rate"] == "downgraded"


def test_grounding_quality_blocks_critical_claim_without_evidence() -> None:
    validated, evidence_items = _validated_report(include_github=False)
    result = verify_structured_report_grounding(
        validated,
        evidence_items=evidence_items,
        period_start=_period_start(),
        period_end=_period_end(),
    )

    assert result.status == "blocked"
    assert result.error_code == "GROUNDING_CRITICAL_CLAIM_UNGROUNDED"


def _validated_report(
    *,
    include_github: bool = True,
    include_feishu: bool = True,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    evidence_items = _evidence_items(include_github=include_github, include_feishu=include_feishu)
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
        metric_values=_metric_values(include_github=include_github, include_feishu=include_feishu),
        member_activity_breakdown=_member_activity_breakdown(
            include_github=include_github, include_feishu=include_feishu
        ),
    )
    validated = validate_structured_report_payload(
        payload,
        expected_metric_values=_metric_values(
            include_github=include_github, include_feishu=include_feishu
        ),
        allowed_evidence_keys=[item["evidence_key"] for item in evidence_items],
        expected_data_snapshot_hash="data-snapshot-hash",
    )
    return validated, evidence_items


def _metric_values(*, include_github: bool, include_feishu: bool) -> dict[str, int]:
    if include_github and include_feishu:
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
    if include_github:
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
            "plan_task_completion_rate": 0,
        }
    if include_feishu:
        return {
            "github_issue_total_count": 0,
            "github_issue_open_count": 0,
            "github_issue_closed_count": 0,
            "github_issue_overdue_count": 0,
            "github_pr_total_count": 0,
            "github_pr_merged_count": 0,
            "github_pr_long_review_count": 0,
            "github_commit_count": 0,
            "active_contributor_count": 2,
            "milestone_completion_rate": 0,
            "plan_task_completion_rate": 100,
        }
    return {
        "github_issue_total_count": 0,
        "github_issue_open_count": 0,
        "github_issue_closed_count": 0,
        "github_issue_overdue_count": 0,
        "github_pr_total_count": 0,
        "github_pr_merged_count": 0,
        "github_pr_long_review_count": 0,
        "github_commit_count": 0,
        "active_contributor_count": 0,
        "milestone_completion_rate": 0,
        "plan_task_completion_rate": 0,
    }


def _member_activity_breakdown(
    *, include_github: bool, include_feishu: bool
) -> list[dict[str, object]]:
    if include_github and include_feishu:
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
    if include_github:
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
                "task_count": 0,
                "issue_count": 0,
                "overdue_issue_count": 0,
                "pull_request_count": 1,
                "commit_count": 0,
                "review_count": 0,
                "total_activity_count": 1,
            },
        ]
    return [
        {
            "member_id": "user-a",
            "task_count": 1,
            "issue_count": 0,
            "overdue_issue_count": 0,
            "pull_request_count": 0,
            "commit_count": 0,
            "review_count": 0,
            "total_activity_count": 1,
        },
        {
            "member_id": "user-b",
            "task_count": 1,
            "issue_count": 0,
            "overdue_issue_count": 0,
            "pull_request_count": 0,
            "commit_count": 0,
            "review_count": 0,
            "total_activity_count": 1,
        },
    ]


def _evidence_items(
    *,
    include_github: bool,
    include_feishu: bool,
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    if include_feishu:
        items.extend(
            [
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
            ]
        )
    if include_github:
        items.extend(
            [
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
        )
    return items


def _period_start() -> date:
    return date(2026, 7, 20)


def _period_end() -> date:
    return date(2026, 7, 27)
