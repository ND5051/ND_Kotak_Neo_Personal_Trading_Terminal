"""
Basket ORM Entities.
Phase 9: Advanced Orders & Option Strategy Foundation.
Provides relational persistence for baskets, basket legs, and multi-leg transition events.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class BasketModel(BaseModel):
    """
    Relational database entity for baskets.
    Persists strategy type, execution mode, multi-leg configuration, exposure state, and dual timestamps.
    """

    __tablename__ = "baskets"
    __table_args__ = (
        Index("idx_baskets_user_status", "user_id", "status"),
        Index("idx_baskets_strategy", "strategy_type"),
        Index("idx_baskets_client_id", "client_basket_id", unique=True),
    )

    client_basket_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    basket_idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(32), default="CUSTOM", nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(32), default="V1", nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(16), default="DISABLED", nullable=False)
    basket_execution_mode: Mapped[str] = mapped_column(String(16), default="SEQUENTIAL", nullable=False)
    failure_policy: Mapped[str] = mapped_column(String(32), default="ABORT_REMAINING", nullable=False)

    # Status & Exposure States
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False, index=True)
    exposure_state: Mapped[str] = mapped_column(String(32), default="NEUTRAL", nullable=False)

    # Margins and Risk
    estimated_margin: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    margin_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    validation_timestamp: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    source_timestamp: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    retrieved_timestamp: Mapped[str] = mapped_column(
        String(64),
        default=lambda: datetime.now(timezone.utc).isoformat(),
        nullable=False,
    )

    # Relationships
    legs: Mapped[List["BasketLegModel"]] = relationship(
        "BasketLegModel",
        back_populates="basket",
        cascade="all, delete-orphan",
        order_by="BasketLegModel.leg_index",
        lazy="selectin",
    )
    events: Mapped[List["BasketEventModel"]] = relationship(
        "BasketEventModel",
        back_populates="basket",
        cascade="all, delete-orphan",
        order_by="BasketEventModel.id",
        lazy="selectin",
    )


class BasketLegModel(BaseModel):
    """
    Relational database entity for an individual leg of a basket.
    """

    __tablename__ = "basket_legs"
    __table_args__ = (
        Index("idx_basket_legs_basket_idx", "basket_id", "leg_index"),
        Index("idx_basket_legs_order_id", "order_id"),
        Index("idx_basket_legs_broker_id", "broker_order_id"),
    )

    basket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("baskets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leg_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trading_symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    exchange_segment: Mapped[str] = mapped_column(String(16), default="nse_fo", nullable=False)
    instrument_token: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), default="LIMIT", nullable=False)
    product_type: Mapped[str] = mapped_column(String(16), default="MIS", nullable=False)
    validity: Mapped[str] = mapped_column(String(8), default="DAY", nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    trigger_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Execution State
    order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    broker_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING_VALIDATION", nullable=False)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    depends_on_leg_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationship
    basket: Mapped["BasketModel"] = relationship("BasketModel", back_populates="legs")


class BasketEventModel(BaseModel):
    """
    Append-only audit trail recording every state and exposure transition on a basket.
    """

    __tablename__ = "basket_events"
    __table_args__ = (
        Index("idx_basket_events_basket", "basket_id"),
        Index("idx_basket_events_client_id", "client_basket_id"),
    )

    basket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("baskets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_basket_id: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    from_exposure: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    to_exposure: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    source_timestamp: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    retrieved_timestamp: Mapped[str] = mapped_column(
        String(64),
        default=lambda: datetime.now(timezone.utc).isoformat(),
        nullable=False,
    )

    basket: Mapped["BasketModel"] = relationship("BasketModel", back_populates="events")
