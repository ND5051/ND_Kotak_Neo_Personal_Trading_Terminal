import os
import re
from typing import Optional, Tuple

from app.auth.models.session import Session
from app.auth.models.user import User
from app.auth.repositories.user_repository import UserRepository
from app.auth.services.session_manager import SessionManager, session_manager
from app.core.audit import (
    audit_logger,
    AuditCategory,
    LOGIN_SUCCESS,
    LOGIN_FAILED,
    LOGOUT,
    PASSWORD_CHANGED,
)
from app.core.exceptions import ValidationException
from app.core.request_context import get_correlation_id, get_request_id
from app.logging.logger import get_logger

logger = get_logger("app.auth.auth_service")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthService:
    """
    Core authentication domain service handling user registration,
    credential verification, password maintenance, and account status.
    """

    def __init__(
        self,
        user_repository: Optional[UserRepository] = None,
        sess_manager: Optional[SessionManager] = None,
    ) -> None:
        self.user_repo = user_repository or UserRepository()
        self.session_manager = sess_manager or session_manager

    def register_user(self, username: str, email: str, password: str) -> User:
        """Register a new system user with salted password hashing."""
        clean_username = (username or "").strip()
        clean_email = (email or "").strip().lower()

        if len(clean_username) < 3:
            raise ValidationException("Username must be at least 3 characters long")
        if not EMAIL_REGEX.match(clean_email):
            raise ValidationException("Invalid email format")

        if self.user_repo.get_by_username(clean_username):
            raise ValidationException(f"Username '{clean_username}' is already registered")
        if self.user_repo.get_by_email(clean_email):
            raise ValidationException(f"Email '{clean_email}' is already registered")

        user = User(
            username=clean_username,
            email=clean_email,
            is_active=True,
        )
        user.set_password(password)
        saved = self.user_repo.add(user)

        audit_logger.record(
            category=AuditCategory.AUTH,
            action="USER_REGISTERED",
            actor=clean_username,
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"user_id": saved.id, "username": clean_username},
        )
        return saved

    def ensure_default_operator(
        self,
        username: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Optional[User]:
        """
        Ensure at least one default authorized operator account exists.
        Does NOT authenticate or establish any session. Operator must explicitly login.
        """
        op_user = username or os.getenv("DEFAULT_OPERATOR_USERNAME", "admin")
        op_email = email or os.getenv("DEFAULT_OPERATOR_EMAIL", "admin@kotakneo.local")
        op_pass = password or os.getenv("DEFAULT_OPERATOR_PASSWORD", "AdminPassword123!")

        try:
            if not self.user_repo.get_by_username(op_user) and not self.user_repo.get_by_email(op_email):
                user = self.register_user(
                    username=op_user,
                    email=op_email,
                    password=op_pass,
                )
                logger.info(
                    f"Default terminal operator '{op_user}' created. Explicit login required.",
                    event="DEFAULT_OPERATOR_CREATED",
                )
                return user
        except Exception as e:
            logger.debug(f"Default operator check skipped: {str(e)}")
        return None

    def authenticate_user(
        self, username_or_email: str, password: str
    ) -> Tuple[User, Session]:
        """Authenticate user credentials and issue an active session."""
        identifier = (username_or_email or "").strip()
        corr_id = get_correlation_id()
        req_id = get_request_id()

        # Lookup by username or email
        user = self.user_repo.get_by_username(identifier)
        if not user and EMAIL_REGEX.match(identifier.lower()):
            user = self.user_repo.get_by_email(identifier.lower())

        if not user:
            audit_logger.record(
                category=AuditCategory.AUTH,
                action=LOGIN_FAILED,
                actor=identifier,
                correlation_id=corr_id,
                request_id=req_id,
                details={"reason": "USER_NOT_FOUND"},
            )
            raise ValidationException("Invalid credentials")

        if not user.is_active:
            audit_logger.record(
                category=AuditCategory.AUTH,
                action=LOGIN_FAILED,
                actor=user.username,
                correlation_id=corr_id,
                request_id=req_id,
                details={"reason": "ACCOUNT_DISABLED"},
            )
            raise ValidationException("User account is disabled")

        if not user.check_password(password):
            audit_logger.record(
                category=AuditCategory.AUTH,
                action=LOGIN_FAILED,
                actor=user.username,
                correlation_id=corr_id,
                request_id=req_id,
                details={"reason": "PASSWORD_MISMATCH"},
            )
            raise ValidationException("Invalid credentials")

        # Create session
        session = self.session_manager.create_session(
            user_id=user.id,
            actor=user.username,
        )

        audit_logger.record(
            category=AuditCategory.AUTH,
            action=LOGIN_SUCCESS,
            actor=user.username,
            correlation_id=corr_id,
            request_id=req_id,
            details={"user_id": user.id, "session_id": session.session_id[:8] + "..."},
        )
        return user, session

    def logout_user(self, session_id: str) -> bool:
        """Revoke session and log audit event."""
        session = self.session_manager.validate_session(session_id)
        actor = str(session.user_id) if session else "unknown"

        result = self.session_manager.destroy_session(session_id)

        audit_logger.record(
            category=AuditCategory.AUTH,
            action=LOGOUT,
            actor=actor,
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"session_id": session_id[:8] + "..."},
        )
        return result

    def change_password(
        self, user_id: int, old_password: str, new_password: str
    ) -> bool:
        """Change a user's password following verification of old password."""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValidationException("User not found")

        if not user.check_password(old_password):
            audit_logger.record(
                category=AuditCategory.AUTH,
                action="PASSWORD_CHANGE_FAILED",
                actor=user.username,
                correlation_id=get_correlation_id(),
                request_id=get_request_id(),
                details={"reason": "OLD_PASSWORD_INCORRECT"},
            )
            raise ValidationException("Current password is incorrect")

        user.set_password(new_password)
        self.user_repo.update(user)

        # Deactivate all active sessions for security
        from app.auth.repositories.session_repository import SessionRepository

        SessionRepository(self.user_repo.session).deactivate_user_sessions(user.id)

        audit_logger.record(
            category=AuditCategory.AUTH,
            action=PASSWORD_CHANGED,
            actor=user.username,
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"user_id": user.id},
        )
        return True

    def disable_user(self, user_id: int) -> bool:
        """Disable a user account and terminate all active sessions."""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValidationException("User not found")

        user.is_active = False
        self.user_repo.update(user)

        from app.auth.repositories.session_repository import SessionRepository

        SessionRepository(self.user_repo.session).deactivate_user_sessions(user.id)

        audit_logger.record(
            category=AuditCategory.AUTH,
            action="USER_DISABLED",
            actor="admin",
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"user_id": user.id, "username": user.username},
        )
        return True

    def enable_user(self, user_id: int) -> bool:
        """Re-enable a previously disabled user account."""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValidationException("User not found")

        user.is_active = True
        self.user_repo.update(user)

        audit_logger.record(
            category=AuditCategory.AUTH,
            action="USER_ENABLED",
            actor="admin",
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"user_id": user.id, "username": user.username},
        )
        return True


# Global Singleton
auth_service = AuthService()
