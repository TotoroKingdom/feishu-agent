from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from app.domain.source import (
    ENTITY_TYPE_FEISHU_RECORD,
    ENTITY_TYPE_GITHUB_ISSUE,
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
        "assignee_external_ids": list(record.get("assignee_external_ids", []))
        if isinstance(record.get("assignee_external_ids"), Sequence)
        and not isinstance(record.get("assignee_external_ids"), (str, bytes, bytearray))
        else [],
        "labels": list(record.get("labels", []))
        if isinstance(record.get("labels"), Sequence)
        and not isinstance(record.get("labels"), (str, bytes, bytearray))
        else [],
        "milestone_external_id": record.get("milestone_external_id"),
        "created_at_external": _pick_datetime(record, ("created_at",)),
        "updated_at_external": _pick_datetime(record, ("updated_at",)),
        "closed_at_external": _pick_datetime(record, ("closed_at",)),
        "occurred_at": occurred_at,
        "raw_batch_id": source_batch_id,
        "raw_summary": _raw_summary(record),
        "attributes": attributes,
        "fetched_at": fetched_at.astimezone(timezone.utc),
    }
    entity["content_hash"] = build_entity_content_hash(entity)
    return entity


def _pick_datetime(record: Mapping[str, object], keys: Sequence[str] = ("occurred_at",)) -> datetime | None:
    for key in keys:
        candidate = record.get(key)
        parsed = _coerce_datetime(candidate)
        if parsed is not None:
            return parsed
    return None


def _coerce_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
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
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _raw_summary(record: Mapping[str, object]) -> str | None:
    title = record.get("title")
    if isinstance(title, str) and title:
        return title
    if "number" in record:
        return f"#{record['number']}"
    if "external_id" in record:
        return str(record["external_id"])
    return None
