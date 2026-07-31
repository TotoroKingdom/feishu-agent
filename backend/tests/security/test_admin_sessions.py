from __future__ import annotations

from tests.integration.admin._helpers import make_admin_client


def test_admin_refresh_rotates_tokens_and_invalidates_previous_refresh_cookie() -> None:
    client, _, _ = make_admin_client(authenticated=False)

    login_response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "AdminDemo!2026"},
    )
    assert login_response.status_code == 200

    first_refresh_cookie = client.cookies.get("admin_refresh_token")
    assert first_refresh_cookie

    refresh_response = client.post("/api/v1/admin/auth/refresh")
    assert refresh_response.status_code == 200
    second_refresh_cookie = client.cookies.get("admin_refresh_token")
    assert second_refresh_cookie and second_refresh_cookie != first_refresh_cookie

    client.cookies.set("admin_refresh_token", first_refresh_cookie, path="/")
    stale_refresh_response = client.post("/api/v1/admin/auth/refresh")
    assert stale_refresh_response.status_code == 401


def test_admin_state_changing_requests_require_csrf_header() -> None:
    client, _, _ = make_admin_client(authenticated=False)
    login_response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "AdminDemo!2026"},
    )
    assert login_response.status_code == 200

    missing_csrf_response = client.post(
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
    assert missing_csrf_response.status_code == 403
