from datetime import datetime, timedelta, timezone
from typing import Optional

from app.broker.interfaces.broker_interface import BrokerInterface
from app.broker.models.broker_session import BrokerSession
from app.broker.repositories.broker_session_repository import BrokerSessionRepository
from app.core.audit import (
    audit_logger,
    AuditCategory,
    BROKER_SESSION_CREATED,
    BROKER_SESSION_RESTORED,
    BROKER_SESSION_EXPIRED,
    BROKER_LOGOUT,
)
from app.core.encryption import EncryptionService, encryption_service
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import (
    BROKER_CONNECTED,
    BROKER_DISCONNECTED,
    BROKER_AUTHENTICATED,
    BROKER_SESSION_RESTORED,
    BROKER_SESSION_EXPIRED as EVT_BROKER_SESSION_EXPIRED,
)
from app.logging.logger import get_logger

logger = get_logger("app.broker.services.broker_session_manager")


class BrokerSessionManager:
    """
    Dedicated manager for third-party broker sessions and secure token lifecycles.
    Decoupled from local user sessions. Handles encryption, validation,
    automatic startup recovery, and audit tracking.
    """

    def __init__(
        self,
        repository: Optional[BrokerSessionRepository] = None,
        encryption: Optional[EncryptionService] = None,
    ) -> None:
        self.repo = repository or BrokerSessionRepository()
        self.encryption = encryption or encryption_service

    def create_session(
        self,
        user_id: int,
        session_token: str,
        refresh_token: Optional[str] = None,
        expiry_time: Optional[datetime] = None,
        broker_name: str = "KOTAK_NEO",
        actor: str = "system",
    ) -> BrokerSession:
        """Encrypt and persist new broker credentials, deactivating previous broker sessions."""
        now = datetime.now(timezone.utc)
        resolved_expiry = expiry_time or (now + timedelta(hours=8))

        # Encrypt sensitive tokens using Phase 2 EncryptionService
        encrypted_session = self.encryption.encrypt(session_token)
        encrypted_refresh = self.encryption.encrypt(refresh_token) if refresh_token else None

        # Deactivate any previous active sessions for this broker and user
        self.repo.invalidate_all_user_sessions(user_id=user_id, broker_name=broker_name)

        session_entity = BrokerSession(
            user_id=user_id,
            broker_name=broker_name,
            session_token_encrypted=encrypted_session,
            refresh_token_encrypted=encrypted_refresh,
            login_time=now,
            expiry_time=resolved_expiry,
            is_active=True,
        )
        saved = self.repo.save_session(session_entity)

        corr_id = get_correlation_id()
        req_id = get_request_id()

        audit_logger.record(
            category=AuditCategory.BROKER,
            action=BROKER_SESSION_CREATED,
            actor=actor,
            correlation_id=corr_id,
            request_id=req_id,
            details={
                "broker_session_id": saved.id,
                "user_id": user_id,
                "broker": broker_name,
                "expiry_time": resolved_expiry.isoformat(),
            },
        )

        publish(BROKER_CONNECTED, {"user_id": user_id, "broker": broker_name})
        publish(BROKER_AUTHENTICATED, {"user_id": user_id, "broker": broker_name})

        return saved

    def validate_session(
        self,
        user_id: int,
        adapter: Optional[BrokerInterface] = None,
        broker_name: str = "KOTAK_NEO",
    ) -> bool:
        """Validate if active broker session exists, is unexpired, and functional."""
        active_sess = self.repo.get_active_session(user_id=user_id, broker_name=broker_name)
        if not active_sess:
            return False

        if active_sess.is_expired():
            self.expire_session(active_sess.id, actor=str(user_id))
            return False

        if adapter is not None:
            if not adapter.validate_session():
                self.expire_session(active_sess.id, actor=str(user_id))
                return False

        return True

    def restore_session(
        self,
        user_id: int,
        adapter: BrokerInterface,
        broker_name: str = "KOTAK_NEO",
        actor: str = "system",
    ) -> bool:
        """
        Locate active broker session, decrypt credentials, and restore connectivity.
        Marks session inactive without user intervention if decryption or validation fails.
        """
        active_sess = self.repo.get_active_session(user_id=user_id, broker_name=broker_name)
        if not active_sess or active_sess.is_expired():
            logger.info("No active unexpired broker session found for recovery", user_id=user_id)
            return False

        corr_id = get_correlation_id()
        req_id = get_request_id()

        # Decrypt stored credentials
        try:
            decrypted_session_token = self.encryption.decrypt(active_sess.session_token_encrypted)
            decrypted_refresh_token = (
                self.encryption.decrypt(active_sess.refresh_token_encrypted)
                if active_sess.refresh_token_encrypted
                else None
            )
        except Exception as e:
            logger.error(
                f"Decryption failure during broker session restore: {str(e)}",
                event="BROKER_RESTORE_DECRYPT_FAIL",
                exc_info=True,
            )
            self.expire_session(active_sess.id, actor=actor)
            return False

        # Attempt restoration on the adapter
        session_payload = {
            "session_token": decrypted_session_token,
            "refresh_token": decrypted_refresh_token,
            "expiry_time": active_sess.expiry_time,
            "broker_name": broker_name,
        }

        success = adapter.restore_session(session_payload)
        if success:
            audit_logger.record(
                category=AuditCategory.BROKER,
                action=BROKER_SESSION_RESTORED,
                actor=actor,
                correlation_id=corr_id,
                request_id=req_id,
                details={"broker_session_id": active_sess.id, "broker": broker_name},
            )
            publish(BROKER_SESSION_RESTORED, {"user_id": user_id, "broker": broker_name})
            return True
        else:
            self.expire_session(active_sess.id, actor=actor)
            return False

    def expire_session(self, session_id: int, actor: str = "system") -> bool:
        """Mark a broker session as expired/inactive."""
        sess = self.repo.get_by_id(session_id)
        if not sess or not sess.is_active:
            return False

        self.repo.invalidate_session(session_id)

        corr_id = get_correlation_id()
        req_id = get_request_id()

        audit_logger.record(
            category=AuditCategory.BROKER,
            action=BROKER_SESSION_EXPIRED,
            actor=actor,
            correlation_id=corr_id,
            request_id=req_id,
            details={"broker_session_id": session_id, "broker": sess.broker_name},
        )
        publish(EVT_BROKER_SESSION_EXPIRED, {"broker_session_id": session_id})
        return True

    def destroy_session(
        self,
        user_id: int,
        adapter: Optional[BrokerInterface] = None,
        broker_name: str = "KOTAK_NEO",
        actor: str = "system",
    ) -> bool:
        """Log out from broker adapter and deactivate all associated broker sessions."""
        if adapter is not None:
            adapter.logout()

        count = self.repo.invalidate_all_user_sessions(user_id=user_id, broker_name=broker_name)

        corr_id = get_correlation_id()
        req_id = get_request_id()

        audit_logger.record(
            category=AuditCategory.BROKER,
            action=BROKER_LOGOUT,
            actor=actor,
            correlation_id=corr_id,
            request_id=req_id,
            details={"user_id": user_id, "broker": broker_name, "sessions_invalidated": count},
        )
        publish(BROKER_DISCONNECTED, {"user_id": user_id, "broker": broker_name})
        return True


# Global Singleton
broker_session_manager = BrokerSessionManager()

