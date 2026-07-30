from __future__ import annotations

from app.db.models import Project

from ._helpers import make_admin_client


def test_admin_configuration_crud_flow() -> None:
    client, factory, project_id = make_admin_client()

    project_response = client.get("/api/v1/admin/project")
    assert project_response.status_code == 200
    project = project_response.json()["data"]
    assert project["name"] == "Demo"

    update_response = client.put(
        "/api/v1/admin/project",
        json={
            "name": "Project Alpha",
            "description": "Project description",
            "timezone": "Asia/Shanghai",
            "default_period_rule": {"type": "previous_calendar_week"},
            "default_prompt_version_id": None,
            "revision": project["revision"],
        },
    )
    assert update_response.status_code == 200
    updated_project = update_response.json()["data"]
    assert updated_project["name"] == "Project Alpha"
    assert updated_project["revision"] == project["revision"] + 1

    repo_response = client.post(
        "/api/v1/admin/project/repositories",
        json={
            "owner": "openai",
            "repo": "feishu-agent",
            "repository_type": "github",
            "weight": 80,
            "enabled": True,
            "default_branch": "main",
        },
    )
    assert repo_response.status_code == 201
    repository = repo_response.json()["data"]
    assert repository["owner"] == "openai"
    assert repository["repo"] == "feishu-agent"

    repo_update_response = client.patch(
        f"/api/v1/admin/project/repositories/{repository['id']}",
        json={
            "owner": "openai",
            "repo": "feishu-agent",
            "repository_type": "github",
            "weight": 60,
            "enabled": False,
            "default_branch": "main",
            "revision": repository["revision"],
        },
    )
    assert repo_update_response.status_code == 200
    updated_repository = repo_update_response.json()["data"]
    assert updated_repository["enabled"] is False

    repo_connectivity = client.post(
        f"/api/v1/admin/project/repositories/{repository['id']}/connectivity-test"
    )
    assert repo_connectivity.status_code == 200
    repo_connectivity_data = repo_connectivity.json()["data"]
    assert repo_connectivity_data["repository_id"] == repository["id"]
    assert repo_connectivity_data["capabilities"]["metadata"] == "ok"

    prompt_response = client.post(
        "/api/v1/admin/prompts",
        json={
            "prompt_type": "report",
            "content": "You are a report generator.",
            "status": "draft",
            "created_by": "admin",
            "model_constraints": {"temperature": 0.2},
        },
    )
    assert prompt_response.status_code == 201
    prompt = prompt_response.json()["data"]
    assert prompt["version"] == 1

    activate_response = client.post(f"/api/v1/admin/prompts/{prompt['id']}/activate")
    assert activate_response.status_code == 200
    activated_prompt = activate_response.json()["data"]
    assert activated_prompt["status"] == "active"

    model_response = client.get("/api/v1/admin/model-config")
    assert model_response.status_code == 200
    model = model_response.json()["data"]
    assert model["model"] == "fake-model"

    model_patch_response = client.patch(
        "/api/v1/admin/model-config",
        json={
            "base_url": "https://api.openai.example/v1",
            "model": "gpt-4.1-mini",
            "temperature": 0.1,
            "timeout_seconds": 45,
            "max_retries": 3,
            "stream": False,
            "revision": model["revision"],
        },
    )
    assert model_patch_response.status_code == 200
    patched_model = model_patch_response.json()["data"]
    assert patched_model["model"] == "gpt-4.1-mini"

    job_response = client.post("/api/v1/admin/project/connectivity-test")
    assert job_response.status_code == 202
    job = job_response.json()["data"]
    assert job["status"] == "succeeded"
    assert set(job["result_summary"]) == {"github", "feishu", "llm"}

    job_get_response = client.get(f"/api/v1/admin/connectivity-jobs/{job['id']}")
    assert job_get_response.status_code == 200
    assert job_get_response.json()["data"]["id"] == job["id"]

