import base64
import os

import pytest

from app.security.crypto import EncryptionEnvelope, SecretBox, SecurityError


def encoded_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def test_aead_round_trip_contains_key_version_and_nonce() -> None:
    box = SecretBox({"v1": encoded_key()})

    envelope = box.encrypt("credential-value", key_version="v1")

    assert isinstance(envelope, EncryptionEnvelope)
    assert envelope.key_version == "v1"
    assert envelope.nonce
    assert box.decrypt(envelope) == "credential-value"
    assert "credential-value" not in repr(envelope)


def test_aead_rejects_tampering_and_wrong_key() -> None:
    envelope = SecretBox({"v1": encoded_key()}).encrypt("credential-value", key_version="v1")
    tampered = envelope.model_copy(update={"ciphertext": envelope.ciphertext[:-1] + "A"})

    with pytest.raises(SecurityError):
        SecretBox({"v1": encoded_key()}).decrypt(envelope)
    with pytest.raises(SecurityError):
        SecretBox({"v1": encoded_key()}).decrypt(tampered)


def test_aead_rejects_empty_plaintext() -> None:
    box = SecretBox({"v1": encoded_key()})

    with pytest.raises(SecurityError, match="empty"):
        box.encrypt("", key_version="v1")
