from datetime import datetime, timezone

from app.domain.source import (
    DEFAULT_FEISHU_RESOURCE_ID,
    DEFAULT_GITHUB_RESOURCE_ID,
    ENTITY_TYPE_FEISHU_RECORD,
    ENTITY_TYPE_GITHUB_ISSUE,
    SOURCE_TYPE_FEISHU_BITABLE,
    SOURCE_TYPE_GITHUB,
    build_batch_set_hash,
)
from app.reports.normalization import (
    build_entity_content_hash,
    build_snapshot_content_hash,
    build_source_batch_set_hash_from_batches,
    normalize_feishu_records,
    normalize_github_issue_records,
)


def test_normalization_filters_irrelevant_rows_and_builds_stable_hashes() -> None:
    fetched_at = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
    period_start = datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2026, 7, 27, 0, 0, tzinfo=timezone.utc)

    feishu_entities = normalize_feishu_records(
        [
            {
                "external_id": "feishu-1",
                "title": "Within period",
                "status": "success",
                "occurred_at": "2026-07-22T09:00:00+00:00",
            },
            {
                "external_id": "feishu-2",
                "title": "Outside period",
                "status": "success",
                "occurred_at": "2026-07-30T09:00:00+00:00",
            },
        ],
        source_batch_id="batch-feishu",
        source_resource_id=DEFAULT_FEISHU_RESOURCE_ID,
        fetched_at=fetched_at,
        period_start=period_start,
        period_end=period_end,
    )
    github_entities = normalize_github_issue_records(
        [
            {
                "external_id": "issue-1",
                "number": 1,
                "title": "Keep this issue",
                "status": "open",
                "occurred_at": "2026-07-22T12:00:00+00:00",
                "html_url": "https://example.test/issues/1",
            },
            {
                "external_id": "issue-pr-2",
                "number": 2,
                "title": "Drop pull request",
                "status": "open",
                "pull_request": True,
                "occurred_at": "2026-07-23T12:00:00+00:00",
            },
        ],
        source_batch_id="batch-github",
        source_resource_id=DEFAULT_GITHUB_RESOURCE_ID,
        fetched_at=fetched_at,
        period_start=period_start,
        period_end=period_end,
    )

    assert len(feishu_entities) == 1
    assert len(github_entities) == 1
    assert feishu_entities[0]["source_type"] == SOURCE_TYPE_FEISHU_BITABLE
    assert feishu_entities[0]["entity_type"] == ENTITY_TYPE_FEISHU_RECORD
    assert github_entities[0]["source_type"] == SOURCE_TYPE_GITHUB
    assert github_entities[0]["entity_type"] == ENTITY_TYPE_GITHUB_ISSUE
    assert feishu_entities[0]["content_hash"] == build_entity_content_hash(feishu_entities[0])
    assert github_entities[0]["content_hash"] == build_entity_content_hash(github_entities[0])

    snapshot_hash_a = build_snapshot_content_hash(
        source_batch_set_hash=build_source_batch_set_hash_from_batches(
            [{"payload_hash": "hash-feishu"}, {"payload_hash": "hash-github"}]
        ),
        mapping_revision="1",
        entities=[feishu_entities[0], github_entities[0]],
    )
    snapshot_hash_b = build_snapshot_content_hash(
        source_batch_set_hash=build_source_batch_set_hash_from_batches(
            [{"payload_hash": "hash-github"}, {"payload_hash": "hash-feishu"}]
        ),
        mapping_revision="1",
        entities=[github_entities[0], feishu_entities[0]],
    )

    assert snapshot_hash_a == snapshot_hash_b
    assert build_batch_set_hash(["hash-feishu", "hash-github"]) == build_batch_set_hash(
        ["hash-github", "hash-feishu"]
    )
