from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.runtime import WorkflowRuntime
from app.core.config import Settings
from app.db.models import (
    Base,
    HumanApproval,
    Project,
    PublishPlan,
    ReportArtifact,
    ReportRun,
    ReportVersion,
    SideEffectOperation,
    ToolExecution,
)
from app.domain.runs import RunCreationService
from app.main import create_app
from tests.admin_auth import authenticate_admin

_FORBIDDEN_FRAGMENTS = ("secret", "token", "password", "api_key", "apikey", "credential", "client_secret")


def _make_environment() -> tuple[TestClient, sessionmaker[Session], str, WorkflowRuntime]:
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

    client = TestClient(
        create_app(settings=Settings(_env_file=None, app_profile="local-demo"), session_factory=factory)
    )
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


def _assert_secret_free(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _assert_secret_free(str(key))
            _assert_secret_free(item)
        return
    if isinstance(value, list | tuple | set):
        for item in value:
            _assert_secret_free(item)
        return
    if isinstance(value, str):
        lowered = value.casefold()
        for fragment in _FORBIDDEN_FRAGMENTS:
            assert fragment not in lowered, f"unexpected sensitive fragment {fragment!r} in {value!r}"


def test_local_demo_happy_path_is_repeatable_and_secret_safe() -> None:
    client, factory, run_id, runtime = _make_environment()

    started = runtime.start(run_id)
    assert started.status == "waiting"
    assert started.snapshot.values["current_stage"] == "waiting_confirmation"  # type: ignore[index]
    assert started.snapshot.values["current_node"] == "wait_generation_confirmation"  # type: ignore[index]

    waiting_publish = runtime.resume(run_id, _generation_payload(started.snapshot, "approve_generation"))
    assert waiting_publish.status == "waiting"
    assert waiting_publish.snapshot.values["current_stage"] == "waiting_publish_approval"  # type: ignore[index]
    assert waiting_publish.snapshot.values["current_node"] == "wait_publish_confirmation"  # type: ignore[index]
    assert waiting_publish.snapshot.values["report_version_ref"]  # type: ignore[index]
    assert waiting_publish.snapshot.values["rendered_report_ref"]  # type: ignore[index]
    assert waiting_publish.snapshot.values["metrics_ref"]  # type: ignore[index]
    assert waiting_publish.snapshot.values["evidence_set_ref"]  # type: ignore[index]

    completed = runtime.resume(run_id, _publish_payload(waiting_publish.snapshot, "approve_publish"))
    duplicate = runtime.resume(run_id, _publish_payload(waiting_publish.snapshot, "approve_publish"))

    assert completed.status == "completed"
    assert duplicate.status == "completed"
    assert completed.snapshot.values["current_stage"] == "succeeded"  # type: ignore[index]
    assert completed.snapshot.values["current_node"] == "complete_run"  # type: ignore[index]
    assert completed.snapshot.values["publish"]["operation_refs"] == duplicate.snapshot.values["publish"]["operation_refs"]  # type: ignore[index]
    assert completed.snapshot.values["report_version_ref"] == duplicate.snapshot.values["report_version_ref"]  # type: ignore[index]
    assert completed.snapshot.values["publish_plan_ref"] == duplicate.snapshot.values["publish_plan_ref"]  # type: ignore[index]

    response = client.get(f"/api/v1/admin/runs/{run_id}")
    assert response.status_code == 200
    detail = response.json()["data"]

    assert detail["run_id"] == run_id
    assert detail["status"] == "completed"
    assert detail["current_stage"] == "succeeded"
    assert detail["current_node"] == "complete_run"
    assert detail["approval_status"] == "approved"
    assert detail["should_poll"] is False
    assert detail["is_terminal"] is True
    assert detail["refs"]["publish_plan_ref"] == completed.snapshot.values["publish_plan_ref"]  # type: ignore[index]
    assert detail["refs"]["report_version_ref"] == completed.snapshot.values["report_version_ref"]  # type: ignore[index]
    assert detail["refs"]["approved_publish_plan_ref"] == detail["refs"]["publish_plan_ref"]
    assert len(detail["approvals"]) == 2
    assert len(detail["tools"]) == 10
    assert len(detail["side_effects"]) == 3
    assert len(detail["artifacts"]) == 3
    assert detail["timestamps"]["completed_at"] is not None

    with factory() as session:
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        approvals = session.scalars(select(HumanApproval).where(HumanApproval.run_id == run_id)).all()
        report_version = session.scalar(select(ReportVersion).where(ReportVersion.run_id == run_id))
        publish_plan = session.scalar(select(PublishPlan).where(PublishPlan.run_id == run_id))
        operations = session.scalars(
            select(SideEffectOperation).where(SideEffectOperation.run_id == run_id).order_by(SideEffectOperation.sequence)
        ).all()
        artifacts = session.scalars(
            select(ReportArtifact)
            .join(SideEffectOperation)
            .where(ReportArtifact.run_id == run_id)
            .order_by(SideEffectOperation.sequence)
        ).all()
        tools = session.scalars(select(ToolExecution).where(ToolExecution.run_id == run_id)).all()

        assert run_row is not None
        assert run_row.status == "completed"
        assert run_row.current_stage == "succeeded"
        assert run_row.current_node == "complete_run"
        assert len(approvals) == 2
        assert [approval.approval_type for approval in approvals] == ["generation", "publish"]
        assert approvals[0].status == "approved"
        assert approvals[1].status == "approved"
        assert report_version is not None
        assert publish_plan is not None
        assert report_version.id == detail["refs"]["report_version_ref"]
        assert publish_plan.id == detail["refs"]["publish_plan_ref"]
        assert [operation.id for operation in operations] == completed.snapshot.values["publish"]["operation_refs"]  # type: ignore[index]
        assert [artifact.operation_id for artifact in artifacts] == [operation.id for operation in operations]
        assert len(tools) == 10

        secret_scan_targets: list[object] = [
            detail,
            completed.snapshot.values,
            duplicate.snapshot.values,
            report_version.structured_report,
            report_version.rendered_content,
            publish_plan.canonical_plan,
            [
                {
                    "tool_name": tool.tool_name,
                    "request_summary": tool.request_summary,
                    "result_summary": tool.result_summary,
                }
                for tool in tools
            ],
            [
                {
                    "artifact_type": artifact.artifact_type,
                    "external_id": artifact.external_id,
                    "url": artifact.url,
                }
                for artifact in artifacts
            ],
        ]
        _assert_secret_free(secret_scan_targets)
