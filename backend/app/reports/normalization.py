from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import cast

from app.domain.source import (
    ENTITY_TYPE_FEISHU_RECORD,
    ENTITY_TYPE_GITHUB_COMMIT,
    ENTITY_TYPE_GITHUB_CONTRIBUTOR,
    ENTITY_TYPE_GITHUB_ISSUE,
    ENTITY_TYPE_GITHUB_MILESTONE,
    ENTITY_TYPE_GITHUB_PULL_REQUEST,
    ENTITY_TYPE_GITHUB_REPOSITORY,
    ENTITY_TYPE_GITHUB_REVIEW,
    NORMALIZER_VERSION,
    SOURCE_TYPE_FEISHU_BITABLE,
    SOURCE_TYPE_GITHUB,
    build_batch_set_hash,
    canonical_json_hash,
)


def normalize_feishu_records(
    records: Sequence[Mapping[str, object]],
    *,
    source_batch_id: str,
    source_resource_id: str,
    fetched_at: datetime,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for index, record in enumerate(records):
        occurred_at = _pick_datetime(record)
        if not _within_period(occurred_at, period_start, period_end):
            continue
        entity = _build_entity(
            source_type=SOURCE_TYPE_FEISHU_BITABLE,
            entity_type=ENTITY_TYPE_FEISHU_RECORD,
            record=record,
            source_batch_id=source_batch_id,
            source_resource_id=source_resource_id,
            fetched_at=fetched_at,
            fallback_external_id=f"feishu-record-{index + 1}",
            occurred_at=occurred_at,
        )
        normalized.append(entity)
    return normalized


def normalize_github_repository_record(
    record: Mapping[str, object] | None,
    *,
    source_batch_id: str,
    source_resource_id: str,
    fetched_at: datetime,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> list[dict[str, object]]:
    if not isinstance(record, Mapping):
        return []
    occurred_at = _pick_datetime(record, ("updated_at", "pushed_at", "created_at"))
    if not _within_period(occurred_at, period_start, period_end):
        return []
    normalized_record = dict(record)
    normalized_record.setdefault(
        "title",
        normalized_record.get("full_name")
        or normalized_record.get("name")
        or normalized_record.get("id")
        or source_resource_id,
    )
    normalized_record.setdefault(
        "state",
        "archived" if bool(normalized_record.get("archived")) else "active",
    )
    normalized_record.setdefault(
        "external_id",
        normalized_record.get("id") or normalized_record.get("full_name") or source_resource_id,
    )
    entity = _build_entity(
        source_type=SOURCE_TYPE_GITHUB,
        entity_type=ENTITY_TYPE_GITHUB_REPOSITORY,
        record=normalized_record,
        source_batch_id=source_batch_id,
        source_resource_id=source_resource_id,
        fetched_at=fetched_at,
        fallback_external_id=str(normalized_record.get("external_id") or source_resource_id),
        occurred_at=occurred_at,
    )
    return [entity]


def normalize_github_issue_records(
    records: Sequence[Mapping[str, object]],
    *,
    source_batch_id: str,
    source_resource_id: str,
    fetched_at: datetime,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for index, record in enumerate(records):
        if bool(record.get("pull_request")):
            continue
        occurred_at = _pick_datetime(record)
        if not _within_period(occurred_at, period_start, period_end):
            continue
        fallback_external_id = record.get("number")
        entity = _build_entity(
            source_type=SOURCE_TYPE_GITHUB,
            entity_type=ENTITY_TYPE_GITHUB_ISSUE,
            record=record,
            source_batch_id=source_batch_id,
            source_resource_id=source_resource_id,
            fetched_at=fetched_at,
            fallback_external_id=f"issue-{fallback_external_id or index + 1}",
            occurred_at=occurred_at,
        )
        normalized.append(entity)
    return normalized


def normalize_github_pull_request_records(
    records: Sequence[Mapping[str, object]],
    *,
    source_batch_id: str,
    source_resource_id: str,
    fetched_at: datetime,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for index, record in enumerate(records):
        occurred_at = _pick_datetime(record, ("updated_at", "created_at", "closed_at"))
        if not _within_period(occurred_at, period_start, period_end):
            continue
        state = str(record.get("state") or "open").casefold()
        merged_at = _pick_datetime(record, ("merged_at",))
        normalized_record = dict(record)
        normalized_record.setdefault("state", "merged" if merged_at is not None else state)
        head = normalized_record.get("head")
        head_label = head.get("label") if isinstance(head, Mapping) else None
        normalized_record.setdefault("title", normalized_record.get("title") or head_label)
        normalized_record.setdefault(
            "external_id",
            normalized_record.get("id") or normalized_record.get("number") or index + 1,
        )
        entity = _build_entity(
            source_type=SOURCE_TYPE_GITHUB,
            entity_type=ENTITY_TYPE_GITHUB_PULL_REQUEST,
            record=normalized_record,
            source_batch_id=source_batch_id,
            source_resource_id=source_resource_id,
            fetched_at=fetched_at,
            fallback_external_id=f"pull-request-{normalized_record.get('number') or index + 1}",
            occurred_at=occurred_at,
        )
        normalized.append(entity)
    return normalized


def normalize_github_commit_records(
    records: Sequence[Mapping[str, object]],
    *,
    source_batch_id: str,
    source_resource_id: str,
    fetched_at: datetime,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for index, record in enumerate(records):
        occurred_at = _pick_datetime(record, ("commit", "author", "committer"))
        if not _within_period(occurred_at, period_start, period_end):
            continue
        normalized_record = dict(record)
        message = _commit_message(record)
        normalized_record.setdefault("title", message)
        normalized_record.setdefault("state", "committed")
        normalized_record.setdefault(
            "external_id",
            normalized_record.get("sha") or normalized_record.get("node_id") or index + 1,
        )
        normalized_record.setdefault("author_external_id", _commit_author(record))
        entity = _build_entity(
            source_type=SOURCE_TYPE_GITHUB,
            entity_type=ENTITY_TYPE_GITHUB_COMMIT,
            record=normalized_record,
            source_batch_id=source_batch_id,
            source_resource_id=source_resource_id,
            fetched_at=fetched_at,
            fallback_external_id=f"commit-{normalized_record.get('sha') or index + 1}",
            occurred_at=occurred_at,
        )
        normalized.append(entity)
    return normalized


def normalize_github_review_records(
    records: Sequence[Mapping[str, object]],
    *,
    source_batch_id: str,
    source_resource_id: str,
    fetched_at: datetime,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for index, record in enumerate(records):
        occurred_at = _pick_datetime(record, ("submitted_at", "submitted"))
        if not _within_period(occurred_at, period_start, period_end):
            continue
        normalized_record = dict(record)
        pull_request = normalized_record.pop("pull_request", None)
        if isinstance(pull_request, Mapping):
            normalized_record.setdefault("pull_request_number", pull_request.get("number"))
            normalized_record.setdefault("pull_request_title", pull_request.get("title"))
        normalized_record.setdefault(
            "title",
            _review_title(record) or f"Review {record.get('state') or index + 1}",
        )
        normalized_record.setdefault("state", str(record.get("state") or "commented").casefold())
        normalized_record.setdefault(
            "external_id",
            normalized_record.get("id") or normalized_record.get("node_id") or index + 1,
        )
        normalized_record.setdefault("author_external_id", _review_author(record))
        entity = _build_entity(
            source_type=SOURCE_TYPE_GITHUB,
            entity_type=ENTITY_TYPE_GITHUB_REVIEW,
            record=normalized_record,
            source_batch_id=source_batch_id,
            source_resource_id=source_resource_id,
            fetched_at=fetched_at,
            fallback_external_id=f"review-{normalized_record.get('id') or index + 1}",
            occurred_at=occurred_at,
        )
        normalized.append(entity)
    return normalized


def normalize_github_milestone_records(
    records: Sequence[Mapping[str, object]],
    *,
    source_batch_id: str,
    source_resource_id: str,
    fetched_at: datetime,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for index, record in enumerate(records):
        occurred_at = _pick_datetime(record, ("updated_at", "due_on", "created_at", "closed_at"))
        if not _within_period(occurred_at, period_start, period_end):
            continue
        normalized_record = dict(record)
        normalized_record.setdefault(
            "title", normalized_record.get("title") or f"Milestone {index + 1}"
        )
        normalized_record.setdefault("state", str(record.get("state") or "open").casefold())
        normalized_record.setdefault(
            "external_id",
            normalized_record.get("id") or normalized_record.get("number") or index + 1,
        )
        entity = _build_entity(
            source_type=SOURCE_TYPE_GITHUB,
            entity_type=ENTITY_TYPE_GITHUB_MILESTONE,
            record=normalized_record,
            source_batch_id=source_batch_id,
            source_resource_id=source_resource_id,
            fetched_at=fetched_at,
            fallback_external_id=f"milestone-{normalized_record.get('number') or index + 1}",
            occurred_at=occurred_at,
        )
        normalized.append(entity)
    return normalized


def normalize_github_contributor_records(
    records: Sequence[Mapping[str, object]],
    *,
    source_batch_id: str,
    source_resource_id: str,
    fetched_at: datetime,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for index, record in enumerate(records):
        normalized_record = dict(record)
        normalized_record.setdefault(
            "title",
            normalized_record.get("login")
            or normalized_record.get("name")
            or normalized_record.get("author")
            or f"Contributor {index + 1}",
        )
        normalized_record.setdefault("state", "active")
        normalized_record.setdefault(
            "external_id",
            normalized_record.get("login") or normalized_record.get("id") or index + 1,
        )
        normalized_record.setdefault("author_external_id", normalized_record.get("login"))
        entity = _build_entity(
            source_type=SOURCE_TYPE_GITHUB,
            entity_type=ENTITY_TYPE_GITHUB_CONTRIBUTOR,
            record=normalized_record,
            source_batch_id=source_batch_id,
            source_resource_id=source_resource_id,
            fetched_at=fetched_at,
            fallback_external_id=f"contributor-{normalized_record.get('login') or index + 1}",
            occurred_at=None,
        )
        occurred_at = cast(datetime | None, entity.get("occurred_at"))
        if not _within_period(occurred_at, period_start, period_end):
            continue
        normalized.append(entity)
    return normalized


def build_snapshot_content_hash(
    *,
    source_batch_set_hash: str,
    mapping_revision: str,
    normalizer_version: str = NORMALIZER_VERSION,
    entities: Sequence[Mapping[str, object]],
) -> str:
    entity_hashes = [str(entity["content_hash"]) for entity in entities]
    return canonical_json_hash(
        {
            "source_batch_set_hash": source_batch_set_hash,
            "mapping_revision": mapping_revision,
            "normalizer_version": normalizer_version,
            "entity_hashes": sorted(entity_hashes),
        }
    )


def build_entity_content_hash(entity: Mapping[str, object]) -> str:
    payload = dict(entity)
    payload.pop("content_hash", None)
    return canonical_json_hash(payload)


def build_source_batch_set_hash_from_batches(batches: Sequence[Mapping[str, object]]) -> str:
    payload_hashes = [str(batch["payload_hash"]) for batch in batches]
    return build_batch_set_hash(payload_hashes)


def _build_entity(
    *,
    source_type: str,
    entity_type: str,
    record: Mapping[str, object],
    source_batch_id: str,
    source_resource_id: str,
    fetched_at: datetime,
    fallback_external_id: str,
    occurred_at: datetime | None,
) -> dict[str, object]:
    external_id = str(record.get("external_id") or fallback_external_id)
    title = record.get("title")
    state = record.get("status") or record.get("state")
    attributes: dict[str, object] = {
        key: value
        for key, value in record.items()
        if key not in {"external_id", "title", "status", "state", "occurred_at", "created_at"}
    }
    entity: dict[str, object] = {
        "source_type": source_type,
        "entity_type": entity_type,
        "source_resource_id": source_resource_id,
        "external_id": external_id,
        "repository_id": record.get("repository_id"),
        "url": record.get("url"),
        "title": str(title) if isinstance(title, str) else (title if title is None else str(title)),
        "state": str(state) if isinstance(state, str) else (state if state is None else str(state)),
        "author_external_id": record.get("author_external_id"),
        "assignee_external_ids": _sequence_to_list(record.get("assignee_external_ids")),
        "labels": _sequence_to_list(record.get("labels")),
        "milestone_external_id": record.get("milestone_external_id"),
        "created_at_external": _pick_datetime(record, ("created_at",)),
        "updated_at_external": _pick_datetime(record, ("updated_at",)),
        "closed_at_external": _pick_datetime(record, ("closed_at",)),
        "occurred_at": occurred_at,
        "raw_batch_id": source_batch_id,
        "raw_summary": _raw_summary(record),
        "attributes": attributes,
        "fetched_at": fetched_at.astimezone(UTC),
    }
    entity["content_hash"] = build_entity_content_hash(entity)
    return entity


def _pick_datetime(
    record: Mapping[str, object], keys: Sequence[str] = ("occurred_at",)
) -> datetime | None:
    for key in keys:
        candidate = record.get(key)
        parsed = _coerce_datetime(candidate)
        if parsed is not None:
            return parsed
    return None


def _coerce_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _within_period(
    occurred_at: datetime | None, period_start: datetime | None, period_end: datetime | None
) -> bool:
    if occurred_at is None:
        return True
    if period_start is not None and occurred_at < _to_utc(period_start):
        return False
    if period_end is not None and occurred_at >= _to_utc(period_end):
        return False
    return True


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _raw_summary(record: Mapping[str, object]) -> str | None:
    title = record.get("title")
    if isinstance(title, str) and title:
        return title
    if "number" in record:
        return f"#{record['number']}"
    if "external_id" in record:
        return str(record["external_id"])
    return None


def _commit_message(record: Mapping[str, object]) -> str:
    commit = record.get("commit")
    if isinstance(commit, Mapping):
        message = commit.get("message")
        if isinstance(message, str) and message:
            return message.splitlines()[0]
    message = record.get("message")
    if isinstance(message, str) and message:
        return message.splitlines()[0]
    return str(record.get("sha") or "Commit")


def _commit_author(record: Mapping[str, object]) -> str | None:
    for key in ("author", "committer"):
        nested = record.get(key)
        if isinstance(nested, Mapping):
            login = nested.get("login")
            if isinstance(login, str) and login:
                return login
            name = nested.get("name")
            if isinstance(name, str) and name:
                return name
    return None


def _review_title(record: Mapping[str, object]) -> str | None:
    pull_request = record.get("pull_request")
    if isinstance(pull_request, Mapping):
        number = pull_request.get("number")
        title = pull_request.get("title")
        if isinstance(title, str) and title:
            return f"PR #{number}: {title}" if number is not None else title
    body = record.get("body")
    if isinstance(body, str) and body:
        return body.splitlines()[0][:120]
    return None


def _review_author(record: Mapping[str, object]) -> str | None:
    user = record.get("user")
    if isinstance(user, Mapping):
        login = user.get("login")
        if isinstance(login, str) and login:
            return login
    return None


def _sequence_to_list(value: object) -> list[object]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return list(value)
    return []
