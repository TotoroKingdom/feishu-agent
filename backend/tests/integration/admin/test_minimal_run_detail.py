from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.runtime import WorkflowRuntime
from app.core.config import Settings
from app.db.models import Base, Project, ToolExecution, new_id
from app.domain.runs import RunCreationService
from app.main import create_app
from tests.admin_auth import authenticate_admin


def _make_client() -> tuple[TestClient, sessionmaker[Session], str, WorkflowRuntime]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    with factory() as session:
        project = Project(name="Demo", timezone="Asia/Shanghai")
        session.add(project)
        session.flush()
        run = RunCreationService(session).create_run(
            project.id,
            "2026-W30",
            date(2026, 7, 20),
            date(2026, 7, 27),
        )
        session.commit()
    client = TestClient(create_app(settings=Settings(_env_file=None, app_profile="local-demo"), session_factory=factory))
    authenticate_admin(client)
    runtime = WorkflowRuntime(factory, MemorySaver())
    return client, factory, run.id, runtime


def _generation_payload(snapshot: object, action: str) -> dict[str, object]:
    values = snapshot.values  # type: ignore[attr-defined]
    approval = values["approval"]
    scope = values["scope"]
    return {
        "action": action,
        "challenge_id": approval["challenge_id"],
        "approval_revision": approval["approval_revision"],
        "presented_hash": scope["scope_hash"],
        "actor_id": "local-demo",
    }


def _publish_payload(snapshot: object, action: str) -> dict[str, object]:
    values = snapshot.values  # type: ignore[attr-defined]
    approval = values["approval"]
    publish = values["publish"]
    return {
        "action": action,
        "challenge_id": approval["challenge_id"],
        "approval_revision": approval["approval_revision"],
        "presented_hash": publish["plan_hash"],
        "actor_id": "local-demo",
    }


def test_minimal_run_detail_projects_safe_terminal_state() -> None:
    client, factory, run_id, runtime = _make_client()

    started = runtime.start(run_id)
    waiting = runtime.resume(run_id, _generation_payload(started.snapshot, "approve_generation"))
    completed = runtime.resume(run_id, _publish_payload(waiting.snapshot, "approve_publish"))

    with factory() as session:
        session.add(
            ToolExecution(
                id=new_id(),
                run_id=run_id,
                node_execution_id="custom-tool-node",
                tool_name="debug_tool",
                tool_version="fake.v1",
                attempt=1,
                idempotency_key="custom-tool-secret-key",
                request_summary={
                    "token": "super-secret",
                    "password": "hunter2",
                    "plain": "value",
                },
                result_summary={
                    "api_key": "secret-value",
                    "ok": True,
                },
                data_ref=None,
                provider_request_id=None,
                status="success",
                error_class=None,
                error_code=None,
                retryable=False,
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                duration_ms=12,
            )
        )
        session.commit()

    response = client.get(f"/api/v1/admin/runs/{run_id}")

    assert response.status_code == 200
    payload = response.json()
    data = payload["data"]

    assert payload["meta"]["request_id"]
    assert data["run_id"] == run_id
    assert data["status"] == "completed"
    assert data["current_stage"] == "succeeded"
    assert data["current_node"] == "complete_run"
    assert data["approval_status"] == "approved"
    assert data["should_poll"] is False
    assert data["is_terminal"] is True
    assert data["refs"]["publish_plan_ref"]
    assert data["refs"]["report_version_ref"]
    assert len(data["approvals"]) == 2
    assert len(data["artifacts"]) == 3
    assert len(data["side_effects"]) == 3
    assert len(data["tools"]) >= 11
    custom_tool = next(tool for tool in data["tools"] if tool["node_execution_id"] == "custom-tool-node")
    assert custom_tool["request_summary"]["token"] == "[REDACTED]"
    assert custom_tool["request_summary"]["password"] == "[REDACTED]"
    assert custom_tool["result_summary"]["api_key"] == "[REDACTED]"
    assert completed.snapshot.values["current_stage"] == "succeeded"  # type: ignore[index]


def test_minimal_run_detail_keeps_polling_for_waiting_runs() -> None:
    client, _, run_id, runtime = _make_client()

    started = runtime.start(run_id)
    assert started.status == "waiting"

    response = client.get(f"/api/v1/admin/runs/{run_id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "waiting"
    assert data["should_poll"] is True
    assert data["is_terminal"] is False
    assert data["current_stage"] == "waiting_confirmation"
    assert data["current_node"] == "wait_generation_confirmation"


def test_minimal_run_detail_returns_404_for_missing_run() -> None:
    client, _, _, _ = _make_client()

    response = client.get("/api/v1/admin/runs/does-not-exist")

    assert response.status_code == 404

