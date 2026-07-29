from __future__ import annotations

import base64
import os
from datetime import UTC, datetime

from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, EncryptedCredential
from app.providers.github.client import GitHubClient
from app.security.credentials import CredentialType, CredentialVault
from app.security.crypto import SecretBox, SecurityError
from app.security.redaction import redact_sensitive


def _encoded_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def _make_vault() -> tuple[CredentialVault, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    return CredentialVault(factory, SecretBox({"v1": _encoded_key()})), factory


def test_credential_vault_round_trip_and_row_is_encrypted() -> None:
    vault, factory = _make_vault()

    summary = vault.store(
        project_id=None,
        credential_type=CredentialType.GITHUB_PAT,
        label="demo",
        plaintext="ghp_demo_token",
        key_version="v1",
        created_by="tester",
    )
    resolved = vault.resolve(summary.id)

    assert summary.fingerprint_suffix
    assert resolved.secret == SecretStr("ghp_demo_token")
    assert "ghp_demo_token" not in repr(resolved)

    with factory() as session:
        row = session.get(EncryptedCredential, summary.id)
        assert row is not None
        assert row.ciphertext != b"ghp_demo_token"
        assert row.nonce
        assert row.key_version == "v1"


def test_credential_vault_rejects_empty_plaintext() -> None:
    vault, _ = _make_vault()

    try:
        vault.store(
            project_id=None,
            credential_type=CredentialType.GITHUB_PAT,
            label="demo",
            plaintext="",
            key_version="v1",
            created_by="tester",
        )
    except SecurityError as error:
        assert "empty" in str(error)
    else:
        raise AssertionError("expected SecurityError")


def test_redaction_hides_credentials_and_pat_like_fields() -> None:
    payload = {
        "credential": "ghp_secret",
        "credentials": {"github_pat": "ghp_nested_secret"},
        "nested": {"api_key": "sk_test"},
    }

    redacted = redact_sensitive(payload)

    assert redacted["credential"] == "[REDACTED]"
    assert redacted["credentials"]["github_pat"] == "[REDACTED]"
    assert redacted["nested"]["api_key"] == "[REDACTED]"


def test_github_client_repr_does_not_expose_token() -> None:
    client = GitHubClient(token_provider=lambda: SecretStr("ghp_visible_token"))

    rendered = repr(client)

    assert "ghp_visible_token" not in rendered
    assert "configured" in rendered


def test_mark_validated_updates_timestamp() -> None:
    vault, factory = _make_vault()
    summary = vault.store(
        project_id=None,
        credential_type=CredentialType.GITHUB_PAT,
        label="validate",
        plaintext="ghp_validate_token",
        key_version="v1",
        created_by="tester",
    )
    before = datetime.now(UTC)
    vault.mark_validated(summary.id, validated_at=before)

    resolved = vault.resolve(summary.id)

    assert resolved.last_validated_at is not None
    assert resolved.last_validated_at == before
