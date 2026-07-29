from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import SecretStr

from app.core.config import Settings
from app.providers.feishu import (
    FeishuAccessToken,
    FeishuActor,
    FeishuAuthorizationError,
    FeishuIdentityResolver,
    FeishuTokenCache,
)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        app_profile="local-demo",
        feishu_provider="real",
        feishu_app_id="cli-test-app",
        feishu_app_secret=SecretStr("secret"),
        feishu_verification_token=SecretStr("token"),
        feishu_allowed_actor_refs=["ou_123", "tenant:ou_123"],
    )


def test_identity_resolver_accepts_allowed_actor_and_requested_from() -> None:
    resolver = FeishuIdentityResolver(_settings())

    resolved = resolver.resolve_actor(
        FeishuActor(open_id="ou_123", user_id="u_123", tenant_key="tenant"),
        requested_from=["ou_123"],
    )

    assert resolved.actor_ref == "ou_123"
    assert resolved.actor_type == "feishu_user"
    assert resolved.tenant_key == "tenant"


def test_identity_resolver_rejects_unauthorized_actor() -> None:
    resolver = FeishuIdentityResolver(_settings())

    try:
        resolver.resolve_actor(FeishuActor(open_id="ou_999", tenant_key="tenant"))
    except FeishuAuthorizationError as error:
        assert "authorized" in str(error)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected unauthorized actor to be rejected")


def test_token_cache_reuses_and_refreshes_tokens() -> None:
    cache = FeishuTokenCache()
    now = datetime(2026, 7, 29, tzinfo=UTC)
    calls = {"count": 0}

    def refresher() -> FeishuAccessToken:
        calls["count"] += 1
        return FeishuAccessToken(
            access_token=f"token-{calls['count']}",
            expires_at=now + timedelta(minutes=5),
            tenant_key="tenant",
        )

    first = cache.get_or_refresh("tenant", refresher, now=now)
    second = cache.get_or_refresh("tenant", refresher, now=now + timedelta(minutes=1))
    third = cache.get_or_refresh("tenant", refresher, now=now + timedelta(minutes=10))

    assert first.access_token == "token-1"
    assert second.access_token == "token-1"
    assert third.access_token == "token-2"
    assert calls["count"] == 2
