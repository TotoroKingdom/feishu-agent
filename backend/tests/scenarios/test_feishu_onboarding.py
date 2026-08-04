from __future__ import annotations

import base64
import json
import os
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.models import (
    Base,
    EncryptedCredential,
    FeishuFieldMapping,
    FeishuResource,
    OnboardingSession,
    Project,
    ProjectRepository,
    PromptVersion,
)
from app.main import create_app
from tests.admin_auth import authenticate_admin


def _encoded_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def _make_client(
    *, allowed_refs: list[str] | None = None
) -> tuple[TestClient, sessionmaker[Session], str]:
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
        session.commit()
        project_id = project.id

    client = TestClient(
        create_app(
            settings=Settings(
                _env_file=None,
                app_profile="local-demo",
                app_encryption_key=_encoded_key(),
                feishu_allowed_actor_refs=allowed_refs or ["ou_123", "tenant:ou_123"],
            ),
            session_factory=factory,
        )
    )
    authenticate_admin(client)
    return client, factory, project_id


def _draft_payload() -> dict[str, object]:
    return {
        "project": {
            "name": "Weekly Agent",
            "description": "Weekly reporting project",
            "timezone": "Asia/Shanghai",
            "default_period_rule": {"type": "previous_calendar_week"},
            "default_prompt": {
                "prompt_type": "report",
                "content": "You are a report generator.",
                "status": "active",
                "created_by": "admin",
                "model_constraints": {"temperature": 0.2},
            },
        },
        "repositories": [
            {
                "owner": "openai",
                "repo": "feishu-agent",
                "repository_type": "github",
                "weight": 80,
                "enabled": True,
                "default_branch": "main",
            }
        ],
        "feishu_resources": [
            {
                "resource_type": "bitable",
                "external_id": "tbl_123",
                "name": "Weekly tasks",
                "enabled": True,
                "schema_hash": "schema-hash-1",
            }
        ],
        "field_mappings": {
            "tbl_123": [
                {
                    "logical_field": "task_id",
                    "external_field_id": "fld_1",
                    "external_field_name": "Task",
                    "external_field_type": "text",
                    "converter": "text",
                    "required_level": "critical",
                    "mapping_options": {},
                    "enabled": True,
                }
            ]
        },
        "schedule": {
            "cron_expression": "0 9 * * 1",
            "timezone": "Asia/Shanghai",
            "enabled": True,
            "misfire_policy": "skip",
        },
        "publish_group": {"group_id": "chat_123", "group_name": "Weekly publish"},
        "recipients": ["ou_123"],
    }


def test_onboarding_flow_persists_session_and_configuration() -> None:
    client, factory, project_id = _make_client()

    start_response = client.post(
        "/api/v1/admin/onboarding/start", json={"feishu_actor_id": "ou_123"}
    )
    assert start_response.status_code == 201
    session = start_response.json()["data"]
    assert session["status"] == "in_progress"
    assert session["current_step"] == "permissions"

    draft_response = client.patch(
        f"/api/v1/admin/onboarding/sessions/{session['id']}/draft",
        json=_draft_payload(),
    )
    assert draft_response.status_code == 200
    draft = draft_response.json()["data"]
    assert draft["current_step"] == "resources"
    assert "ghp_demo_token" not in json.dumps(draft["draft_config"])

    credential_response = client.put(
        f"/api/v1/admin/onboarding/sessions/{session['id']}/github-pat",
        json={"label": "github-pat", "secret": "ghp_demo_token"},
    )
    assert credential_response.status_code == 200
    credential_session = credential_response.json()["data"]
    assert credential_session["credential_ref"]
    assert credential_session["current_step"] == "review"

    preview_response = client.post(f"/api/v1/admin/onboarding/sessions/{session['id']}/preview")
    assert preview_response.status_code == 200
    preview = preview_response.json()["data"]
    assert preview["ready"] is True
    assert preview["missing"] == []
    assert preview["status"] == "pending_confirmation"

    complete_response = client.post(f"/api/v1/admin/onboarding/sessions/{session['id']}/complete")
    assert complete_response.status_code == 200
    completed = complete_response.json()["data"]
    assert completed["status"] == "completed"
    assert completed["current_step"] == "completed"

    restarted_client = TestClient(
        create_app(settings=client.app.state.settings, session_factory=factory)
    )
    authenticate_admin(restarted_client)
    restarted_response = restarted_client.get(
        "/api/v1/admin/onboarding", params={"feishu_actor_id": "ou_123"}
    )
    assert restarted_response.status_code == 200
    restarted = restarted_response.json()["data"]
    assert restarted["status"] == "completed"
    assert restarted["credential_ref"] == credential_session["credential_ref"]

    with factory() as db:
        project = db.get(Project, project_id)
        assert project is not None
        assert project.name == "Weekly Agent"
        assert project.timezone == "Asia/Shanghai"
        assert project.default_prompt_version_id is not None

        repository = db.scalar(
            select(ProjectRepository).where(ProjectRepository.project_id == project_id)
        )
        assert repository is not None
        assert repository.owner == "openai"
        assert repository.repo == "feishu-agent"

        resource = db.scalar(select(FeishuResource).where(FeishuResource.project_id == project_id))
        assert resource is not None
        assert resource.external_id == "tbl_123"

        mapping = db.scalar(
            select(FeishuFieldMapping).where(FeishuFieldMapping.resource_id == resource.id)
        )
        assert mapping is not None
        assert mapping.logical_field == "task_id"

        prompt = db.get(PromptVersion, project.default_prompt_version_id)
        assert prompt is not None
        assert prompt.status == "active"

        credential = db.get(EncryptedCredential, credential_session["credential_ref"])
        assert credential is not None
        assert credential.ciphertext != b"ghp_demo_token"

        onboarding_session = db.get(OnboardingSession, session["id"])
        assert onboarding_session is not None
        assert onboarding_session.status == "completed"
        assert onboarding_session.current_step == "completed"
        assert "ghp_demo_token" not in json.dumps(onboarding_session.draft_config)


def test_onboarding_reuses_active_session_and_rejects_unauthorized_actor() -> None:
    client, factory, _ = _make_client(allowed_refs=["ou_123"])

    first_response = client.post(
        "/api/v1/admin/onboarding/start", json={"feishu_actor_id": "ou_123"}
    )
    assert first_response.status_code == 201
    first_session = first_response.json()["data"]

    duplicate_response = client.post(
        "/api/v1/admin/onboarding/start", json={"feishu_actor_id": "ou_123"}
    )
    assert duplicate_response.status_code == 200
    duplicate_session = duplicate_response.json()["data"]
    assert duplicate_session["id"] == first_session["id"]

    with factory() as db:
        row = db.get(OnboardingSession, first_session["id"])
        assert row is not None
        row.status = "expired"
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()

    resumed_response = client.post(
        "/api/v1/admin/onboarding/start", json={"feishu_actor_id": "ou_123"}
    )
    assert resumed_response.status_code == 201
    resumed_session = resumed_response.json()["data"]
    assert resumed_session["id"] != first_session["id"]

    forbidden_response = client.post(
        "/api/v1/admin/onboarding/start", json={"feishu_actor_id": "ou_999"}
    )
    assert forbidden_response.status_code in {403, 404}
