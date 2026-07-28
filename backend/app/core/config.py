from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_profile: Literal["local-demo", "production"] = "local-demo"
    feishu_provider: Literal["fake", "real"] = "fake"
    github_provider: Literal["fake", "real"] = "fake"
    llm_provider: Literal["fake", "real"] = "fake"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://feishu_agent:change-me@127.0.0.1:5432/feishu_agent"
    redis_url: str = "redis://127.0.0.1:6379/0"
    app_encryption_key: SecretStr | None = None
    internal_service_token: SecretStr | None = None

    @model_validator(mode="after")
    def validate_profile(self) -> "Settings":
        providers = (self.feishu_provider, self.github_provider, self.llm_provider)
        if self.app_profile == "production" and "fake" in providers:
            raise ValueError("production cannot use fake providers")
        if self.app_profile == "production" and self.app_encryption_key is None:
            raise ValueError("production requires app_encryption_key")
        return self
