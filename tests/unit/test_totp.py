import pyotp
from app.auth.services.totp_service import TOTPService


def test_totp_scaffold():
    """Verify TOTP secret generation, provisioning URI format, and verification."""
    svc = TOTPService()

    secret = svc.generate_secret()
    assert secret is not None
    assert len(secret) == 32

    uri = svc.generate_qr(secret, "trader_test", "KotakTerminal")
    assert uri.startswith("otpauth://totp/")
    assert "KotakTerminal" in uri
    assert "trader_test" in uri

    # Verify matching token
    totp = pyotp.TOTP(secret)
    current_token = totp.now()

    assert svc.verify_token(secret, current_token) is True
    assert svc.verify_token(secret, "000000") is False
    assert svc.verify_token("", current_token) is False
