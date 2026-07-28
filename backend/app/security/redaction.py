from collections.abc import Mapping
from typing import Any

from pydantic import SecretStr

SENSITIVE_NAMES = ("secret", "token", "password", "api_key", "apikey", "pat", "credential")


def _sensitive(name: object) -> bool:
    normalized = str(name).lower().replace("-", "_")
    if normalized in {"credentials", "credential_data"}:
        return False
    return any(part in normalized for part in SENSITIVE_NAMES)


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, SecretStr):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            key: "[REDACTED]" if _sensitive(key) else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    if isinstance(value, set):
        return {redact_sensitive(item) for item in value}
    return value


def safe_exception_message(error: BaseException) -> str:
    return type(error).__name__
