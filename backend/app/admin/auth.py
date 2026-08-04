from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AdminSession, AdminUser, LoginAudit, new_id

SessionFactory = Callable[[], Session]

ACCESS_COOKIE_NAME = "admin_access_token"
REFRESH_COOKIE_NAME = "admin_refresh_token"
CSRF_COOKIE_NAME = "admin_csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


class AdminAuthError(ValueError):
    pass


class AdminAuthenticationError(AdminAuthError):
    pass


class AdminLockoutError(AdminAuthError):
    pass


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class AdminAuthPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    status: str
    session_expires_at: datetime
    last_login_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class AdminAuthContext:
    user: AdminUser
    session: AdminSession


@dataclass(slots=True, frozen=True)
class AdminAuthResult:
    user: AdminUser
    session: AdminSession
    access_token: str
    refresh_token: str
    csrf_token: str

    def payload(self) -> AdminAuthPayload:
        return AdminAuthPayload(
            username=self.user.username,
            status=self.user.status,
            session_expires_at=_to_utc(self.session.expires_at) or self.session.expires_at,
            last_login_at=_to_utc(self.user.last_login_at),
        )


class AdminAuthService:
    def __init__(self, session_factory: SessionFactory, settings: Settings) -> None:
        self._session_factory = session_factory
        self._settings = settings

    def login(self, request: Request, payload: AdminLoginRequest) -> AdminAuthResult:
        with self._session_factory() as session:
            user = self._get_or_create_user(session)
            if payload.username != user.username:
                self._audit_login(
                    session,
                    username=payload.username,
                    admin_user_id=None,
                    success=False,
                    failure_reason="invalid_credentials",
                    request=request,
                )
                session.commit()
                raise AdminAuthenticationError("invalid credentials")
            self._unlock_if_expired(user)
            if user.status == "disabled":
                self._audit_login(
                    session,
                    username=payload.username,
                    admin_user_id=user.id,
                    success=False,
                    failure_reason="disabled",
                    request=request,
                )
                session.commit()
                raise AdminAuthenticationError("admin account disabled")
            locked_until = _to_utc(user.locked_until)
            if locked_until is not None and locked_until > datetime.now(UTC):
                self._audit_login(
                    session,
                    username=payload.username,
                    admin_user_id=user.id,
                    success=False,
                    failure_reason="locked",
                    request=request,
                )
                session.commit()
                raise AdminLockoutError("admin account locked")
            if not _verify_password(payload.password, user.password_hash):
                user.failed_login_count += 1
                failure_reason = "invalid_credentials"
                if user.failed_login_count >= self._settings.admin_failed_login_limit:
                    user.status = "locked"
                    user.locked_until = datetime.now(UTC) + timedelta(
                        minutes=self._settings.admin_lock_minutes
                    )
                    failure_reason = "locked"
                self._audit_login(
                    session,
                    username=payload.username,
                    admin_user_id=user.id,
                    success=False,
                    failure_reason=failure_reason,
                    request=request,
                )
                session.flush()
                session.commit()
                if failure_reason == "locked":
                    raise AdminLockoutError("admin account locked")
                raise AdminAuthenticationError("invalid credentials")

            self._prepare_user_for_success(user)
            session.query(AdminSession).filter(
                AdminSession.admin_user_id == user.id,
                AdminSession.revoked_at.is_(None),
            ).update({AdminSession.revoked_at: datetime.now(UTC)}, synchronize_session=False)
            auth_result = self._create_session(session, user, request)
            user.last_login_at = datetime.now(UTC)
            self._audit_login(
                session,
                username=payload.username,
                admin_user_id=user.id,
                success=True,
                failure_reason=None,
                request=request,
            )
            session.flush()
            session.commit()
            return auth_result

    def refresh(self, request: Request) -> AdminAuthResult:
        with self._session_factory() as session:
            current_session = self._resolve_refresh_session(session, request)
            if current_session is None:
                raise AdminAuthenticationError("refresh token invalid")
            current_session.revoked_at = datetime.now(UTC)
            user = session.get(AdminUser, current_session.admin_user_id)
            if user is None or user.status != "active":
                session.flush()
                session.commit()
                raise AdminAuthenticationError("admin account unavailable")
            auth_result = self._create_session(session, user, request)
            session.flush()
            session.commit()
            return auth_result

    def logout(self, request: Request) -> None:
        with self._session_factory() as session:
            current_session = self._resolve_access_session(session, request)
            if current_session is None:
                current_session = self._resolve_refresh_session(session, request)
            if current_session is None:
                return
            current_session.revoked_at = datetime.now(UTC)
            session.flush()
            session.commit()

    def current_auth(self, request: Request) -> AdminAuthContext | None:
        with self._session_factory() as session:
            current_session = self._resolve_access_session(session, request)
            if current_session is None:
                return None
            user = session.get(AdminUser, current_session.admin_user_id)
            if user is None or user.status != "active":
                return None
            session.expunge(user)
            session.expunge(current_session)
            return AdminAuthContext(user=user, session=current_session)

    def set_auth_cookies(self, response, result: AdminAuthResult) -> None:
        secure = self._settings.app_profile == "production"
        response.set_cookie(
            ACCESS_COOKIE_NAME,
            result.access_token,
            httponly=True,
            secure=secure,
            samesite="lax",
            path="/",
            max_age=self._settings.admin_access_token_minutes * 60,
        )
        response.set_cookie(
            REFRESH_COOKIE_NAME,
            result.refresh_token,
            httponly=True,
            secure=secure,
            samesite="strict",
            path="/api/v1/admin/auth",
            max_age=self._settings.admin_session_days * 24 * 60 * 60,
        )
        response.set_cookie(
            CSRF_COOKIE_NAME,
            result.csrf_token,
            httponly=False,
            secure=secure,
            samesite="lax",
            path="/",
            max_age=self._settings.admin_session_days * 24 * 60 * 60,
        )

    def clear_auth_cookies(self, response) -> None:
        response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
        response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/admin/auth")
        response.delete_cookie(CSRF_COOKIE_NAME, path="/")

    def resolve_csrf_token(self, request: Request) -> str | None:
        return request.headers.get(CSRF_HEADER_NAME) or request.headers.get("X-XSRF-Token")

    def auth_cookie_present(self, request: Request) -> bool:
        return ACCESS_COOKIE_NAME in request.cookies or REFRESH_COOKIE_NAME in request.cookies

    def _create_session(
        self, session: Session, user: AdminUser, request: Request
    ) -> AdminAuthResult:
        issued_at = datetime.now(UTC)
        expires_at = issued_at + timedelta(days=self._settings.admin_session_days)
        refresh_token = secrets.token_urlsafe(48)
        csrf_token = secrets.token_urlsafe(24)
        row = AdminSession(
            id=new_id(),
            admin_user_id=user.id,
            refresh_token_hash=_hash_secret(refresh_token),
            issued_at=issued_at,
            expires_at=expires_at,
            revoked_at=None,
            ip_hash=_ip_hash(request),
            user_agent_summary=_summarize_user_agent(request),
        )
        session.add(row)
        session.flush()
        access_token = _encode_access_token(
            session_id=row.id,
            issued_at=issued_at,
            expires_at=issued_at + timedelta(minutes=self._settings.admin_access_token_minutes),
            secret=_signing_secret(self._settings),
        )
        row.expires_at = expires_at
        return AdminAuthResult(
            user=user,
            session=row,
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
        )

    def _get_or_create_user(self, session: Session) -> AdminUser:
        user = session.scalar(
            select(AdminUser).where(AdminUser.username == self._settings.admin_username)
        )
        if user is None:
            user = AdminUser(
                id=new_id(),
                username=self._settings.admin_username,
                password_hash=_hash_password(
                    self._settings.admin_initial_password.get_secret_value()
                ),
                status="active",
                failed_login_count=0,
                locked_until=None,
                last_login_at=None,
            )
            session.add(user)
            session.flush()
        return user

    def _prepare_user_for_success(self, user: AdminUser) -> None:
        user.status = "active"
        user.failed_login_count = 0
        user.locked_until = None

    def _unlock_if_expired(self, user: AdminUser) -> None:
        if user.status == "locked" and user.locked_until is not None:
            if user.locked_until <= datetime.now(UTC):
                user.status = "active"
                user.failed_login_count = 0
                user.locked_until = None

    def _audit_login(
        self,
        session: Session,
        *,
        username: str,
        admin_user_id: str | None,
        success: bool,
        failure_reason: str | None,
        request: Request,
    ) -> None:
        session.add(
            LoginAudit(
                id=new_id(),
                admin_user_id=admin_user_id,
                username=username,
                success=success,
                failure_reason=failure_reason,
                ip_hash=_ip_hash(request),
                user_agent_summary=_summarize_user_agent(request),
            )
        )

    def _resolve_access_session(self, session: Session, request: Request) -> AdminSession | None:
        token = request.cookies.get(ACCESS_COOKIE_NAME)
        if not token:
            return None
        parsed = _decode_access_token(token, secret=_signing_secret(self._settings))
        if parsed is None:
            return None
        session_id, expires_at = parsed
        if expires_at <= datetime.now(UTC):
            return None
        row = session.get(AdminSession, session_id)
        if row is None:
            return None
        if row.revoked_at is not None:
            return None
        row_expires_at = _to_utc(row.expires_at)
        if row_expires_at is None or row_expires_at <= datetime.now(UTC):
            return None
        user = session.get(AdminUser, row.admin_user_id)
        if user is None or user.status != "active":
            return None
        return row

    def _resolve_refresh_session(self, session: Session, request: Request) -> AdminSession | None:
        token = request.cookies.get(REFRESH_COOKIE_NAME)
        if not token:
            return None
        token_hash = _hash_secret(token)
        row = session.scalar(
            select(AdminSession).where(AdminSession.refresh_token_hash == token_hash)
        )
        if row is None:
            return None
        if row.revoked_at is not None:
            return None
        row_expires_at = _to_utc(row.expires_at)
        if row_expires_at is None or row_expires_at <= datetime.now(UTC):
            return None
        user = session.get(AdminUser, row.admin_user_id)
        if user is None or user.status != "active":
            return None
        return row


