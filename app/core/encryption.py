import base64
import hashlib
import os
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

from app.core.exceptions import ConfigurationException, ValidationException


class EncryptionService:
    """
    Symmetric encryption service for securing credentials, broker tokens,
    and sensitive session data at rest using Fernet (AES-128-CBC + HMAC-SHA256).
    """

    def __init__(self, key: Optional[str] = None) -> None:
        self._key = self._resolve_key(key)
        self._cipher = Fernet(self._key)

    @staticmethod
    def _resolve_key(key: Optional[str] = None) -> bytes:
        """Derive a URL-safe base64-encoded 32-byte key suitable for Fernet."""
        raw_key = key or os.getenv("ENCRYPTION_KEY") or os.getenv("SECRET_KEY")
        if not raw_key:
            raise ConfigurationException("EncryptionService requires ENCRYPTION_KEY or SECRET_KEY")

        # Deterministically derive 32 bytes using SHA-256
        hashed = hashlib.sha256(raw_key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(hashed)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string into URL-safe base64 ciphertext string."""
        if plaintext is None:
            raise ValidationException("Plaintext for encryption cannot be None")
        encrypted_bytes = self._cipher.encrypt(plaintext.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt URL-safe base64 ciphertext string into plaintext."""
        if not ciphertext:
            raise ValidationException("Ciphertext for decryption cannot be empty")
        try:
            decrypted_bytes = self._cipher.decrypt(ciphertext.encode("utf-8"))
            return decrypted_bytes.decode("utf-8")
        except InvalidToken as e:
            raise ValidationException("Decryption failed: corrupted ciphertext or invalid key") from e


# Global Singleton instance
encryption_service = EncryptionService()
