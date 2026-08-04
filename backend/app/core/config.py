from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_profile: Literal["local-demo", "production"] = "local-demo"
    feishu_provider: Literal["fake", "real"] = "fake"
    feishu_app_id: str | None = None
    feishu_app_secret: SecretStr | None = None
    feishu_verification_token: SecretStr | None = None
    feishu_encrypt_key: SecretStr | None = None
    feishu_allowed_actor_refs: list[str] = Field(default_factory=list)
    feishu_callback_max_skew_seconds: int = 600
    github_provider: Literal["fake", "real"] = "fake"
    llm_provider: Literal["fake", "real"] = "fake"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://feishu_agent:change-me@127.0.0.1:5432/feishu_agent"
    redis_url: str = "redis://127.0.0.1:6379/0"
    app_encryption_key: SecretStr | None = None
    internal_service_token: SecretStr | None = None
    admin_username: str = Field(default="admin", min_length=1, max_length=64)
    admin_initial_password: SecretStr = SecretStr("AdminDemo!2026")
    admin_access_token_minutes: int = Field(default=30, ge=1, le=1440)
    admin_session_days: int = Field(default=7, ge=1, le=365)
    admin_failed_login_limit: int = Field(default=5, ge=1, le=20)
    admin_lock_minutes: int = Field(default=15, ge=1, le=1440)
    admin_allowed_origins: list[str] = Field(default_factory=list)

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @model_validator(mode="after")
    def validate_profile(self) -> "Settings":
        providers = (self.feishu_provider, self.github_provider, self.llm_provider)
        if self.app_profile == "production" and "fake" in providers:
            raise ValueError("production cannot use fake providers")
        if self.app_profile == "production" and self.app_encryption_key is None:
            raise ValueError("production requires app_encryption_key")
        if self.app_profile == "production" and not self._looks_strong(
            self.admin_initial_password.get_secret_value()
        ):
            raise ValueError("production requires a strong admin_initial_password")
        if self.feishu_provider == "real":
            if self.feishu_app_id is None:
                raise ValueError("real feishu provider requires feishu_app_id")
            if self.feishu_app_secret is None:
                raise ValueError("real feishu provider requires feishu_app_secret")
            if self.feishu_verification_token is None:
                raise ValueError("real feishu provider requires feishu_verification_token")
        return self

    @staticmethod
    def _looks_strong(value: str) -> bool:
        if len(value) < 12:
            return False
        has_upper = any(character.isupper() for character in value)
        has_lower = any(character.islower() for character in value)
        has_digit = any(character.isdigit() for character in value)
        has_symbol = any(not character.isalnum() for character in value)
        return has_upper and has_lower and has_digit and has_symbol
