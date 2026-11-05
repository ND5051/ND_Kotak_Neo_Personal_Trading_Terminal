from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session as DbSession

from app.broker.models.broker_session import BrokerSession
from app.repositories.base import BaseRepository


class BrokerSessionRepository(BaseRepository[BrokerSession]):
    """
    Data repository managing BrokerSession persistence, active session lookup,
    and lifecycle invalidation.
    """

    def __init__(self, session: Optional[DbSession] = None) -> None:
        super().__init__(model_class=BrokerSession, session=session)

    def get_active_session(
        self, user_id: int, broker_name: str = "KOTAK_NEO"
    ) -> Optional[BrokerSession]:
        """Fetch current non-expired active broker session for a specific user and broker."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(BrokerSession)
            .where(
                BrokerSession.user_id == user_id,
                BrokerSession.broker_name == broker_name,
                BrokerSession.is_active == True,
                BrokerSession.expiry_time > now,
            )
            .order_by(BrokerSession.id.desc())
        )
        return self.session.execute(stmt).scalars().first()

    def save_session(self, session_entity: BrokerSession) -> BrokerSession:
        """Persist a new broker session entity."""
        return self.add(session_entity)

    def update_session(self, session_entity: BrokerSession) -> BrokerSession:
        """Update and commit modifications to an existing broker session."""
        return self.update(session_entity)

    def invalidate_session(self, session_id: int) -> bool:
        """Deactivate a single broker session by primary key."""
        sess = self.get_by_id(session_id)
        if sess and sess.is_active:
            sess.deactivate()
            self.session.commit()
            return True
        return False

    def invalidate_all_user_sessions(
        self, user_id: int, broker_name: str = "KOTAK_NEO"
    ) -> int:
        """Deactivate all active broker sessions for a user."""
        stmt = (
            update(BrokerSession)
            .where(
                BrokerSession.user_id == user_id,
                BrokerSession.broker_name == broker_name,
                BrokerSession.is_active == True,
            )
            .values(is_active=False)
        )
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount

    def cleanup_expired_sessions(self, cutoff: Optional[datetime] = None) -> int:
        """Mark all past-expiry sessions as inactive."""
        threshold = cutoff or datetime.now(timezone.utc)
        stmt = (
            update(BrokerSession)
            .where(
                BrokerSession.is_active == True,
                BrokerSession.expiry_time <= threshold,
            )
            .values(is_active=False)
        )
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount
