from typing import Optional
import pyotp

from app.logging.logger import get_logger

logger = get_logger("app.auth.totp_service")


class TOTPService:
    """
    Time-based One-Time Password (TOTP) security framework scaffolding.
    Provides cryptographic primitives for future two-factor authentication (2FA).
    No UI or active enforcement in Phase 2.
    """

    @staticmethod
    def generate_secret() -> str:
        """Generate a cryptographically random Base32 TOTP secret."""
        return pyotp.random_base32()

    @staticmethod
    def generate_qr(
        secret: str, username: str, issuer: str = "KotakNeoTerminal"
    ) -> str:
        """
        Generate standard OTPAuth provisioning URI for authenticator apps.
        (e.g., Google Authenticator, Authy).
        """
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=username, issuer_name=issuer)

    @staticmethod
    def verify_token(secret: str, token: str, valid_window: int = 1) -> bool:
        """
        Verify a 6-digit TOTP token against the provided secret.
        Allows standard +/- 1 time-step clock drift.
        """
        if not secret or not token:
            return False
        clean_token = str(token).strip()
        totp = pyotp.TOTP(secret)
        return bool(totp.verify(clean_token, valid_window=valid_window))


# Global Singleton
totp_service = TOTPService()
