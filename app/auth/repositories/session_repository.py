from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session as DbSession

from app.auth.models.session import Session
from app.repositories.base import BaseRepository


class SessionRepository(BaseRepository[Session]):
    """Repository handling persistence and lookup for Session entities."""

    def __init__(self, session: Optional[DbSession] = None) -> None:
        super().__init__(model_class=Session, session=session)

    def get_by_session_id(self, session_id: str) -> Optional[Session]:
        """Fetch session entity by its unique session token."""
        stmt = select(Session).where(Session.session_id == session_id.strip())
        return self.session.execute(stmt).scalar_one_or_none()

    def get_active_user_sessions(self, user_id: int) -> List[Session]:
        """Fetch all non-expired active sessions for a user."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(Session)
            .where(
                Session.user_id == user_id,
                Session.is_active == True,
                Session.expires_at > now,
            )
        )
        return list(self.session.execute(stmt).scalars().all())

    def deactivate_user_sessions(self, user_id: int) -> int:
        """Deactivate all active sessions for a user (e.g. on logout-all or password change)."""
        stmt = (
            update(Session)
            .where(Session.user_id == user_id, Session.is_active == True)
            .values(is_active=False)
        )
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount
