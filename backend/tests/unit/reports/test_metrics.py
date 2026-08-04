from datetime import date

from app.domain.metrics import (
    METRIC_ACTIVE_CONTRIBUTOR_COUNT,
    METRIC_GITHUB_COMMIT_COUNT,
    METRIC_GITHUB_ISSUE_CLOSED_COUNT,
    METRIC_GITHUB_ISSUE_OPEN_COUNT,
    METRIC_GITHUB_ISSUE_OVERDUE_COUNT,
    METRIC_GITHUB_ISSUE_TOTAL_COUNT,
    METRIC_GITHUB_PR_LONG_REVIEW_COUNT,
    METRIC_GITHUB_PR_MERGED_COUNT,
    METRIC_GITHUB_PR_TOTAL_COUNT,
    METRIC_KEYS,
    METRIC_MILESTONE_COMPLETION_RATE,
    METRIC_PLAN_TASK_COMPLETION_RATE,
)
from app.reports.metrics import calculate_metric_payload, extract_metric_values


def test_metric_payload_is_deterministic_for_duplicates_and_ordering() -> None:
    period_start = date(2026, 7, 20)
    period_end = date(2026, 7, 27)
    entities = _entities()

    payload_a = calculate_metric_payload(entities, period_start=period_start, period_end=period_end)
    payload_b = calculate_metric_payload(
        list(reversed(entities)), period_start=period_start, period_end=period_end
    )

    assert payload_a["content_hash"] == payload_b["content_hash"]
    assert payload_a["definition_version"] == payload_b["definition_version"]
    assert payload_a["metric_keys"] == list(METRIC_KEYS)
    assert extract_metric_values(payload_a) == {
        METRIC_GITHUB_ISSUE_TOTAL_COUNT: 3,
        METRIC_GITHUB_ISSUE_OPEN_COUNT: 2,
        METRIC_GITHUB_ISSUE_CLOSED_COUNT: 1,
        METRIC_GITHUB_ISSUE_OVERDUE_COUNT: 1,
        METRIC_GITHUB_PR_TOTAL_COUNT: 1,
        METRIC_GITHUB_PR_MERGED_COUNT: 0,
        METRIC_GITHUB_PR_LONG_REVIEW_COUNT: 0,
        METRIC_GITHUB_COMMIT_COUNT: 1,
        METRIC_ACTIVE_CONTRIBUTOR_COUNT: 7,
        METRIC_MILESTONE_COMPLETION_RATE: 33,
        METRIC_PLAN_TASK_COMPLETION_RATE: 100,
    }

    breakdown = payload_a["member_activity_breakdown"]
    assert isinstance(breakdown, list)
    assert [entry["member_id"] for entry in breakdown[:2]] == ["contributor-a", "contributor-b"]
    assert breakdown[0]["total_activity_count"] == 2
    assert breakdown[1]["total_activity_count"] == 2


def test_metric_payload_handles_empty_snapshot() -> None:
    payload = calculate_metric_payload(
        [], period_start=date(2026, 7, 20), period_end=date(2026, 7, 27)
    )

    assert extract_metric_values(payload) == {
        METRIC_GITHUB_ISSUE_TOTAL_COUNT: 0,
        METRIC_GITHUB_ISSUE_OPEN_COUNT: 0,
        METRIC_GITHUB_ISSUE_CLOSED_COUNT: 0,
        METRIC_GITHUB_ISSUE_OVERDUE_COUNT: 0,
        METRIC_GITHUB_PR_TOTAL_COUNT: 0,
        METRIC_GITHUB_PR_MERGED_COUNT: 0,
        METRIC_GITHUB_PR_LONG_REVIEW_COUNT: 0,
        METRIC_GITHUB_COMMIT_COUNT: 0,
        METRIC_ACTIVE_CONTRIBUTOR_COUNT: 0,
        METRIC_MILESTONE_COMPLETION_RATE: 0,
        METRIC_PLAN_TASK_COMPLETION_RATE: 0,
    }
    assert payload["member_activity_breakdown"] == []
    assert isinstance(payload["content_hash"], str)
    assert payload["content_hash"]


