from __future__ import annotations

from app.publishing.generation import build_publish_plan_hash, build_publish_plan_payload


def test_publish_plan_hash_is_stable_for_equivalent_mappings() -> None:
    plan = build_publish_plan_payload(
        run_id="run-123",
        report_version_ref="report-version-1",
        report_version=4,
        report_period={
            "start_at": "2026-07-20T00:00:00+00:00",
            "end_at": "2026-07-27T00:00:00+00:00",
            "timezone": "Asia/Shanghai",
        },
        content_hash="rendered-hash",
        expected_publish_group_ref="feishu-publish-group-example",
        archive_resource_ref="feishu-archive-example",
        content_version=1,
    )
    reordered = {
        "content_version": plan["content_version"],
        "content_hash": plan["content_hash"],
        "operations": [
            {
                "payload": {
                    "rendered_content_hash": "rendered-hash",
                    "rendered_report_ref": "report-version-1",
                },
                "sequence": 1,
                "target": {
                    "publish_group_ref": "feishu-publish-group-example",
                    "report_version_ref": "report-version-1",
                },
                "type": "create_feishu_document",
            },
            {
                "target": {"publish_group_ref": "feishu-publish-group-example"},
                "type": "send_group_summary",
                "payload": {
                    "report_period": {
                        "timezone": "Asia/Shanghai",
                        "end_at": "2026-07-27T00:00:00+00:00",
                        "start_at": "2026-07-20T00:00:00+00:00",
                    },
                    "report_version_ref": "report-version-1",
                },
                "sequence": 2,
            },
            {
                "sequence": 3,
                "payload": {
                    "content_hash": "rendered-hash",
                    "report_version_ref": "report-version-1",
                },
                "target": {"archive_resource_ref": "feishu-archive-example"},
                "type": "upsert_bitable_archive",
            },
        ],
        "report_period": {
            "timezone": "Asia/Shanghai",
            "end_at": "2026-07-27T00:00:00+00:00",
            "start_at": "2026-07-20T00:00:00+00:00",
        },
        "report_version": 4,
        "report_version_ref": "report-version-1",
        "run_id": "run-123",
        "schema_version": 1,
    }

    assert plan["operations"] == [
        {
            "sequence": 1,
            "type": "create_feishu_document",
            "target": {
                "publish_group_ref": "feishu-publish-group-example",
                "report_version_ref": "report-version-1",
            },
            "payload": {
                "rendered_report_ref": "report-version-1",
                "rendered_content_hash": "rendered-hash",
            },
        },
        {
            "sequence": 2,
            "type": "send_group_summary",
            "target": {"publish_group_ref": "feishu-publish-group-example"},
            "payload": {
                "report_version_ref": "report-version-1",
                "report_period": {
                    "start_at": "2026-07-20T00:00:00+00:00",
                    "end_at": "2026-07-27T00:00:00+00:00",
                    "timezone": "Asia/Shanghai",
                },
            },
        },
        {
            "sequence": 3,
            "type": "upsert_bitable_archive",
            "target": {"archive_resource_ref": "feishu-archive-example"},
            "payload": {
                "report_version_ref": "report-version-1",
                "content_hash": "rendered-hash",
            },
        },
    ]
    assert build_publish_plan_hash(plan) == build_publish_plan_hash(reordered)
