import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


def test_local_demo_explicitly_uses_fake_providers() -> None:
    settings = Settings(_env_file=None)
    assert (
        settings.app_profile,
        settings.feishu_provider,
        settings.github_provider,
        settings.llm_provider,
    ) == ("local-demo", "fake", "fake", "fake")


def test_production_rejects_fake_provider_configuration() -> None:
    with pytest.raises(ValidationError, match="fake providers"):
        Settings(
            _env_file=None,
            app_profile="production",
            feishu_provider="fake",
            github_provider="real",
            llm_provider="real",
            app_encryption_key=SecretStr("A" * 43),
        )


def test_sensitive_settings_repr_does_not_contain_secret() -> None:
    secret = "do-not-print-this-secret"
    settings = Settings(_env_file=None, internal_service_token=SecretStr(secret))
    assert secret not in repr(settings)
    assert secret not in str(settings.internal_service_token)
