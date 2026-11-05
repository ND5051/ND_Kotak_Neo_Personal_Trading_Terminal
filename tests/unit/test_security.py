import pytest
from app.auth.models.user import User
from app.core.encryption import EncryptionService
from app.core.exceptions import ValidationException
from app.core.request_context import (
    RequestContext,
    get_current_context,
    set_current_context,
)


def test_password_hashing_uniqueness():
    """Verify identical passwords generate distinct salted hashes."""
    u1 = User(username="user1", email="u1@test.com")
    u2 = User(username="user2", email="u2@test.com")

    pwd = "SharedSecret123!"
    u1.set_password(pwd)
    u2.set_password(pwd)

    assert u1.password_hash != u2.password_hash
    assert u1.check_password(pwd) is True
    assert u2.check_password(pwd) is True


def test_encryption_service_roundtrip():
    """Verify symmetric encryption and decryption."""
    enc = EncryptionService(key="test-secure-symmetric-key-12345")
    secret = "KotakNeo-Bearer-Token-xyz987654321"

    ciphertext = enc.encrypt(secret)
    assert ciphertext != secret
    assert len(ciphertext) > len(secret)

    decrypted = enc.decrypt(ciphertext)
    assert decrypted == secret


def test_encryption_service_tampering_detection():
    """Verify tampered ciphertext fails decryption."""
    enc = EncryptionService(key="test-secure-symmetric-key-12345")
    ciphertext = enc.encrypt("SensitiveData")

    # Corrupt ciphertext
    tampered = ciphertext[:-4] + "AAAA"
    with pytest.raises(ValidationException):
        enc.decrypt(tampered)


def test_request_context_creation():
    """Verify RequestContext fields and defaults."""
    ctx = RequestContext()
    assert ctx.request_id is not None
    assert ctx.correlation_id is not None
    assert ctx.session_id is None
    assert ctx.user_id is None

    as_dict = ctx.to_dict()
    assert as_dict["request_id"] == ctx.request_id
    assert as_dict["correlation_id"] == ctx.correlation_id


def test_request_context_fallback_outside_request():
    """Verify get_current_context gracefully falls back to system context."""
    ctx = get_current_context()
    assert ctx is not None
    assert ctx.request_id.startswith("sys-")
    assert ctx.correlation_id.startswith("sys-corr-")
