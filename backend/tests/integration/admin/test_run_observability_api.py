from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db.models import AuditLog, LlmExecution, NodeExecution, ToolExecution, new_id
from app.domain.runs import RunCreationService
from tests.integration.admin._helpers import make_admin_client


def test_run_observability_endpoints_return_redacted_timeline_and_lists() -> None:
    client, factory, project_id = make_admin_client()
    with factory() as session:
        run = RunCreationService(session).create_run(
            project_id,
            "2026-W30",
            datetime(2026, 7, 20, tzinfo=UTC).date(),
            datetime(2026, 7, 27, tzinfo=UTC).date(),
        )
        session.add_all(
            [
                NodeExecution(
                    id=new_id(),
                    run_id=run.id,
                    node_name="collect_github_data",
                    node_attempt=1,
                    checkpoint_before="checkpoint-before",
                    checkpoint_after="checkpoint-after",
                    status="succeeded",
                    input_summary={"repository_ref": "org/repo"},
                    output_summary={"count": 2},
                    error_class=None,
                    error_summary=None,
                    started_at=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
                    ended_at=datetime(2026, 7, 29, 10, 0, 30, tzinfo=UTC),
                    duration_ms=30_000,
                ),
                ToolExecution(
                    id=new_id(),
                    run_id=run.id,
                    node_execution_id="collect_github_data",
                    tool_name="github.read_repository_core_data",
                    tool_version="fake.v1",
                    attempt=1,
                    idempotency_key="tool-key-1",
                    request_summary={"token": "super-secret", "repo": "org/repo"},
                    result_summary={"ok": True, "api_key": "secret-value"},
                    data_ref=None,
                    provider_request_id=None,
                    status="success",
                    error_class=None,
                    error_code=None,
                    retryable=False,
                    started_at=datetime(2026, 7, 29, 10, 0, 5, tzinfo=UTC),
                    ended_at=datetime(2026, 7, 29, 10, 0, 7, tzinfo=UTC),
                    duration_ms=2000,
                ),
                LlmExecution(
                    id=new_id(),
                    run_id=run.id,
                    node_execution_id="generate_structured_report",
                    provider="openai",
                    model="gpt-4.1-mini",
                    prompt_type="report",
                    prompt_version_id=None,
                    input_hash="input-hash-1",
                    output_ref="report-version-1",
                    status="succeeded",
                    schema_valid=True,
                    input_tokens=111,
                    output_tokens=222,
                    total_tokens=333,
                    duration_ms=444,
                    error_class=None,
                    created_at=datetime(2026, 7, 29, 10, 0, 10, tzinfo=UTC),
                ),
                AuditLog(
                    id=1,
                    occurred_at=datetime(2026, 7, 29, 10, 0, 15, tzinfo=UTC),
                    request_id="req_123",
                    run_id=run.id,
                    actor_type="admin",
                    actor_id="admin",
                    action="update_project",
                    resource_type="project",
                    resource_id=project_id,
                    before_summary={"password": "hunter2", "name": "Demo"},
                    after_summary={"password": "hunter2", "name": "Demo v2"},
                    result="succeeded",
                    ip_hash="ip-hash",
                    metadata={"token": "secret"},
                ),
            ]
        )
        session.commit()

    timeline_response = client.get(f"/api/v1/admin/runs/{run.id}/timeline", params={"limit": 2})
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()["data"]
    assert timeline["has_more"] is True
    assert timeline["next_cursor"] == "2"
    assert [item["event_type"] for item in timeline["items"]] == [
        "node_execution",
        "tool_execution",
    ]

    nodes_response = client.get(f"/api/v1/admin/runs/{run.id}/nodes")
    assert nodes_response.status_code == 200
    nodes = nodes_response.json()["data"]
    assert nodes["items"][0]["node_name"] == "collect_github_data"
    assert nodes["items"][0]["duration_ms"] == 30000

    tools_response = client.get(f"/api/v1/admin/runs/{run.id}/tools")
    assert tools_response.status_code == 200
    tools = tools_response.json()["data"]
    assert tools["items"][0]["request_summary"]["token"] == "[REDACTED]"
    assert tools["items"][0]["result_summary"]["api_key"] == "[REDACTED]"

    llm_response = client.get(f"/api/v1/admin/runs/{run.id}/llm-executions")
    assert llm_response.status_code == 200
    llms = llm_response.json()["data"]
    assert llms["items"][0]["total_tokens"] == 333

    audit_response = client.get(f"/api/v1/admin/runs/{run.id}/audit-logs")
    assert audit_response.status_code == 200
    audits = audit_response.json()["data"]
    assert audits["items"][0]["before_summary"]["password"] == "[REDACTED]"
    assert audits["items"][0]["after_summary"]["password"] == "[REDACTED]"
