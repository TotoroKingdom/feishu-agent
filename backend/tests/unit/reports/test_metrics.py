from datetime import date, datetime, timezone

from app.domain.metrics import (
    METRIC_ACTIVE_CONTRIBUTOR_COUNT,
    METRIC_GITHUB_ISSUE_CLOSED_COUNT,
    METRIC_GITHUB_ISSUE_OPEN_COUNT,
    METRIC_GITHUB_ISSUE_OVERDUE_COUNT,
    METRIC_GITHUB_ISSUE_TOTAL_COUNT,
)
from app.reports.metrics import calculate_metric_payload, extract_metric_values


def test_metric_payload_is_deterministic_for_duplicates_and_ordering() -> None:
    period_start = date(2026, 7, 20)
    period_end = date(2026, 7, 27)
    entities = [
        _github_issue(
            "issue-1",
            "open",
            "2026-07-22T09:00:00+00:00",
            "contributor-a",
        ),
        _github_issue(
            "issue-2",
            "closed",
            "2026-07-23T09:00:00+00:00",
            "contributor-b",
        ),
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
        _github_issue(
            "issue-4",
            "open",
            "2026-07-29T09:00:00+00:00",
            "contributor-d",
        ),
    ]

    payload_a = calculate_metric_payload(entities, period_start=period_start, period_end=period_end)
    payload_b = calculate_metric_payload(
        list(reversed(entities)), period_start=period_start, period_end=period_end
    )

    assert payload_a["content_hash"] == payload_b["content_hash"]
    assert payload_a["definition_version"] == payload_b["definition_version"]
    assert extract_metric_values(payload_a) == {
        METRIC_GITHUB_ISSUE_TOTAL_COUNT: 3,
        METRIC_GITHUB_ISSUE_OPEN_COUNT: 2,
        METRIC_GITHUB_ISSUE_CLOSED_COUNT: 1,
        METRIC_GITHUB_ISSUE_OVERDUE_COUNT: 1,
        METRIC_ACTIVE_CONTRIBUTOR_COUNT: 3,
    }


def test_metric_payload_handles_empty_snapshot() -> None:
    payload = calculate_metric_payload([], period_start=date(2026, 7, 20), period_end=date(2026, 7, 27))

    assert extract_metric_values(payload) == {
        METRIC_GITHUB_ISSUE_TOTAL_COUNT: 0,
        METRIC_GITHUB_ISSUE_OPEN_COUNT: 0,
        METRIC_GITHUB_ISSUE_CLOSED_COUNT: 0,
        METRIC_GITHUB_ISSUE_OVERDUE_COUNT: 0,
        METRIC_ACTIVE_CONTRIBUTOR_COUNT: 0,
    }
    assert isinstance(payload["content_hash"], str)
    assert payload["content_hash"]


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
