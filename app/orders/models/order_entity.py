"""
Order ORM Entities.
Phase 7: Order Domain Foundation.
Provides relational persistence for orders, state transition history, and trade execution fills.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class OrderModel(BaseModel):
    """
    Relational database entity for orders.
    Persists order parameters, exchange IDs, current state, and dual timestamps.
    """

    __tablename__ = "orders"
    __table_args__ = (
        Index("idx_orders_user_status", "user_id", "status"),
        Index("idx_orders_broker_id", "broker_order_id"),
        Index("idx_orders_symbol", "trading_symbol"),
    )

    client_order_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    broker_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    exchange_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Scrip Parameters
    instrument_token: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange_segment: Mapped[str] = mapped_column(String(16), nullable=False)
    trading_symbol: Mapped[str] = mapped_column(String(64), nullable=False)

    # Order Specifications
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    product_type: Mapped[str] = mapped_column(String(16), nullable=False)
    validity: Mapped[str] = mapped_column(String(8), default="DAY", nullable=False)

    # Financial Values
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pending_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    disclosed_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    trigger_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    average_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Lifecycle & Status
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    exchange_timestamp: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_timestamp: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    retrieved_timestamp: Mapped[str] = mapped_column(
        String(64),
        default=lambda: datetime.now(timezone.utc).isoformat(),
        nullable=False,
    )

    # Relationships
    events: Mapped[List["OrderEventModel"]] = relationship(
        "OrderEventModel",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderEventModel.id",
        lazy="selectin",
    )
    executions: Mapped[List["TradeExecutionModel"]] = relationship(
        "TradeExecutionModel",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="TradeExecutionModel.id",
        lazy="selectin",
    )


class OrderEventModel(BaseModel):
    """
    Immutable audit history record capturing individual order state transitions.
    """

    __tablename__ = "order_events"
    __table_args__ = (
        Index("idx_order_events_order_id", "order_id"),
        Index("idx_order_events_client_order_id", "client_order_id"),
    )

    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    client_order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationship
    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="events")


class TradeExecutionModel(BaseModel):
    """
    Relational record representing an atomic partial or full trade execution fill.
    """

    __tablename__ = "trade_executions"
    __table_args__ = (
        Index("idx_trade_executions_order_id", "order_id"),
        Index("idx_trade_executions_client_order_id", "client_order_id"),
    )

    trade_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    client_order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    fill_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    fill_price: Mapped[float] = mapped_column(Float, nullable=False)
    exchange_segment: Mapped[str] = mapped_column(String(16), nullable=False)
    trading_symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    exchange_timestamp: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieved_timestamp: Mapped[str] = mapped_column(
        String(64),
        default=lambda: datetime.now(timezone.utc).isoformat(),
        nullable=False,
    )

    # Relationship
    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="executions")
