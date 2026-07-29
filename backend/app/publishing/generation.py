from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from app.approvals import canonical_json_hash

PUBLISH_PLAN_SCHEMA_VERSION = 1
PUBLISH_PLAN_CONTENT_VERSION = 1


def build_publish_plan_payload(
    *,
    run_id: str,
    report_version_ref: str,
    report_version: int,
    report_period: Mapping[str, object],
    content_hash: str,
    expected_publish_group_ref: str | None,
    archive_resource_ref: str | None = None,
    content_version: int = PUBLISH_PLAN_CONTENT_VERSION,
) -> dict[str, object]:
    normalized_period = _normalize_report_period(report_period)
    operations = [
        {
            "sequence": 1,
            "type": "create_feishu_document",
            "target": {
                "publish_group_ref": expected_publish_group_ref,
                "report_version_ref": report_version_ref,
            },
            "payload": {
                "rendered_report_ref": report_version_ref,
                "rendered_content_hash": content_hash,
            },
        },
        {
            "sequence": 2,
            "type": "send_group_summary",
            "target": {
                "publish_group_ref": expected_publish_group_ref,
            },
            "payload": {
                "report_version_ref": report_version_ref,
                "report_period": normalized_period,
            },
        },
        {
            "sequence": 3,
            "type": "upsert_bitable_archive",
            "target": {
                "archive_resource_ref": archive_resource_ref,
            },
            "payload": {
                "report_version_ref": report_version_ref,
                "content_hash": content_hash,
            },
        },
    ]

    return {
        "schema_version": PUBLISH_PLAN_SCHEMA_VERSION,
        "run_id": run_id,
        "report_version_ref": report_version_ref,
        "report_version": report_version,
        "content_version": content_version,
        "content_hash": content_hash,
        "report_period": normalized_period,
        "operations": operations,
    }


def build_publish_plan_hash(plan: Mapping[str, object]) -> str:
    return canonical_json_hash(plan)


def _normalize_report_period(report_period: Mapping[str, object]) -> dict[str, object]:
    return {
        "start_at": _coerce_string(report_period.get("start_at"), "start_at"),
        "end_at": _coerce_string(report_period.get("end_at"), "end_at"),
        "timezone": _coerce_string(report_period.get("timezone"), "timezone"),
    }


def _coerce_string(value: object, field_name: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None:
        return ""
    raise ValueError(f"{field_name} must be a string")
