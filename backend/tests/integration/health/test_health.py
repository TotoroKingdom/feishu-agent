from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_minimal_status_and_request_id() -> None:
    response = TestClient(create_app()).get("/health", headers={"X-Request-ID": "req-test-123"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "req-test-123"


def test_ready_hides_dependency_exception_details() -> None:
    def failing_dependency() -> bool:
        raise RuntimeError("database password should not escape")

    response = TestClient(create_app(readiness_checks={"database": failing_dependency})).get(
        "/ready"
    )
    assert response.status_code == 503
    assert response.json() == {
        "error": {"code": "DEPENDENCY_UNAVAILABLE", "message": "Service is not ready"}
    }
    assert "password" not in response.text and "Traceback" not in response.text
