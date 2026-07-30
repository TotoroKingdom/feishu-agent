from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone

from app.domain.metrics import (
    LONG_REVIEW_PR_AGE_DAYS,
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
    METRICS_DEFINITION_VERSION,
    METRIC_MILESTONE_COMPLETION_RATE,
    METRIC_PLAN_TASK_COMPLETION_RATE,
    MetricComputedValue,
    OVERDUE_ISSUE_AGE_DAYS,
)
from app.domain.source import canonical_json_hash


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

    github_issues = _select_entities(filtered_entities, "github_issue")
    github_pull_requests = _select_entities(filtered_entities, "github_pull_request")
    github_commits = _select_entities(filtered_entities, "github_commit")
    github_reviews = _select_entities(filtered_entities, "github_review")
    github_milestones = _select_entities(filtered_entities, "github_milestone")
    feishu_records = _select_entities(filtered_entities, "feishu_record")

    open_issues = [entity for entity in github_issues if _issue_state(entity) == "open"]
    closed_issues = [entity for entity in github_issues if _issue_state(entity) == "closed"]
    overdue_issues = [
        entity for entity in open_issues if _is_overdue_issue(entity, period_end_dt)
    ]
    merged_pull_requests = [
        entity for entity in github_pull_requests if _pull_request_state(entity) == "merged"
    ]
    long_review_pull_requests = [
        entity
        for entity in github_pull_requests
        if _is_long_review_pull_request(entity, period_end_dt)
    ]

    active_contributors = {
        str(entity.get("author_external_id") or "").strip()
        for entity in filtered_entities
        if isinstance(entity.get("author_external_id"), str)
        and str(entity.get("author_external_id") or "").strip()
    }

    metrics = {
        METRIC_GITHUB_ISSUE_TOTAL_COUNT: _metric_value(
            len(github_issues),
            "count",
            "Count of normalized GitHub issues created in the reporting period",
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
        METRIC_GITHUB_PR_TOTAL_COUNT: _metric_value(
            len(github_pull_requests),
            "count",
            "Count of normalized GitHub pull requests created in the reporting period",
            "github_pull_request",
        ),
        METRIC_GITHUB_PR_MERGED_COUNT: _metric_value(
            len(merged_pull_requests),
            "count",
            "Count of normalized GitHub pull requests in merged state",
            "github_pull_request",
        ),
        METRIC_GITHUB_PR_LONG_REVIEW_COUNT: _metric_value(
            len(long_review_pull_requests),
            "count",
            f"Count of open GitHub pull requests older than {LONG_REVIEW_PR_AGE_DAYS} days without an approved review state",
            "github_pull_request",
        ),
        METRIC_GITHUB_COMMIT_COUNT: _metric_value(
            len(github_commits),
            "count",
            "Count of normalized GitHub commits created in the reporting period",
            "github_commit",
        ),
        METRIC_ACTIVE_CONTRIBUTOR_COUNT: _metric_value(
            len(active_contributors),
            "count",
            "Distinct normalized contributors with activity in the snapshot",
            "all_sources",
        ),
        METRIC_MILESTONE_COMPLETION_RATE: _metric_value(
            _completion_rate(*_milestone_completion_counts(github_milestones)),
            "percent",
            "Completion rate derived from GitHub milestone issue totals",
            "github_milestone",
        ),
        METRIC_PLAN_TASK_COMPLETION_RATE: _metric_value(
            _completion_rate(*_task_completion_counts(feishu_records)),
            "percent",
            "Completion rate derived from Feishu plan task records",
            "feishu_bitable",
        ),
    }

    payload: dict[str, object] = {
        "definition_version": definition_version,
        "period_start": _to_iso_string(period_start_dt),
        "period_end": _to_iso_string(period_end_dt),
        "overdue_issue_age_days": OVERDUE_ISSUE_AGE_DAYS,
        "long_review_pr_age_days": LONG_REVIEW_PR_AGE_DAYS,
        "metric_keys": list(METRIC_KEYS),
        "metrics": metrics,
        "input_entity_count": len(filtered_entities),
        "github_issue_count": len(github_issues),
        "github_pull_request_count": len(github_pull_requests),
        "github_commit_count": len(github_commits),
        "github_review_count": len(github_reviews),
        "github_milestone_count": len(github_milestones),
        "feishu_record_count": len(feishu_records),
        "member_activity_breakdown": _build_member_activity_breakdown(filtered_entities, period_end_dt),
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


def _select_entities(
    entities: Sequence[Mapping[str, object]], entity_type: str
) -> list[Mapping[str, object]]:
    return [
        entity
        for entity in entities
        if str(entity.get("entity_type") or "") == entity_type
    ]


def _build_member_activity_breakdown(
    entities: Sequence[Mapping[str, object]], period_end: datetime
) -> list[dict[str, object]]:
    breakdown: dict[str, dict[str, int | str]] = defaultdict(
        lambda: {
            "member_id": "",
            "task_count": 0,
            "issue_count": 0,
            "overdue_issue_count": 0,
            "pull_request_count": 0,
            "commit_count": 0,
            "review_count": 0,
            "total_activity_count": 0,
        }
    )
    for entity in entities:
        member_id = _activity_member_id(entity)
        if not member_id:
            continue
        entity_type = str(entity.get("entity_type") or "")
        if entity_type == "github_repository" or entity_type == "github_milestone":
            continue
        bucket = breakdown[member_id]
        bucket["member_id"] = member_id
        if entity_type == "feishu_record":
            bucket["task_count"] = int(bucket["task_count"]) + 1
            bucket["total_activity_count"] = int(bucket["total_activity_count"]) + 1
            continue
        if entity_type == "github_issue":
            bucket["issue_count"] = int(bucket["issue_count"]) + 1
            bucket["total_activity_count"] = int(bucket["total_activity_count"]) + 1
            if _issue_state(entity) == "open" and _is_overdue_issue(entity, period_end):
                bucket["overdue_issue_count"] = int(bucket["overdue_issue_count"]) + 1
            continue
        if entity_type == "github_pull_request":
            bucket["pull_request_count"] = int(bucket["pull_request_count"]) + 1
            bucket["total_activity_count"] = int(bucket["total_activity_count"]) + 1
            continue
        if entity_type == "github_commit":
            bucket["commit_count"] = int(bucket["commit_count"]) + 1
            bucket["total_activity_count"] = int(bucket["total_activity_count"]) + 1
            continue
        if entity_type == "github_review":
            bucket["review_count"] = int(bucket["review_count"]) + 1
            bucket["total_activity_count"] = int(bucket["total_activity_count"]) + 1
    ordered = sorted(
        breakdown.values(),
        key=lambda item: (-int(item["total_activity_count"]), str(item["member_id"])),
    )
    return [dict(item) for item in ordered]


def _activity_member_id(entity: Mapping[str, object]) -> str:
    for key in ("author_external_id", "external_id"):
        value = entity.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _milestone_completion_counts(entities: Sequence[Mapping[str, object]]) -> tuple[int, int]:
    completed = 0
    total = 0
    for entity in entities:
        attributes = _attributes(entity)
        open_issues = _int_value(attributes.get("open_issues"))
        closed_issues = _int_value(attributes.get("closed_issues"))
        milestone_total = max(open_issues, 0) + max(closed_issues, 0)
        if milestone_total <= 0:
            continue
        total += milestone_total
        completed += max(closed_issues, 0)
    return completed, total


def _task_completion_counts(entities: Sequence[Mapping[str, object]]) -> tuple[int, int]:
    completed = 0
    total = 0
    for entity in entities:
        state = _normalized_state(entity.get("state") or entity.get("status"))
        if not state or state in {"unknown", "failed"}:
            total += 1
            continue
        total += 1
        if state in {"success", "done", "completed", "closed", "approved"}:
            completed += 1
    return completed, total


def _completion_rate(completed: int, total: int) -> int:
    if total <= 0:
        return 0
    return int(round((completed / total) * 100))


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
    return _normalized_state(value)


def _pull_request_state(entity: Mapping[str, object]) -> str:
    value = entity.get("state")
    if _normalized_state(value) == "merged":
        return "merged"
    attributes = _attributes(entity)
    if _normalized_state(attributes.get("merged_at")):
        return "merged"
    return _normalized_state(value)


def _is_long_review_pull_request(entity: Mapping[str, object], period_end: datetime) -> bool:
    if _normalized_state(entity.get("state")) != "open":
        return False
    attributes = _attributes(entity)
    latest_review_state = _normalized_state(attributes.get("latest_review_state"))
    review_count = _int_value(attributes.get("review_count"))
    if latest_review_state == "approved":
        return False
    anchor = _pick_datetime(entity.get("updated_at_external")) or _pick_datetime(
        entity.get("occurred_at")
    )
    if anchor is None:
        return False
    if review_count <= 0:
        return anchor < period_end - timedelta(days=LONG_REVIEW_PR_AGE_DAYS)
    return latest_review_state not in {"approved", "changes_requested"} and anchor < period_end - timedelta(days=LONG_REVIEW_PR_AGE_DAYS)


def _is_overdue_issue(entity: Mapping[str, object], period_end: datetime) -> bool:
    if _issue_state(entity) != "open":
        return False
    anchor = _pick_datetime(entity.get("updated_at_external")) or _pick_datetime(
        entity.get("occurred_at")
    )
    if anchor is None:
        return False
    return anchor < period_end - timedelta(days=OVERDUE_ISSUE_AGE_DAYS)


def _attributes(entity: Mapping[str, object]) -> Mapping[str, object]:
    value = entity.get("attributes")
    if isinstance(value, Mapping):
        return value
    return {}


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _normalized_state(value: object) -> str:
    return str(value or "").strip().casefold()


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
