from __future__ import annotations

from datetime import UTC, datetime

from app.domain.source import (
    DEFAULT_GITHUB_RESOURCE_ID,
    ENTITY_TYPE_GITHUB_COMMIT,
    ENTITY_TYPE_GITHUB_CONTRIBUTOR,
    ENTITY_TYPE_GITHUB_ISSUE,
    ENTITY_TYPE_GITHUB_MILESTONE,
    ENTITY_TYPE_GITHUB_PULL_REQUEST,
    ENTITY_TYPE_GITHUB_REPOSITORY,
    ENTITY_TYPE_GITHUB_REVIEW,
    SOURCE_TYPE_GITHUB,
)
from app.reports.normalization import (
    build_entity_content_hash,
    build_snapshot_content_hash,
    build_source_batch_set_hash_from_batches,
    normalize_github_commit_records,
    normalize_github_contributor_records,
    normalize_github_issue_records,
    normalize_github_milestone_records,
    normalize_github_pull_request_records,
    normalize_github_repository_record,
    normalize_github_review_records,
)


def test_github_core_entity_normalization_covers_repository_activity() -> None:
    fetched_at = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
    period_start = datetime(2026, 7, 20, 0, 0, tzinfo=UTC)
    period_end = datetime(2026, 7, 27, 0, 0, tzinfo=UTC)

    repository_entities = normalize_github_repository_record(
        {
            "id": "repo-1",
            "full_name": "acme/demo",
            "name": "demo",
            "archived": False,
            "updated_at": "2026-07-24T10:00:00+00:00",
            "open_issues_count": 2,
        },
        source_batch_id="batch-github",
        source_resource_id=DEFAULT_GITHUB_RESOURCE_ID,
        fetched_at=fetched_at,
        period_start=period_start,
        period_end=period_end,
    )
    issue_entities = normalize_github_issue_records(
        [
            {
                "external_id": "issue-1",
                "number": 1,
                "title": "Fix flaky test",
                "status": "open",
                "author_external_id": "contributor-a",
                "occurred_at": "2026-07-22T12:00:00+00:00",
            },
            {
                "external_id": "issue-pr-2",
                "number": 2,
                "title": "Add report export",
                "status": "open",
                "author_external_id": "contributor-b",
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
    pull_request_entities = normalize_github_pull_request_records(
        [
            {
                "external_id": "pr-2",
                "number": 2,
                "title": "Add report export",
                "status": "open",
                "author_external_id": "contributor-b",
                "occurred_at": "2026-07-23T12:00:00+00:00",
                "latest_review_state": "approved",
                "review_count": 2,
            }
        ],
        source_batch_id="batch-github",
        source_resource_id=DEFAULT_GITHUB_RESOURCE_ID,
        fetched_at=fetched_at,
        period_start=period_start,
        period_end=period_end,
    )
    commit_entities = normalize_github_commit_records(
        [
            {
                "external_id": "commit-1",
                "sha": "aaa111",
                "message": "Refine report metrics",
                "status": "complete",
                "author_external_id": "contributor-a",
                "occurred_at": "2026-07-22T08:00:00+00:00",
                "commit": {
                    "message": "Refine report metrics\n\nKeep calculations stable.",
                    "author": {
                        "login": "contributor-a",
                        "date": "2026-07-22T08:00:00+00:00",
                    },
                },
            }
        ],
        source_batch_id="batch-github",
        source_resource_id=DEFAULT_GITHUB_RESOURCE_ID,
        fetched_at=fetched_at,
        period_start=period_start,
        period_end=period_end,
    )
    review_entities = normalize_github_review_records(
        [
            {
                "external_id": "review-1",
                "id": 101,
                "state": "APPROVED",
                "pull_request": {"number": 2, "title": "Add report export"},
                "user": {"login": "reviewer-a"},
                "submitted_at": "2026-07-23T13:00:00+00:00",
            }
        ],
        source_batch_id="batch-github",
        source_resource_id=DEFAULT_GITHUB_RESOURCE_ID,
        fetched_at=fetched_at,
        period_start=period_start,
        period_end=period_end,
    )
    milestone_entities = normalize_github_milestone_records(
        [
            {
                "external_id": "milestone-1",
                "id": 201,
                "number": 1,
                "title": "Release 1.0",
                "status": "open",
                "occurred_at": "2026-07-24T10:00:00+00:00",
            }
        ],
        source_batch_id="batch-github",
        source_resource_id=DEFAULT_GITHUB_RESOURCE_ID,
        fetched_at=fetched_at,
        period_start=period_start,
        period_end=period_end,
    )
    contributor_entities = normalize_github_contributor_records(
        [
            {
                "external_id": "contributor-a",
                "login": "contributor-a",
                "name": "Contributor A",
                "status": "active",
                "contributions": 12,
            }
        ],
        source_batch_id="batch-github",
        source_resource_id=DEFAULT_GITHUB_RESOURCE_ID,
        fetched_at=fetched_at,
        period_start=period_start,
        period_end=period_end,
    )

    assert len(repository_entities) == 1
    assert len(issue_entities) == 1
    assert len(pull_request_entities) == 1
    assert len(commit_entities) == 1
    assert len(review_entities) == 1
    assert len(milestone_entities) == 1
    assert len(contributor_entities) == 1

    repository = repository_entities[0]
    issue = issue_entities[0]
    pull_request = pull_request_entities[0]
    commit = commit_entities[0]
    review = review_entities[0]
    milestone = milestone_entities[0]
    contributor = contributor_entities[0]

    assert repository["source_type"] == SOURCE_TYPE_GITHUB
    assert repository["entity_type"] == ENTITY_TYPE_GITHUB_REPOSITORY
    assert issue["entity_type"] == ENTITY_TYPE_GITHUB_ISSUE
    assert pull_request["entity_type"] == ENTITY_TYPE_GITHUB_PULL_REQUEST
    assert commit["entity_type"] == ENTITY_TYPE_GITHUB_COMMIT
    assert review["entity_type"] == ENTITY_TYPE_GITHUB_REVIEW
    assert milestone["entity_type"] == ENTITY_TYPE_GITHUB_MILESTONE
    assert contributor["entity_type"] == ENTITY_TYPE_GITHUB_CONTRIBUTOR

    assert commit["author_external_id"] == "contributor-a"
    assert review["author_external_id"] == "reviewer-a"
    assert contributor["author_external_id"] == "contributor-a"
    assert pull_request["attributes"]["latest_review_state"] == "approved"

    for entity in (
        repository,
        issue,
        pull_request,
        commit,
        review,
        milestone,
        contributor,
    ):
        assert entity["content_hash"] == build_entity_content_hash(entity)

    snapshot_hash_a = build_snapshot_content_hash(
        source_batch_set_hash=build_source_batch_set_hash_from_batches(
            [{"payload_hash": "hash-a"}, {"payload_hash": "hash-b"}]
        ),
        mapping_revision="1",
        entities=[
            repository,
            issue,
            pull_request,
            commit,
            review,
            milestone,
            contributor,
        ],
    )
    snapshot_hash_b = build_snapshot_content_hash(
        source_batch_set_hash=build_source_batch_set_hash_from_batches(
            [{"payload_hash": "hash-b"}, {"payload_hash": "hash-a"}]
        ),
        mapping_revision="1",
        entities=[
            contributor,
            milestone,
            review,
            commit,
            pull_request,
            issue,
            repository,
        ],
    )

    assert snapshot_hash_a == snapshot_hash_b
