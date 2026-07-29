from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from threading import Lock

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.providers.feishu.models import FeishuActor, FeishuResolvedActor


class FeishuAuthError(ValueError):
    pass


class FeishuAuthorizationError(FeishuAuthError):
    pass


class FeishuAccessToken(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: str = Field(min_length=1)
    expires_at: datetime
    tenant_key: str | None = None


class FeishuTokenCache:
    def __init__(self) -> None:
        self._lock = Lock()
        self._entry_locks: dict[str, Lock] = {}
        self._tokens: dict[str, FeishuAccessToken] = {}

    def get(self, cache_key: str, *, now: datetime | None = None) -> FeishuAccessToken | None:
        token = self._tokens.get(cache_key)
        if token is None:
            return None
        current = now or datetime.now(UTC)
        if token.expires_at <= current + timedelta(seconds=60):
            return None
        return token

    def get_or_refresh(
        self,
        cache_key: str,
        refresher: Callable[[], FeishuAccessToken],
        *,
        now: datetime | None = None,
    ) -> FeishuAccessToken:
        cached = self.get(cache_key, now=now)
        if cached is not None:
            return cached

        lock = self._entry_lock(cache_key)
        with lock:
            cached = self.get(cache_key, now=now)
            if cached is not None:
                return cached
            refreshed = refresher()
            self._tokens[cache_key] = refreshed
            return refreshed

    def _entry_lock(self, cache_key: str) -> Lock:
        with self._lock:
            lock = self._entry_locks.get(cache_key)
            if lock is None:
                lock = Lock()
                self._entry_locks[cache_key] = lock
            return lock


class FeishuIdentityResolver:
    def __init__(self, settings: Settings) -> None:
        self._allowed_actor_refs = tuple(settings.feishu_allowed_actor_refs)
        self._callback_max_skew = timedelta(seconds=settings.feishu_callback_max_skew_seconds)

    @property
    def callback_max_skew(self) -> timedelta:
        return self._callback_max_skew

    def resolve_actor(
        self, actor: FeishuActor, requested_from: Sequence[str] | None = None
    ) -> FeishuResolvedActor:
        actor_ref = self._actor_ref(actor)
        refs = self._actor_references(actor)
        self._require_present(refs)
        self._require_allowed(refs)
        if requested_from is not None and not self._matches_requested_from(refs, requested_from):
            raise FeishuAuthorizationError("actor is not allowed for this approval")
        return FeishuResolvedActor(
            actor_ref=actor_ref,
            open_id=actor.open_id,
            user_id=actor.user_id,
            tenant_key=actor.tenant_key,
        )

    def _require_present(self, refs: tuple[str, ...]) -> None:
        if not refs:
            raise FeishuAuthorizationError("feishu actor identity is missing")

    def _require_allowed(self, refs: tuple[str, ...]) -> None:
        if self._allowed_actor_refs and not set(refs).intersection(self._allowed_actor_refs):
            raise FeishuAuthorizationError("feishu actor is not authorized")

    def _matches_requested_from(self, refs: tuple[str, ...], requested_from: Sequence[str]) -> bool:
        return bool(set(refs).intersection(str(ref) for ref in requested_from if str(ref)))

    def _actor_references(self, actor: FeishuActor) -> tuple[str, ...]:
        references: list[str] = []
        if actor.open_id:
            references.append(actor.open_id)
        if actor.user_id and actor.user_id not in references:
            references.append(actor.user_id)
        if actor.tenant_key and actor.tenant_key not in references:
            references.append(actor.tenant_key)
        if actor.open_id and actor.tenant_key:
            tenant_scoped = f"{actor.tenant_key}:{actor.open_id}"
            if tenant_scoped not in references:
                references.append(tenant_scoped)
        return tuple(references)

    def _actor_ref(self, actor: FeishuActor) -> str:
        if actor.open_id:
            return actor.open_id
        if actor.user_id:
            return actor.user_id
        if actor.tenant_key:
            return actor.tenant_key
        raise FeishuAuthorizationError("feishu actor identity is missing")
