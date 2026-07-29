from __future__ import annotations

import base64
import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EncryptedCredential, new_id
from app.security.crypto import EncryptionEnvelope, SecretBox, SecurityError

SessionFactory = Callable[[], Session]


class CredentialType(StrEnum):
    GITHUB_PAT = "github_pat"
    FEISHU_APP_SECRET = "feishu_app_secret"
    LLM_API_KEY = "llm_api_key"


class CredentialStatus(StrEnum):
    ACTIVE = "active"
    INVALID = "invalid"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(slots=True, frozen=True)
class CredentialSummary:
    id: str
    project_id: str | None
    credential_type: str
    label: str
    status: str
    fingerprint_suffix: str
    expires_at: datetime | None
    last_validated_at: datetime | None


@dataclass(slots=True, frozen=True)
class ResolvedCredential(CredentialSummary):
    secret: SecretStr


class CredentialVault:
    def __init__(self, session_factory: SessionFactory, box: SecretBox) -> None:
        self._session_factory = session_factory
        self._box = box

    def store(
        self,
        *,
        project_id: str | None,
        credential_type: CredentialType | str,
        label: str,
        plaintext: str,
        key_version: str,
        created_by: str,
        updated_by: str | None = None,
        status: CredentialStatus | str = CredentialStatus.ACTIVE,
        expires_at: datetime | None = None,
    ) -> CredentialSummary:
        if not plaintext:
            raise SecurityError("plaintext cannot be empty")
        envelope = self._box.encrypt(plaintext, key_version=key_version)
        fingerprint = _fingerprint(plaintext)
        with self._session_factory() as session:
            record = session.scalar(
                select(EncryptedCredential).where(
                    EncryptedCredential.project_id == project_id,
                    EncryptedCredential.credential_type == str(credential_type),
                    EncryptedCredential.label == label,
                )
            )
            if record is None:
                record = EncryptedCredential(
                    id=new_id(),
                    project_id=project_id,
                    credential_type=str(credential_type),
                    label=label,
                    ciphertext=_decode(envelope.ciphertext),
                    nonce=_decode(envelope.nonce),
                    key_version=envelope.key_version,
                    fingerprint=fingerprint,
                    status=str(status),
                    expires_at=expires_at,
                    last_validated_at=None,
                    created_by=created_by,
                    updated_by=updated_by or created_by,
                )
                session.add(record)
            else:
                record.ciphertext = _decode(envelope.ciphertext)
                record.nonce = _decode(envelope.nonce)
                record.key_version = envelope.key_version
                record.fingerprint = fingerprint
                record.status = str(status)
                record.expires_at = expires_at
                record.updated_by = updated_by or created_by
            session.commit()
            session.refresh(record)
            return _summary(record)

    def resolve(self, credential_id: str) -> ResolvedCredential:
        with self._session_factory() as session:
            record = session.get(EncryptedCredential, credential_id)
            if record is None:
                raise SecurityError(f"unknown credential: {credential_id}")
            secret = self._box.decrypt(
                EncryptionEnvelope(
                    key_version=record.key_version,
                    nonce=_encode(record.nonce),
                    ciphertext=_encode(record.ciphertext),
                )
            )
            summary = _summary(record)
            return ResolvedCredential(
                id=summary.id,
                project_id=summary.project_id,
                credential_type=summary.credential_type,
                label=summary.label,
                status=summary.status,
                fingerprint_suffix=summary.fingerprint_suffix,
                expires_at=summary.expires_at,
                last_validated_at=summary.last_validated_at,
                secret=SecretStr(secret),
            )

    def mark_validated(self, credential_id: str, *, validated_at: datetime | None = None) -> None:
        with self._session_factory() as session:
            record = session.get(EncryptedCredential, credential_id)
            if record is None:
                raise SecurityError(f"unknown credential: {credential_id}")
            record.last_validated_at = validated_at or datetime.now(UTC)
            session.commit()


def _summary(record: EncryptedCredential) -> CredentialSummary:
    return CredentialSummary(
        id=record.id,
        project_id=record.project_id,
        credential_type=record.credential_type,
        label=record.label,
        status=record.status,
        fingerprint_suffix=record.fingerprint[-4:],
        expires_at=_to_utc(record.expires_at),
        last_validated_at=_to_utc(record.last_validated_at),
    )


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
