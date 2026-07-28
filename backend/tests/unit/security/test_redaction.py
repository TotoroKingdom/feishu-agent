from app.security.redaction import redact_sensitive, safe_exception_message


def test_redaction_recursively_removes_sensitive_mapping_values() -> None:
    payload = {
        "request_id": "req-123",
        "credentials": {
            "api_key": "secret-api-key",
            "nested": [{"password": "secret-password", "name": "safe"}],
        },
        "items": ("safe", {"token": "secret-token"}),
    }
    assert redact_sensitive(payload) == {
        "request_id": "req-123",
        "credentials": {
            "api_key": "[REDACTED]",
            "nested": [{"password": "[REDACTED]", "name": "safe"}],
        },
        "items": ("safe", {"token": "[REDACTED]"}),
    }


def test_exception_message_is_sanitized_without_traceback() -> None:
    message = safe_exception_message(RuntimeError("secret-token"))
    assert message == "RuntimeError"
    assert "secret-token" not in message and "Traceback" not in message
