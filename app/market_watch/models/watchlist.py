"""
Watchlist and WatchlistItem Domain Models.
Phase 5: Market Watch Foundation.
Provides persistent storage for user-customized watchlists and pinned scrips.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Watchlist(BaseModel):
    """
    Watchlist entity representing a user's curated collection of instruments.
    Supports display ordering, default watchlist designation, and cascade item deletion.
    """

    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uix_watchlists_user_name"),
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    items: Mapped[List["WatchlistItem"]] = relationship(
        "WatchlistItem",
        back_populates="watchlist",
        cascade="all, delete-orphan",
        order_by="WatchlistItem.position",
        lazy="selectin",
    )

    def to_dict(self, include_items: bool = True) -> Dict[str, Any]:
        """Convert watchlist and its child items to dictionary representation."""
        data = super().to_dict()
        if include_items:
            data["items"] = [item.to_dict() for item in self.items]
            data["item_count"] = len(self.items)
        return data


class WatchlistItem(BaseModel):
    """
    WatchlistItem entity representing an individual instrument pinned inside a watchlist.
    """

    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint(
            "watchlist_id",
            "instrument_token",
            "exchange_segment",
            name="uix_watchlist_item_unique",
        ),
    )

    watchlist_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("watchlists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instrument_token: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    exchange_segment: Mapped[str] = mapped_column(String(16), nullable=False)
    trading_symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    watchlist: Mapped["Watchlist"] = relationship("Watchlist", back_populates="items")

    def to_dict(self) -> Dict[str, Any]:
        """Convert item attributes to dictionary representation."""
        return super().to_dict()
