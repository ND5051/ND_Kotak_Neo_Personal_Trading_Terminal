import pytest
from app.core.encryption import EncryptionService
from app.core.exceptions import ValidationException


def test_encrypted_storage_never_plaintext():
    """Verify stored token ciphertext cannot be decoded without secret key."""
    enc = EncryptionService(key="primary-secret-key-12345")
    secret_token = "Kotak-Session-Token-UltraSecret-987654"

    ciphertext = enc.encrypt(secret_token)
    assert secret_token not in ciphertext
    assert enc.decrypt(ciphertext) == secret_token


def test_failed_decryption_on_corrupt_data():
    """Verify that corrupting ciphertext raises ValidationException rather than crashing."""
    enc = EncryptionService(key="primary-secret-key-12345")
    ciphertext = enc.encrypt("SecretBrokerData")

    corrupted = "gAAAAAB" + ciphertext[7:-5] + "XXXXX"
    with pytest.raises(ValidationException) as exc_info:
        enc.decrypt(corrupted)
    assert "Decryption failed" in str(exc_info.value)


def test_key_rotation_handling():
    """Verify migrating data between an old key and new key."""
    old_enc = EncryptionService(key="old-legacy-key-phase2")
    new_enc = EncryptionService(key="new-rotated-key-phase3")

    secret = "KotakTokenPriorToRotation"
    old_ciphertext = old_enc.encrypt(secret)

    # Cannot decrypt with new key directly
    with pytest.raises(ValidationException):
        new_enc.decrypt(old_ciphertext)

    # Rotation flow: decrypt with old, re-encrypt with new
    plain = old_enc.decrypt(old_ciphertext)
    new_ciphertext = new_enc.encrypt(plain)

    assert new_enc.decrypt(new_ciphertext) == secret

