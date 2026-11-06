"""
Basket Persistence Repository.
Phase 9: Advanced Orders & Option Strategy Foundation.
Provides relational database access for multi-leg baskets, basket legs, and transition history.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select
from sqlalchemy.orm import Session as DbSession

from app.baskets.models.basket import (
    Basket,
    BasketEventRecord,
    BasketExecutionMode,
    BasketExposureState,
    BasketFailurePolicy,
    BasketLeg,
    BasketState,
    StrategyType,
)
from app.baskets.models.basket_entity import (
    BasketEventModel,
    BasketLegModel,
    BasketModel,
)
from app.models.db import db_session
from app.orders.models.execution_mode import ExecutionMode
from app.orders.models.order import (
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
    Validity,
)
from app.repositories.base import BaseRepository


class BasketRepositoryInterface(ABC):
    """Abstract contract for basket persistence operations."""

    @abstractmethod
    def save_basket(self, basket: Basket) -> Basket:
        """Persist or update a basket entity and its legs."""
        pass

    @abstractmethod
    def get_basket_by_id(self, basket_id: str) -> Optional[Basket]:
        """Lookup basket by internal UUID."""
        pass

    @abstractmethod
    def get_basket_by_client_id(self, client_basket_id: str) -> Optional[Basket]:
        """Lookup basket by client idempotency token."""
        pass

    @abstractmethod
    def find_baskets(
        self,
        user_id: Optional[int] = None,
        status: Optional[Any] = None,
        strategy_type: Optional[Any] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Basket]:
        """Query baskets with filter parameters."""
        pass

    @abstractmethod
    def record_transition(
        self,
        basket_id: str,
        client_basket_id: str,
        from_status: str,
        to_status: str,
        from_exposure: str = "",
        to_exposure: str = "",
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        source_timestamp: Optional[str] = None,
    ) -> BasketEventRecord:
        """Append an immutable state transition record."""
        pass

    @abstractmethod
    def get_basket_events(self, client_basket_id: str) -> List[BasketEventRecord]:
        """Retrieve transition timeline for a specific basket."""
        pass

    @abstractmethod
    def delete_basket(self, basket_id: str) -> bool:
        """Delete a basket (only permitted if in DRAFT state)."""
        pass


class BasketRepository(BaseRepository[BasketModel], BasketRepositoryInterface):
    """
    Production Basket Repository implementation.
    Manages relational mapping between Basket domain dataclasses and SQLAlchemy models.
    """

    def __init__(self, session: Optional[DbSession] = None, session_factory=None) -> None:
        super().__init__(model_class=BasketModel, session=session)
        self._session_factory = session_factory

    def _get_session(self) -> DbSession:
        if self._session_factory:
            return self._session_factory()
        return self.session

    def save_basket(self, basket: Basket) -> Basket:
        session = self._get_session()
        existing = session.execute(
            select(BasketModel).where(BasketModel.client_basket_id == basket.client_basket_id)
        ).scalar_one_or_none()

        if existing is None:
            # Create new
            entity = BasketModel(
                client_basket_id=basket.client_basket_id,
                basket_idempotency_key=basket.basket_idempotency_key,
                user_id=basket.user_id,
                name=basket.name,
                strategy_type=basket.strategy_type.value if isinstance(basket.strategy_type, StrategyType) else str(basket.strategy_type),
                strategy_version=basket.strategy_version,
                execution_mode=basket.execution_mode.value if isinstance(basket.execution_mode, ExecutionMode) else str(basket.execution_mode),
                basket_execution_mode=basket.basket_execution_mode.value if isinstance(basket.basket_execution_mode, BasketExecutionMode) else str(basket.basket_execution_mode),
                failure_policy=basket.failure_policy.value if isinstance(basket.failure_policy, BasketFailurePolicy) else str(basket.failure_policy),
                status=basket.status.value if isinstance(basket.status, BasketState) else str(basket.status),
                exposure_state=basket.exposure_state.value if isinstance(basket.exposure_state, BasketExposureState) else str(basket.exposure_state),
                estimated_margin=float(basket.estimated_margin),
                margin_snapshot=basket.margin_snapshot,
                validation_timestamp=basket.validation_timestamp,
                rejection_reason=basket.rejection_reason,
                source_timestamp=basket.source_timestamp,
                retrieved_timestamp=basket.retrieved_timestamp,
            )
            # Add legs
            for leg in basket.legs:
                leg_entity = BasketLegModel(
                    leg_index=leg.leg_index,
                    trading_symbol=leg.trading_symbol,
                    exchange_segment=leg.exchange_segment,
                    instrument_token=leg.instrument_token,
                    side=leg.side.value if isinstance(leg.side, OrderSide) else str(leg.side),
                    order_type=leg.order_type.value if isinstance(leg.order_type, OrderType) else str(leg.order_type),
                    product_type=leg.product_type.value if isinstance(leg.product_type, ProductType) else str(leg.product_type),
                    validity=leg.validity.value if isinstance(leg.validity, Validity) else str(leg.validity),
                    quantity=int(leg.quantity),
                    price=float(leg.price),
                    trigger_price=float(leg.trigger_price),
                    order_id=leg.order_id,
                    broker_order_id=leg.broker_order_id,
                    status=leg.status.value if isinstance(leg.status, OrderStatus) else str(leg.status),
                    filled_quantity=int(leg.filled_quantity),
                    average_price=float(leg.average_price),
                    depends_on_leg_index=leg.depends_on_leg_index,
                )
                entity.legs.append(leg_entity)

            session.add(entity)
            session.commit()
            session.refresh(entity)
            basket.basket_id = str(entity.id)
            return basket
        else:
            # Update existing
            existing.status = basket.status.value if isinstance(basket.status, BasketState) else str(basket.status)
            existing.exposure_state = basket.exposure_state.value if isinstance(basket.exposure_state, BasketExposureState) else str(basket.exposure_state)
            existing.execution_mode = basket.execution_mode.value if isinstance(basket.execution_mode, ExecutionMode) else str(basket.execution_mode)
            existing.estimated_margin = float(basket.estimated_margin)
            existing.margin_snapshot = basket.margin_snapshot
            existing.validation_timestamp = basket.validation_timestamp
            existing.rejection_reason = basket.rejection_reason
            existing.source_timestamp = basket.source_timestamp
            existing.retrieved_timestamp = basket.retrieved_timestamp

            # Synchronize legs
            leg_map = {l.leg_index: l for l in existing.legs}
            for domain_leg in basket.legs:
                if domain_leg.leg_index in leg_map:
                    le = leg_map[domain_leg.leg_index]
                    le.status = domain_leg.status.value if isinstance(domain_leg.status, OrderStatus) else str(domain_leg.status)
                    le.filled_quantity = int(domain_leg.filled_quantity)
                    le.average_price = float(domain_leg.average_price)
                    le.order_id = domain_leg.order_id
                    le.broker_order_id = domain_leg.broker_order_id
                    le.depends_on_leg_index = domain_leg.depends_on_leg_index
                else:
                    new_le = BasketLegModel(
                        leg_index=domain_leg.leg_index,
                        trading_symbol=domain_leg.trading_symbol,
                        exchange_segment=domain_leg.exchange_segment,
                        instrument_token=domain_leg.instrument_token,
                        side=domain_leg.side.value if isinstance(domain_leg.side, OrderSide) else str(domain_leg.side),
                        order_type=domain_leg.order_type.value if isinstance(domain_leg.order_type, OrderType) else str(domain_leg.order_type),
                        product_type=domain_leg.product_type.value if isinstance(domain_leg.product_type, ProductType) else str(domain_leg.product_type),
                        validity=domain_leg.validity.value if isinstance(domain_leg.validity, Validity) else str(domain_leg.validity),
                        quantity=int(domain_leg.quantity),
                        price=float(domain_leg.price),
                        trigger_price=float(domain_leg.trigger_price),
                        order_id=domain_leg.order_id,
                        broker_order_id=domain_leg.broker_order_id,
                        status=domain_leg.status.value if isinstance(domain_leg.status, OrderStatus) else str(domain_leg.status),
                        filled_quantity=int(domain_leg.filled_quantity),
                        average_price=float(domain_leg.average_price),
                        depends_on_leg_index=domain_leg.depends_on_leg_index,
                    )
                    existing.legs.append(new_le)

            session.commit()
            basket.basket_id = str(existing.id)
            return basket

    def get_basket_by_id(self, basket_id: str) -> Optional[Basket]:
        session = self._get_session()
        try:
            int_id = int(basket_id)
            entity = session.execute(select(BasketModel).where(BasketModel.id == int_id)).scalar_one_or_none()
        except ValueError:
            entity = session.execute(select(BasketModel).where(BasketModel.client_basket_id == basket_id)).scalar_one_or_none()
        return self._to_domain(entity) if entity else None

    def get_basket_by_client_id(self, client_basket_id: str) -> Optional[Basket]:
        session = self._get_session()
        entity = session.execute(
            select(BasketModel).where(BasketModel.client_basket_id == client_basket_id)
        ).scalar_one_or_none()
        return self._to_domain(entity) if entity else None

    def find_baskets(
        self,
        user_id: Optional[int] = None,
        status: Optional[Any] = None,
        strategy_type: Optional[Any] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Basket]:
        session = self._get_session()
        query = select(BasketModel)
        if user_id is not None:
            query = query.where(BasketModel.user_id == user_id)
        if status is not None:
            st_val = status.value if isinstance(status, BasketState) else str(status)
            query = query.where(BasketModel.status == st_val)
        if strategy_type is not None:
            strat_val = strategy_type.value if isinstance(strategy_type, StrategyType) else str(strategy_type)
            query = query.where(BasketModel.strategy_type == strat_val)

        query = query.order_by(desc(BasketModel.id)).offset(offset).limit(limit)
        results = session.execute(query).scalars().all()
        return [self._to_domain(b) for b in results]

    def record_transition(
        self,
        basket_id: str,
        client_basket_id: str,
        from_status: str,
        to_status: str,
        from_exposure: str = "",
        to_exposure: str = "",
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        source_timestamp: Optional[str] = None,
    ) -> BasketEventRecord:
        session = self._get_session()
        try:
            int_id = int(basket_id)
        except ValueError:
            basket_ent = session.execute(
                select(BasketModel).where(BasketModel.client_basket_id == client_basket_id)
            ).scalar_one_or_none()
            int_id = basket_ent.id if basket_ent else 1

        event_entity = BasketEventModel(
            basket_id=int_id,
            client_basket_id=client_basket_id,
            from_status=from_status,
            to_status=to_status,
            from_exposure=from_exposure,
            to_exposure=to_exposure,
            reason=reason or "",
            details=details or {},
            source_timestamp=source_timestamp,
            retrieved_timestamp=datetime.now(timezone.utc).isoformat(),
        )
        session.add(event_entity)
        session.commit()
        session.refresh(event_entity)

        return BasketEventRecord(
            event_id=str(event_entity.id),
            basket_id=str(int_id),
            client_basket_id=client_basket_id,
            from_status=from_status,
            to_status=to_status,
            from_exposure=from_exposure,
            to_exposure=to_exposure,
            reason=reason or "",
            details=details or {},
            source_timestamp=source_timestamp,
            retrieved_timestamp=event_entity.retrieved_timestamp,
        )

    def get_basket_events(self, client_basket_id: str) -> List[BasketEventRecord]:
        session = self._get_session()
        query = (
            select(BasketEventModel)
            .where(BasketEventModel.client_basket_id == client_basket_id)
            .order_by(BasketEventModel.id)
        )
        entities = session.execute(query).scalars().all()
        return [
            BasketEventRecord(
                event_id=str(e.id),
                basket_id=str(e.basket_id),
                client_basket_id=e.client_basket_id,
                from_status=e.from_status,
                to_status=e.to_status,
                from_exposure=e.from_exposure,
                to_exposure=e.to_exposure,
                reason=e.reason or "",
                details=e.details or {},
                source_timestamp=e.source_timestamp,
                retrieved_timestamp=e.retrieved_timestamp,
            )
            for e in entities
        ]

    def delete_basket(self, basket_id: str) -> bool:
        session = self._get_session()
        try:
            int_id = int(basket_id)
            entity = session.execute(select(BasketModel).where(BasketModel.id == int_id)).scalar_one_or_none()
        except ValueError:
            entity = session.execute(select(BasketModel).where(BasketModel.client_basket_id == basket_id)).scalar_one_or_none()

        if entity and entity.status == BasketState.DRAFT.value:
            session.delete(entity)
            session.commit()
            return True
        return False

    def _to_domain(self, entity: BasketModel) -> Basket:
        legs: List[BasketLeg] = []
        for l in entity.legs:
            legs.append(
                BasketLeg(
                    leg_id=str(l.id),
                    leg_index=l.leg_index,
                    trading_symbol=l.trading_symbol,
                    exchange_segment=l.exchange_segment,
                    instrument_token=l.instrument_token,
                    side=OrderSide(l.side),
                    order_type=OrderType(l.order_type),
                    product_type=ProductType(l.product_type),
                    validity=Validity(l.validity),
                    quantity=l.quantity,
                    price=l.price,
                    trigger_price=l.trigger_price,
                    order_id=l.order_id,
                    broker_order_id=l.broker_order_id,
                    status=OrderStatus(l.status),
                    filled_quantity=l.filled_quantity,
                    average_price=l.average_price,
                    depends_on_leg_index=l.depends_on_leg_index,
                )
            )

        return Basket(
            basket_id=str(entity.id),
            client_basket_id=entity.client_basket_id,
            basket_idempotency_key=entity.basket_idempotency_key,
            user_id=entity.user_id,
            name=entity.name,
            strategy_type=StrategyType(entity.strategy_type),
            strategy_version=entity.strategy_version,
            execution_mode=ExecutionMode(entity.execution_mode),
            basket_execution_mode=BasketExecutionMode(entity.basket_execution_mode),
            failure_policy=BasketFailurePolicy(entity.failure_policy),
            status=BasketState(entity.status),
            exposure_state=BasketExposureState(entity.exposure_state),
            legs=legs,
            estimated_margin=entity.estimated_margin,
            margin_snapshot=entity.margin_snapshot or {},
            validation_timestamp=entity.validation_timestamp,
            rejection_reason=entity.rejection_reason,
            source_timestamp=entity.source_timestamp,
            retrieved_timestamp=entity.retrieved_timestamp,
        )


# Global singleton repository
basket_repository = BasketRepository()
