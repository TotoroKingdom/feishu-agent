from __future__ import annotations

from ._helpers import make_admin_client


def test_admin_login_me_and_logout_flow() -> None:
    client, _, _ = make_admin_client(authenticated=False)

    unauthenticated_response = client.get("/api/v1/admin/auth/me")
    assert unauthenticated_response.status_code == 401

    login_response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "AdminDemo!2026"},
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()["data"]
    assert login_payload["username"] == "admin"
    assert login_payload["status"] == "active"
    assert "session_expires_at" in login_payload

    me_response = client.get("/api/v1/admin/auth/me")
    assert me_response.status_code == 200
    me_payload = me_response.json()["data"]
    assert me_payload["username"] == "admin"

    project_response = client.get("/api/v1/admin/project")
    assert project_response.status_code == 200

    logout_response = client.post("/api/v1/admin/auth/logout")
    assert logout_response.status_code == 204

    revoked_response = client.get("/api/v1/admin/project")
    assert revoked_response.status_code == 401
