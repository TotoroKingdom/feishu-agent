from fastapi.testclient import TestClient


def authenticate_admin(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "AdminDemo!2026"},
    )
    assert response.status_code == 200, response.text
    csrf_token = client.cookies.get("admin_csrf_token")
    assert csrf_token, "expected csrf cookie after admin login"
    client.headers["X-CSRF-Token"] = csrf_token