def _hash_password(value: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 210_000
    digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_encode_bytes(salt)}${_encode_bytes(digest)}"


def _verify_password(candidate: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    expected = hashlib.pbkdf2_hmac(
        "sha256",
        candidate.encode("utf-8"),
        _decode_bytes(salt),
        int(iterations),
    )
    return hmac.compare_digest(_encode_bytes(expected), digest)


def _hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _encode_access_token(
    *, session_id: str, issued_at: datetime, expires_at: datetime, secret: str
) -> str:
    payload = f"{session_id}.{int(issued_at.timestamp())}.{int(expires_at.timestamp())}"
    signature = hmac.new(
        secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def _decode_access_token(token: str, *, secret: str) -> tuple[str, datetime] | None:
    parts = token.split(".")
    if len(parts) != 4:
        return None
    session_id, issued_raw, expires_raw, signature = parts
    payload = f"{session_id}.{issued_raw}.{expires_raw}"
    expected = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        expires_at = datetime.fromtimestamp(int(expires_raw), tz=UTC)
    except ValueError:
        return None
    return session_id, expires_at


def _encode_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_bytes(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _signing_secret(settings: Settings) -> str:
    if settings.app_encryption_key is not None:
        return settings.app_encryption_key.get_secret_value()
    if settings.internal_service_token is not None:
        return settings.internal_service_token.get_secret_value()
    return settings.admin_initial_password.get_secret_value()


def _ip_hash(request: Request) -> str | None:
    host = request.client.host if request.client is not None else None
    if not host:
        forwarded = request.headers.get("X-Forwarded-For", "")
        host = forwarded.split(",", maxsplit=1)[0].strip() if forwarded else None
    if not host:
        return None
    return _hash_secret(host)


def _summarize_user_agent(request: Request) -> str | None:
    user_agent = request.headers.get("User-Agent")
    if not user_agent:
        return None
    normalized = " ".join(user_agent.split())
    return normalized[:512]


def _to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
