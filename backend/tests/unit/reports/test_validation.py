from datetime import datetime, timezone

from app.domain.source import DEFAULT_FEISHU_RESOURCE_ID, DEFAULT_GITHUB_RESOURCE_ID
from app.reports.normalization import normalize_feishu_records, normalize_github_issue_records
from app.reports.validation import validate_normalized_entities


def test_validation_passes_for_happy_normalized_entities() -> None:
    fetched_at = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
    period_start = datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2026, 7, 27, 0, 0, tzinfo=timezone.utc)

    entities = normalize_feishu_records(
        [
            {
                "external_id": "feishu-1",
                "title": "Milestone ready",
                "status": "success",
                "occurred_at": "2026-07-22T09:00:00+00:00",
            }
        ],
        source_batch_id="batch-feishu",
        source_resource_id=DEFAULT_FEISHU_RESOURCE_ID,
        fetched_at=fetched_at,
        period_start=period_start,
        period_end=period_end,
    )
    entities.extend(
        normalize_github_issue_records(
            [
                {
                    "external_id": "issue-1",
                    "number": 1,
                    "title": "Fix flaky test",
                    "status": "open",
                    "occurred_at": "2026-07-22T12:00:00+00:00",
                }
            ],
            source_batch_id="batch-github",
            source_resource_id=DEFAULT_GITHUB_RESOURCE_ID,
            fetched_at=fetched_at,
            period_start=period_start,
            period_end=period_end,
        )
    )

    outcome = validate_normalized_entities(entities, input_snapshot_hash="snapshot-hash")

    assert outcome.validation_pass is True
    assert outcome.data_quality_status == "complete"
    assert outcome.critical_count == 0
    assert outcome.warning_count == 0
    assert outcome.missing_items == []
    assert outcome.conflicts == []


def test_validation_blocks_missing_sources() -> None:
    outcome = validate_normalized_entities([], input_snapshot_hash="snapshot-hash")

    assert outcome.validation_pass is False
    assert outcome.data_quality_status == "blocked"
    assert outcome.critical_count == 2
    assert "feishu_records_missing" in outcome.missing_items
    assert "github_issues_missing" in outcome.missing_items


def test_validation_blocks_failed_or_pr_payloads() -> None:
    outcome = validate_normalized_entities(
        [
            {
                "source_type": "github",
                "entity_type": "github_issue",
                "source_resource_id": DEFAULT_GITHUB_RESOURCE_ID,
                "external_id": "issue-1",
                "title": "Broken record",
                "state": "failed",
                "attributes": {"pull_request": True},
            },
            {
                "source_type": "feishu_bitable",
                "entity_type": "feishu_record",
                "source_resource_id": DEFAULT_FEISHU_RESOURCE_ID,
                "external_id": "feishu-1",
                "title": "Still needed",
                "state": "success",
                "attributes": {},
            },
        ],
        input_snapshot_hash="snapshot-hash",
    )

    assert outcome.validation_pass is False
    assert outcome.data_quality_status == "blocked"
    assert outcome.critical_count >= 1
    assert any(item.startswith("github:github_issue:state:failed") for item in outcome.missing_items)
    assert any(item.endswith("pull_request_excluded") for item in outcome.missing_items)
