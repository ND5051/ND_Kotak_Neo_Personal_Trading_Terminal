"""
Order Persistence Repository.
Phase 7: Order Domain Foundation.
Provides relational database access for orders, order transition events, and trade executions.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select
from sqlalchemy.orm import Session as DbSession

from app.models.db import db_session
from app.orders.models.order import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
    TradeExecution,
    Validity,
)
from app.orders.models.order_entity import (
    OrderEventModel,
    OrderModel,
    TradeExecutionModel,
)
from app.repositories.base import BaseRepository


class OrderRepositoryInterface(ABC):
    """Abstract contract for order persistence operations."""

    @abstractmethod
    def save_order(self, order: Order) -> Order:
        """Persist or update an order entity."""
        pass

    @abstractmethod
    def find_by_client_order_id(self, client_order_id: str) -> Optional[Order]:
        """Lookup order by idempotency token."""
        pass

    @abstractmethod
    def find_by_broker_order_id(self, broker_order_id: str) -> Optional[Order]:
        """Lookup order by broker nOrdNo."""
        pass

    @abstractmethod
    def find_orders(
        self,
        user_id: Optional[int] = None,
        status: Optional[Any] = None,
        symbol: Optional[str] = None,
        segment: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Order]:
        """Query orders with comprehensive filter parameters."""
        pass

    @abstractmethod
    def record_transition(
        self,
        order_id: int,
        client_order_id: str,
        from_status: str,
        to_status: str,
        reason: Optional[str] = None,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> OrderEventModel:
        """Append an immutable state transition event."""
        pass

    @abstractmethod
    def record_trade_execution(self, trade: TradeExecution) -> TradeExecutionModel:
        """Persist an atomic trade execution fill."""
        pass


class OrderRepository(BaseRepository[OrderModel], OrderRepositoryInterface):
    """
    Concrete SQLAlchemy repository handling persistence and relational queries
    for OrderModel, OrderEventModel, and TradeExecutionModel.
    """

    def __init__(self, session: Optional[DbSession] = None) -> None:
        super().__init__(model_class=OrderModel, session=session)

    def save_order(self, order: Order) -> Order:
        """Persist or update an order entity."""
        stmt = select(OrderModel).where(OrderModel.client_order_id == order.client_order_id)
        existing = self.session.execute(stmt).scalars().first()

        if existing:
            # Update fields
            existing.broker_order_id = order.broker_order_id
            existing.exchange_order_id = order.exchange_order_id
            existing.filled_quantity = order.filled_quantity
            existing.pending_quantity = order.pending_quantity
            existing.price = order.price
            existing.trigger_price = order.trigger_price
            existing.average_price = order.average_price
            existing.status = (
                order.status.value if isinstance(order.status, OrderStatus) else str(order.status)
            )
            existing.rejection_reason = order.rejection_reason
            existing.exchange_timestamp = order.exchange_timestamp
            existing.source_timestamp = order.source_timestamp
            existing.retrieved_timestamp = order.retrieved_timestamp
            self.session.commit()
            self.session.refresh(existing)
            return self._entity_to_domain(existing)
        else:
            entity = OrderModel(
                client_order_id=order.client_order_id,
                user_id=order.user_id,
                broker_order_id=order.broker_order_id,
                exchange_order_id=order.exchange_order_id,
                instrument_token=order.instrument_token,
                exchange_segment=order.exchange_segment,
                trading_symbol=order.trading_symbol,
                side=order.side.value if isinstance(order.side, OrderSide) else str(order.side),
                order_type=(
                    order.order_type.value
                    if isinstance(order.order_type, OrderType)
                    else str(order.order_type)
                ),
                product_type=(
                    order.product_type.value
                    if isinstance(order.product_type, ProductType)
                    else str(order.product_type)
                ),
                validity=(
                    order.validity.value
                    if isinstance(order.validity, Validity)
                    else str(order.validity)
                ),
                quantity=order.quantity,
                filled_quantity=order.filled_quantity,
                pending_quantity=order.pending_quantity,
                disclosed_quantity=order.disclosed_quantity,
                price=order.price,
                trigger_price=order.trigger_price,
                average_price=order.average_price,
                status=(
                    order.status.value
                    if isinstance(order.status, OrderStatus)
                    else str(order.status)
                ),
                rejection_reason=order.rejection_reason,
                exchange_timestamp=order.exchange_timestamp,
                source_timestamp=order.source_timestamp,
                retrieved_timestamp=order.retrieved_timestamp,
            )
            self.session.add(entity)
            self.session.commit()
            self.session.refresh(entity)
            return self._entity_to_domain(entity)

    def find_by_client_order_id(self, client_order_id: str) -> Optional[Order]:
        """Lookup order by idempotency token."""
        stmt = select(OrderModel).where(OrderModel.client_order_id == client_order_id.strip())
        res = self.session.execute(stmt).scalars().first()
        return self._entity_to_domain(res) if res else None

    def find_by_broker_order_id(self, broker_order_id: str) -> Optional[Order]:
        """Lookup order by broker nOrdNo."""
        stmt = select(OrderModel).where(OrderModel.broker_order_id == broker_order_id.strip())
        res = self.session.execute(stmt).scalars().first()
        return self._entity_to_domain(res) if res else None

    def find_orders(
        self,
        user_id: Optional[int] = None,
        status: Optional[Any] = None,
        symbol: Optional[str] = None,
        segment: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Order]:
        """Query orders with comprehensive filter parameters."""
        stmt = select(OrderModel)
        if user_id is not None:
            stmt = stmt.where(OrderModel.user_id == user_id)

        if status:
            status_clean = (status.value if hasattr(status, "value") else str(status)).strip().upper()
            if status_clean == "OPEN":
                stmt = stmt.where(
                    OrderModel.status.in_(
                        [
                            OrderStatus.ACKNOWLEDGED.value,
                            OrderStatus.TRIGGER_PENDING.value,
                            OrderStatus.PARTIALLY_FILLED.value,
                            OrderStatus.RECONCILING.value,
                        ]
                    )
                )
            elif status_clean == "COMPLETED":
                stmt = stmt.where(OrderModel.status == OrderStatus.FILLED.value)
            elif status_clean == "REJECTED":
                stmt = stmt.where(
                    OrderModel.status.in_(
                        [OrderStatus.REJECTED.value, OrderStatus.FAILED.value]
                    )
                )
            elif status_clean != "ALL":
                stmt = stmt.where(OrderModel.status == status_clean)

        if symbol:
            stmt = stmt.where(OrderModel.trading_symbol.ilike(f"%{symbol.strip()}%"))

        if segment:
            stmt = stmt.where(OrderModel.exchange_segment == segment.strip().lower())

        stmt = stmt.order_by(desc(OrderModel.created_at)).limit(limit).offset(offset)
        entities = self.session.execute(stmt).scalars().all()
        return [self._entity_to_domain(e) for e in entities]

    def record_transition(
        self,
        order_id: int,
        client_order_id: str,
        from_status: str,
        to_status: str,
        reason: Optional[str] = None,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> OrderEventModel:
        """Append an immutable state transition event."""
        event = OrderEventModel(
            order_id=order_id,
            client_order_id=client_order_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            payload_snapshot=snapshot,
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def record_trade_execution(self, trade: TradeExecution) -> TradeExecutionModel:
        """Persist an atomic trade execution fill."""
        # Find order_id by client_order_id
        stmt = select(OrderModel.id).where(OrderModel.client_order_id == trade.client_order_id)
        order_id = self.session.execute(stmt).scalar() or 0

        model = TradeExecutionModel(
            trade_id=trade.trade_id,
            order_id=order_id,
            client_order_id=trade.client_order_id,
            broker_order_id=trade.broker_order_id,
            fill_quantity=trade.fill_quantity,
            fill_price=trade.fill_price,
            exchange_segment=trade.exchange_segment,
            trading_symbol=trade.trading_symbol,
            exchange_timestamp=trade.exchange_timestamp,
            retrieved_timestamp=trade.retrieved_timestamp,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return model

    def get_order_events(self, client_order_id: str) -> List[OrderEventModel]:
        """Fetch all transition history for an order."""
        stmt = (
            select(OrderEventModel)
            .where(OrderEventModel.client_order_id == client_order_id.strip())
            .order_by(OrderEventModel.id.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_trades(
        self, user_id: Optional[int] = None, limit: int = 100
    ) -> List[TradeExecution]:
        """Query executed trade fills."""
        stmt = select(TradeExecutionModel)
        if user_id is not None:
            stmt = stmt.outerjoin(OrderModel, TradeExecutionModel.order_id == OrderModel.id).where(
                (OrderModel.user_id == user_id) | (TradeExecutionModel.order_id == 0)
            )
        stmt = stmt.order_by(desc(TradeExecutionModel.created_at)).limit(limit)
        models = self.session.execute(stmt).scalars().all()
        return [
            TradeExecution(
                trade_id=m.trade_id,
                client_order_id=m.client_order_id,
                broker_order_id=m.broker_order_id,
                fill_quantity=m.fill_quantity,
                fill_price=m.fill_price,
                exchange_segment=m.exchange_segment,
                trading_symbol=m.trading_symbol,
                exchange_timestamp=m.exchange_timestamp,
                retrieved_timestamp=m.retrieved_timestamp,
            )
            for m in models
        ]

    def _entity_to_domain(self, e: OrderModel) -> Order:
        """Convert OrderModel entity to domain Order dataclass."""
        try:
            status_enum = OrderStatus(e.status)
        except (ValueError, KeyError):
            status_enum = OrderStatus.PENDING_VALIDATION

        try:
            side_enum = OrderSide(e.side)
        except (ValueError, KeyError):
            side_enum = OrderSide.BUY

        try:
            type_enum = OrderType(e.order_type)
        except (ValueError, KeyError):
            type_enum = OrderType.LIMIT

        try:
            prod_enum = ProductType(e.product_type)
        except (ValueError, KeyError):
            prod_enum = ProductType.MIS

        try:
            val_enum = Validity(e.validity)
        except (ValueError, KeyError):
            val_enum = Validity.DAY

        order = Order(
            client_order_id=e.client_order_id,
            user_id=e.user_id,
            broker_order_id=e.broker_order_id,
            exchange_order_id=e.exchange_order_id,
            instrument_token=e.instrument_token,
            exchange_segment=e.exchange_segment,
            trading_symbol=e.trading_symbol,
            side=side_enum,
            order_type=type_enum,
            product_type=prod_enum,
            validity=val_enum,
            quantity=e.quantity,
            filled_quantity=e.filled_quantity,
            pending_quantity=e.pending_quantity,
            disclosed_quantity=e.disclosed_quantity,
            price=e.price,
            trigger_price=e.trigger_price,
            average_price=e.average_price,
            status=status_enum,
            rejection_reason=e.rejection_reason,
            exchange_timestamp=e.exchange_timestamp,
            source_timestamp=e.source_timestamp,
            retrieved_timestamp=e.retrieved_timestamp,
        )
        return order


# Global Singleton Order Repository
order_repository = OrderRepository()
