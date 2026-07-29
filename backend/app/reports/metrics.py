from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from app.domain.metrics import (
    METRIC_ACTIVE_CONTRIBUTOR_COUNT,
    METRIC_GITHUB_ISSUE_CLOSED_COUNT,
    METRIC_GITHUB_ISSUE_OPEN_COUNT,
    METRIC_GITHUB_ISSUE_OVERDUE_COUNT,
    METRIC_GITHUB_ISSUE_TOTAL_COUNT,
    METRIC_KEYS,
    METRICS_DEFINITION_VERSION,
    OVERDUE_ISSUE_AGE_DAYS,
    MetricComputedValue,
)
from app.domain.source import SOURCE_TYPE_GITHUB, canonical_json_hash


def calculate_metric_payload(
    entities: Sequence[Mapping[str, object]],
    *,
    period_start: date | datetime,
    period_end: date | datetime,
    definition_version: str = METRICS_DEFINITION_VERSION,
) -> dict[str, object]:
    period_start_dt = _to_utc_datetime(period_start)
    period_end_dt = _to_utc_datetime(period_end)
    filtered_entities = [
        entity
        for entity in _dedupe_entities(entities)
        if _within_period(_pick_datetime(entity.get("occurred_at")), period_start_dt, period_end_dt)
    ]

    github_issues = [
        entity
        for entity in filtered_entities
        if str(entity.get("source_type") or "") == SOURCE_TYPE_GITHUB
        and str(entity.get("entity_type") or "") == "github_issue"
    ]

    open_issues = [entity for entity in github_issues if _issue_state(entity) == "open"]
    closed_issues = [entity for entity in github_issues if _issue_state(entity) == "closed"]
    overdue_issues = [
        entity
        for entity in open_issues
        if _is_overdue_issue(entity, period_end_dt)
    ]
    active_contributors = {
        str(entity.get("author_external_id") or "")
        for entity in filtered_entities
        if isinstance(entity.get("author_external_id"), str)
        and str(entity.get("author_external_id") or "")
    }

    metrics = {
        METRIC_GITHUB_ISSUE_TOTAL_COUNT: _metric_value(
            len(github_issues),
            "count",
            "Count of normalized GitHub issues in the snapshot",
            "github_issue",
        ),
        METRIC_GITHUB_ISSUE_OPEN_COUNT: _metric_value(
            len(open_issues),
            "count",
            "Count of normalized GitHub issues with open state",
            "github_issue",
        ),
        METRIC_GITHUB_ISSUE_CLOSED_COUNT: _metric_value(
            len(closed_issues),
            "count",
            "Count of normalized GitHub issues with closed state",
            "github_issue",
        ),
        METRIC_GITHUB_ISSUE_OVERDUE_COUNT: _metric_value(
            len(overdue_issues),
            "count",
            f"Count of open GitHub issues older than {OVERDUE_ISSUE_AGE_DAYS} days",
            "github_issue",
        ),
        METRIC_ACTIVE_CONTRIBUTOR_COUNT: _metric_value(
            len(active_contributors),
            "count",
            "Distinct normalized contributors with activity in the snapshot",
            "all_sources",
        ),
    }

    payload: dict[str, object] = {
        "definition_version": definition_version,
        "period_start": _to_iso_string(period_start_dt),
        "period_end": _to_iso_string(period_end_dt),
        "overdue_issue_age_days": OVERDUE_ISSUE_AGE_DAYS,
        "metric_keys": list(METRIC_KEYS),
        "metrics": metrics,
        "input_entity_count": len(filtered_entities),
        "github_issue_count": len(github_issues),
    }
    payload["content_hash"] = build_metric_snapshot_content_hash(payload)
    return payload


def build_metric_snapshot_content_hash(payload: Mapping[str, object]) -> str:
    normalized = dict(payload)
    normalized.pop("content_hash", None)
    return canonical_json_hash(normalized)


def extract_metric_values(payload: Mapping[str, object]) -> dict[str, int]:
    metrics = payload.get("metrics")
    if not isinstance(metrics, Mapping):
        return {}
    values: dict[str, int] = {}
    for key in METRIC_KEYS:
        metric = metrics.get(key)
        if isinstance(metric, Mapping) and isinstance(metric.get("value"), int):
            values[key] = metric["value"]
    return values


def _metric_value(value: int, unit: str, description: str, source_scope: str) -> dict[str, object]:
    metric = MetricComputedValue(
        value=value,
        unit=unit,
        description=description,
        source_scope=source_scope,
    )
    return {
        "value": metric.value,
        "unit": metric.unit,
        "description": metric.description,
        "source_scope": metric.source_scope,
    }


def _dedupe_entities(entities: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    seen: set[str] = set()
    deduped: list[Mapping[str, object]] = []
    for entity in entities:
        fingerprint = str(entity.get("content_hash") or canonical_json_hash(dict(entity)))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(entity)
    return deduped


def _pick_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _issue_state(entity: Mapping[str, object]) -> str:
    value = entity.get("state")
    return str(value or "").strip().casefold()


def _is_overdue_issue(entity: Mapping[str, object], period_end: datetime) -> bool:
    if _issue_state(entity) != "open":
        return False
    anchor = _pick_datetime(entity.get("updated_at_external")) or _pick_datetime(
        entity.get("occurred_at")
    )
    if anchor is None:
        return False
    return anchor < period_end - timedelta(days=OVERDUE_ISSUE_AGE_DAYS)


def _within_period(
    occurred_at: datetime | None, period_start: datetime, period_end: datetime
) -> bool:
    if occurred_at is None:
        return True
    return period_start <= occurred_at < period_end


def _to_utc_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _to_iso_string(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()