def _entities() -> list[dict[str, object]]:
    return [
        _feishu_record("feishu-1", "success", "user-a", "2026-07-22T09:00:00+00:00"),
        _feishu_record("feishu-2", "success", "user-b", "2026-07-23T09:00:00+00:00"),
        _github_issue("issue-1", "open", "2026-07-22T09:00:00+00:00", "contributor-a"),
        _github_issue("issue-2", "closed", "2026-07-23T09:00:00+00:00", "contributor-b"),
        _github_issue(
            "issue-3",
            "open",
            "2026-07-24T09:00:00+00:00",
            "contributor-c",
            updated_at_external="2026-07-10T09:00:00+00:00",
        ),
        _github_issue(
            "issue-3",
            "open",
            "2026-07-24T09:00:00+00:00",
            "contributor-c",
            updated_at_external="2026-07-10T09:00:00+00:00",
        ),
        _github_pull_request(
            "pr-1",
            "open",
            "2026-07-23T09:00:00+00:00",
            "contributor-b",
            latest_review_state="approved",
            review_count=2,
        ),
        _github_commit("commit-1", "2026-07-22T08:00:00+00:00", "contributor-a"),
        _github_review("review-1", "reviewer-a", "2026-07-23T13:00:00+00:00"),
        _github_review("review-2", "reviewer-b", "2026-07-23T14:00:00+00:00"),
        _github_milestone("milestone-1", 1, 2, "2026-07-24T10:00:00+00:00"),
        _github_contributor("contributor-a"),
        _github_contributor("contributor-b"),
    ]


def _feishu_record(
    external_id: str,
    status: str,
    author_external_id: str,
    occurred_at: str,
) -> dict[str, object]:
    return {
        "source_type": "feishu_bitable",
        "entity_type": "feishu_record",
        "source_resource_id": "feishu-table-example",
        "external_id": external_id,
        "state": status,
        "author_external_id": author_external_id,
        "occurred_at": occurred_at,
        "content_hash": f"hash-{external_id}",
    }


def _github_issue(
    external_id: str,
    state: str,
    occurred_at: str,
    author_external_id: str,
    *,
    updated_at_external: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_type": "github",
        "entity_type": "github_issue",
        "source_resource_id": "github-repository-example",
        "external_id": external_id,
        "state": state,
        "author_external_id": author_external_id,
        "occurred_at": occurred_at,
        "content_hash": f"hash-{external_id}",
    }
    if updated_at_external is not None:
        payload["updated_at_external"] = updated_at_external
    return payload


def _github_pull_request(
    external_id: str,
    state: str,
    occurred_at: str,
    author_external_id: str,
    *,
    latest_review_state: str,
    review_count: int,
) -> dict[str, object]:
    return {
        "source_type": "github",
        "entity_type": "github_pull_request",
        "source_resource_id": "github-repository-example",
        "external_id": external_id,
        "state": state,
        "author_external_id": author_external_id,
        "occurred_at": occurred_at,
        "attributes": {
            "latest_review_state": latest_review_state,
            "review_count": review_count,
        },
        "content_hash": f"hash-{external_id}",
    }


def _github_commit(
    external_id: str,
    occurred_at: str,
    author_external_id: str,
) -> dict[str, object]:
    return {
        "source_type": "github",
        "entity_type": "github_commit",
        "source_resource_id": "github-repository-example",
        "external_id": external_id,
        "state": "committed",
        "author_external_id": author_external_id,
        "occurred_at": occurred_at,
        "content_hash": f"hash-{external_id}",
    }


def _github_review(
    external_id: str,
    author_external_id: str,
    occurred_at: str,
) -> dict[str, object]:
    return {
        "source_type": "github",
        "entity_type": "github_review",
        "source_resource_id": "github-repository-example",
        "external_id": external_id,
        "state": "approved",
        "author_external_id": author_external_id,
        "occurred_at": occurred_at,
        "content_hash": f"hash-{external_id}",
    }


def _github_milestone(
    external_id: str,
    closed_issues: int,
    open_issues: int,
    occurred_at: str,
) -> dict[str, object]:
    return {
        "source_type": "github",
        "entity_type": "github_milestone",
        "source_resource_id": "github-repository-example",
        "external_id": external_id,
        "state": "open",
        "occurred_at": occurred_at,
        "attributes": {
            "closed_issues": closed_issues,
            "open_issues": open_issues,
        },
        "content_hash": f"hash-{external_id}",
    }


def _github_contributor(login: str) -> dict[str, object]:
    return {
        "source_type": "github",
        "entity_type": "github_contributor",
        "source_resource_id": "github-repository-example",
        "external_id": login,
        "state": "active",
        "author_external_id": login,
        "content_hash": f"hash-{login}",
    }
