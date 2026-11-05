from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Session(BaseModel):
    """
    User session entity tracking authenticated lifetimes and inactivity timeouts.
    """

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationship to user
    user = relationship("User", backref="sessions")

    def is_expired(self) -> bool:
        """Check if the session has passed its expiration timestamp."""
        now = datetime.now(timezone.utc)
        # Ensure timezone-aware comparison
        expiry = self.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return now > expiry or not self.is_active

    def touch(self) -> None:
        """Update last activity timestamp to current UTC time."""
        self.last_activity = datetime.now(timezone.utc)

    def deactivate(self) -> None:
        """Revoke / terminate the session."""
        self.is_active = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "is_active": self.is_active,
            "is_expired": self.is_expired(),
        }

    def __repr__(self) -> str:
        return f"<Session(session_id='{self.session_id[:8]}...', user_id={self.user_id}, active={self.is_active})>"
