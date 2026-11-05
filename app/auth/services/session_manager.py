from datetime import datetime, timedelta, timezone
import secrets
from typing import Optional

from app.auth.models.session import Session
from app.auth.repositories.session_repository import SessionRepository
from app.core.audit import audit_logger, AuditCategory, SESSION_CREATED, SESSION_EXPIRED
from app.core.request_context import get_correlation_id, get_request_id
from app.logging.logger import get_logger

logger = get_logger("app.auth.session_manager")


class SessionManager:
    """
    Manages user session lifecycle including generation, validation,
    sliding-expiration refreshing, and revocation.
    """

    def __init__(
        self,
        session_repository: Optional[SessionRepository] = None,
        default_duration_hours: int = 24,
    ) -> None:
        self.repo = session_repository or SessionRepository()
        self.default_duration_hours = default_duration_hours

    def create_session(
        self,
        user_id: int,
        duration_hours: Optional[int] = None,
        actor: str = "system",
    ) -> Session:
        """Issue a new cryptographically secure session for a user."""
        hours = duration_hours or self.default_duration_hours
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=hours)
        token = secrets.token_urlsafe(32)

        session_entity = Session(
            session_id=token,
            user_id=user_id,
            expires_at=expires_at,
            last_activity=now,
            is_active=True,
        )
        saved = self.repo.add(session_entity)

        audit_logger.record(
            category=AuditCategory.SESSION,
            action=SESSION_CREATED,
            actor=actor,
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"user_id": user_id, "session_id": token[:8] + "..."},
        )
        return saved

    def validate_session(self, session_id: str) -> Optional[Session]:
        """Validate an active session and update its activity timestamp."""
        if not session_id:
            return None

        session = self.repo.get_by_session_id(session_id)
        if not session:
            return None

        if session.is_expired():
            if session.is_active:
                session.deactivate()
                self.repo.update(session)
                audit_logger.record(
                    category=AuditCategory.SESSION,
                    action=SESSION_EXPIRED,
                    actor=str(session.user_id),
                    correlation_id=get_correlation_id(),
                    request_id=get_request_id(),
                    details={"session_id": session_id[:8] + "..."},
                )
            return None

        # Touch last activity
        session.touch()
        return self.repo.update(session)

    def refresh_session(
        self, session_id: str, extend_hours: Optional[int] = None
    ) -> Optional[Session]:
        """Extend the lifetime of an active session."""
        session = self.validate_session(session_id)
        if not session:
            return None

        hours = extend_hours or self.default_duration_hours
        session.expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
        return self.repo.update(session)

    def expire_session(self, session_id: str) -> bool:
        """Mark a session as expired/inactive."""
        session = self.repo.get_by_session_id(session_id)
        if not session or not session.is_active:
            return False

        session.deactivate()
        self.repo.update(session)

        audit_logger.record(
            category=AuditCategory.SESSION,
            action=SESSION_EXPIRED,
            actor=str(session.user_id),
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"session_id": session_id[:8] + "..."},
        )
        return True

    def destroy_session(self, session_id: str) -> bool:
        """Completely revoke/terminate a session."""
        return self.expire_session(session_id)


# Global Singleton
session_manager = SessionManager()
