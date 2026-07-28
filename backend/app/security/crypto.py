import base64
import binascii
import os
from typing import Final

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, ConfigDict, Field


class SecurityError(ValueError):
    """Raised when a secret cannot be safely encrypted or decrypted."""


class EncryptionEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)
    key_version: str = Field(min_length=1)
    nonce: str = Field(min_length=1)
    ciphertext: str = Field(min_length=1)

    def __repr__(self) -> str:
        return (
            f"EncryptionEnvelope(key_version={self.key_version!r}, "
            "nonce='[REDACTED]', ciphertext='[REDACTED]')"
        )


class SecretBox:
    NONCE_BYTES: Final[int] = 12

    def __init__(self, keys: dict[str, str]) -> None:
        try:
            self._keys = {version: self._decode_key(value) for version, value in keys.items()}
        except (ValueError, binascii.Error) as error:
            raise SecurityError("invalid encryption key") from error

    @staticmethod
    def _decode_key(value: str) -> bytes:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        if len(decoded) != 32:
            raise SecurityError("encryption key must be 32 bytes")
        return decoded

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    @staticmethod
    def _decode(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    def encrypt(self, plaintext: str, *, key_version: str) -> EncryptionEnvelope:
        if not plaintext:
            raise SecurityError("plaintext cannot be empty")
        key = self._keys.get(key_version)
        if key is None:
            raise SecurityError("unknown encryption key version")
        nonce = os.urandom(self.NONCE_BYTES)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode(), key_version.encode())
        return EncryptionEnvelope(
            key_version=key_version,
            nonce=self._encode(nonce),
            ciphertext=self._encode(ciphertext),
        )

    def decrypt(self, envelope: EncryptionEnvelope) -> str:
        key = self._keys.get(envelope.key_version)
        if key is None:
            raise SecurityError("unknown encryption key version")
        try:
            plaintext = AESGCM(key).decrypt(
                self._decode(envelope.nonce),
                self._decode(envelope.ciphertext),
                envelope.key_version.encode(),
            )
            return plaintext.decode()
        except Exception as error:
            raise SecurityError("ciphertext authentication failed") from error
