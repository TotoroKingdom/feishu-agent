from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.db.models import AuditLog, LlmExecution, NodeExecution, ToolExecution, new_id
from app.domain.runs import RunCreationService

from ._helpers import make_admin_client


def _make_observability_run() -> tuple[object, object, str]:
    client, factory, project_id = make_admin_client()
    with factory() as session:
        run = RunCreationService(session).create_run(
            project_id,
            "2026-W30",
            date(2026, 7, 20),
            date(2026, 7, 27),
        )
        node_started_at = datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)
        node = NodeExecution(
            id=new_id(),
            run_id=run.id,
            node_name="collect_sources",
            node_attempt=1,
            checkpoint_before="ckpt-before",
            checkpoint_after="ckpt-after",
            status="succeeded",
            input_summary={"token": "node-secret", "plain": "value"},
            output_summary={"api_key": "node-api-key", "rows": 3},
            error_class=None,
            error_summary=None,
            started_at=node_started_at,
            ended_at=node_started_at + timedelta(seconds=30),
            duration_ms=30000,
        )
        tool = ToolExecution(
            id=new_id(),
            run_id=run.id,
            node_execution_id=node.id,
            tool_name="feishu_fetch",
            tool_version="v1",
            attempt=1,
            idempotency_key="tool-secret",
            request_summary={"token": "tool-secret", "query": "items"},
            result_summary={"api_key": "tool-api-key", "count": 1},
            data_ref="data-ref-1",
            provider_request_id="provider-request-1",
            status="success",
            error_class=None,
            error_code=None,
            retryable=False,
            started_at=node_started_at + timedelta(seconds=31),
            ended_at=node_started_at + timedelta(seconds=41),
            duration_ms=10000,
        )
        llm = LlmExecution(
            id=new_id(),
            run_id=run.id,
            node_execution_id=node.id,
            provider="openai",
            model="gpt-4.1-mini",
            prompt_type="report_summary",
            prompt_version_id="prompt-v1",
            input_hash="input-hash-1",
            output_ref="output-ref-1",
            status="succeeded",
            schema_valid=True,
            input_tokens=111,
            output_tokens=222,
            total_tokens=333,
            duration_ms=4444,
            error_class=None,
            created_at=node_started_at + timedelta(seconds=42),
        )
        audit = AuditLog(
            occurred_at=node_started_at + timedelta(seconds=43),
            request_id="req-observability",
            run_id=run.id,
            actor_type="admin",
            actor_id="admin-user",
            action="update_project",
            resource_type="project",
            resource_id=project_id,
            before_summary={"password": "before-secret", "plain": "before"},
            after_summary={"password": "after-secret", "plain": "after"},
            result="succeeded",
            ip_hash="ip-hash-1",
            metadata_={"source": "test", "token": "audit-secret"},
        )
        session.add_all([node, tool, llm, audit])
        session.commit()
    return client, factory, run.id


def test_run_observability_endpoints_expose_desensitized_timelines_and_lists() -> None:
    client, _, run_id = _make_observability_run()

    timeline = client.get(f"/api/v1/admin/runs/{run_id}/timeline?limit=2")
    assert timeline.status_code == 200
    timeline_data = timeline.json()["data"]
    assert len(timeline_data["items"]) == 2
    assert timeline_data["has_more"] is True
    assert timeline_data["next_cursor"] is not None
    assert timeline_data["items"][0]["event_type"] == "node_execution"

    nodes = client.get(f"/api/v1/admin/runs/{run_id}/nodes")
    assert nodes.status_code == 200
    node_items = nodes.json()["data"]["items"]
    assert len(node_items) == 1
    assert node_items[0]["duration_ms"] == 30000
    assert node_items[0]["input_summary"]["token"] == "[REDACTED]"
    assert node_items[0]["output_summary"]["api_key"] == "[REDACTED]"

    tools = client.get(f"/api/v1/admin/runs/{run_id}/tools")
    assert tools.status_code == 200
    tool_items = tools.json()["data"]["items"]
    assert len(tool_items) == 1
    assert tool_items[0]["request_summary"]["token"] == "[REDACTED]"
    assert tool_items[0]["result_summary"]["api_key"] == "[REDACTED]"

    llm = client.get(f"/api/v1/admin/runs/{run_id}/llm-executions")
    assert llm.status_code == 200
    llm_items = llm.json()["data"]["items"]
    assert len(llm_items) == 1
    assert llm_items[0]["total_tokens"] == 333
    assert llm_items[0]["schema_valid"] is True

    audit = client.get(f"/api/v1/admin/runs/{run_id}/audit-logs")
    assert audit.status_code == 200
    audit_items = audit.json()["data"]["items"]
    assert len(audit_items) == 1
    assert audit_items[0]["before_summary"]["password"] == "[REDACTED]"
    assert audit_items[0]["after_summary"]["password"] == "[REDACTED]"
    assert audit_items[0]["metadata"]["token"] == "[REDACTED]"
