from __future__ import annotations

from ._helpers import make_admin_client


def test_github_repository_connectivity_test_returns_status_snapshot() -> None:
    client, _, _ = make_admin_client()

    repository_response = client.post(
        "/api/v1/admin/project/repositories",
        json={
            "owner": "openai",
            "repo": "feishu-agent",
            "repository_type": "github",
            "weight": 100,
            "enabled": True,
            "default_branch": "main",
        },
    )
    repository = repository_response.json()["data"]

    response = client.post(f"/api/v1/admin/project/repositories/{repository['id']}/connectivity-test")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["repository_id"] == repository["id"]
    assert data["status"] in {"ok", "degraded"}
    assert "capabilities" in data

