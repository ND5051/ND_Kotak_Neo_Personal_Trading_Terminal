from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class BrokerSession(BaseModel):
    """
    Broker session entity representing authenticated connections to third-party brokers.
    All sensitive tokens are stored encrypted at rest via EncryptionService.
    """

    __tablename__ = "broker_sessions"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    broker_name: Mapped[str] = mapped_column(String(32), default="KOTAK_NEO", nullable=False)
    session_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    login_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expiry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationship to user
    user = relationship("User", backref="broker_sessions")

    def is_expired(self) -> bool:
        """Evaluate if the broker session has surpassed its validity horizon."""
        now = datetime.now(timezone.utc)
        expiry = self.expiry_time
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return now > expiry or not self.is_active

    def deactivate(self) -> None:
        """Mark session as inactive upon logout, expiration, or replacement."""
        self.is_active = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata without revealing encrypted or plaintext secret tokens."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "broker_name": self.broker_name,
            "login_time": self.login_time.isoformat() if self.login_time else None,
            "expiry_time": self.expiry_time.isoformat() if self.expiry_time else None,
            "is_active": self.is_active,
            "is_expired": self.is_expired(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"<BrokerSession(id={self.id}, user_id={self.user_id}, "
            f"broker='{self.broker_name}', active={self.is_active})>"
        )
