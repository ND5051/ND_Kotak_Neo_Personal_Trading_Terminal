"""
Order State Machine Service.
Phase 7: Order Domain Foundation.
Enforces deterministic lifecycle transitions, transition guards, audit logging,
and event publishing.
"""

from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, List, Optional, Set

from app.core.audit import AuditCategory, audit_logger
from app.core.exceptions import IllegalOrderStateTransitionException
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import (
    ORDER_CANCELLED,
    ORDER_FILLED,
    ORDER_PARTIALLY_FILLED,
    ORDER_REJECTED,
    ORDER_STATE_CHANGED,
)
from app.logging.logger import get_logger
from app.orders.models.order import Order, OrderStatus
from app.orders.repositories.order_repository import (
    OrderRepository,
    order_repository,
)

logger = get_logger("app.orders.services.order_state_machine")


class OrderStateMachine:
    """
    Finite State Machine governing Order lifecycle.
    Guarantees strict state transitions and prevents terminal state corruption.
    """

    # Legal transition dictionary: Source State -> Set of allowed Target States
    LEGAL_TRANSITIONS: Dict[OrderStatus, Set[OrderStatus]] = {
        OrderStatus.PENDING_VALIDATION: {
            OrderStatus.VALIDATED,
            OrderStatus.FAILED,
        },
        OrderStatus.VALIDATED: {
            OrderStatus.SUBMITTED,
            OrderStatus.REJECTED,
            OrderStatus.FAILED,
        },
        OrderStatus.SUBMITTED: {
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.TRIGGER_PENDING,
            OrderStatus.REJECTED,
            OrderStatus.FAILED,
            OrderStatus.RECONCILING,
        },
        OrderStatus.TRIGGER_PENDING: {
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.RECONCILING,
        },
        OrderStatus.ACKNOWLEDGED: {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
            OrderStatus.REJECTED,
            OrderStatus.RECONCILING,
        },
        OrderStatus.PARTIALLY_FILLED: {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.RECONCILING,
        },
        OrderStatus.RECONCILING: {
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.TRIGGER_PENDING,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
            OrderStatus.FAILED,
        },
        # Terminal States (Irreversible; zero permitted subsequent transitions)
        OrderStatus.FILLED: set(),
        OrderStatus.REJECTED: set(),
        OrderStatus.CANCELLED: set(),
        OrderStatus.EXPIRED: set(),
        OrderStatus.FAILED: set(),
    }

    def __init__(self, repo: Optional[OrderRepository] = None) -> None:
        self.repository = repo or order_repository
        self._lock = threading.RLock()

    def can_transition(self, current_status: OrderStatus, target_status: OrderStatus) -> bool:
        """Check if transition from current_status to target_status is legally valid."""
        allowed = self.LEGAL_TRANSITIONS.get(current_status, set())
        return target_status in allowed

    def transition(
        self,
        order: Order,
        target_status: OrderStatus,
        reason: Optional[str] = None,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> Order:
        """
        Execute an order state transition with validation, persistence, audit, and event publishing.
        Raises IllegalOrderStateTransitionException if transition is prohibited.
        """
        with self._lock:
            current_status = order.status
            if current_status == target_status:
                logger.debug(
                    f"Order {order.client_order_id} already in state {target_status.value}; no-op."
                )
                return order

            if not self.can_transition(current_status, target_status):
                msg = (
                    f"Illegal state transition from {current_status.value} to {target_status.value} "
                    f"for order {order.client_order_id}."
                )
                logger.error(
                    msg,
                    event="ILLEGAL_ORDER_TRANSITION",
                    order_id=order.client_order_id,
                    current=current_status.value,
                    target=target_status.value,
                )
                raise IllegalOrderStateTransitionException(
                    message=msg,
                    details={
                        "client_order_id": order.client_order_id,
                        "current_status": current_status.value,
                        "attempted_status": target_status.value,
                    },
                )

            # Apply state update
            order.status = target_status
            if reason:
                order.rejection_reason = reason
            order.updated_at = time.time()
            order.retrieved_timestamp = datetime.now(timezone.utc).isoformat()

            # Save in Repository
            saved_order = self.repository.save_order(order)

            # Record event in order_events table
            try:
                # Find database ID if possible
                self.repository.record_transition(
                    order_id=0,
                    client_order_id=order.client_order_id,
                    from_status=current_status.value,
                    to_status=target_status.value,
                    reason=reason,
                    snapshot=snapshot,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to record order event row for {order.client_order_id}: {str(e)}"
                )

            # Audit Logging
            audit_logger.record(
                category=AuditCategory.ORDER,
                action="ORDER_STATE_TRANSITION",
                actor=str(order.user_id),
                correlation_id=get_correlation_id(),
                request_id=get_request_id(),
                details={
                    "client_order_id": order.client_order_id,
                    "broker_order_id": order.broker_order_id,
                    "from_status": current_status.value,
                    "to_status": target_status.value,
                    "symbol": order.trading_symbol,
                    "reason": reason,
                },
            )

            # Publish Event Bus Notification
            publish(
                ORDER_STATE_CHANGED,
                {
                    "client_order_id": order.client_order_id,
                    "from_status": current_status.value,
                    "to_status": target_status.value,
                    "symbol": order.trading_symbol,
                    "reason": reason,
                    "timestamp": order.retrieved_timestamp,
                },
            )

            # Specific Event Bus triggers
            if target_status == OrderStatus.FILLED:
                publish(ORDER_FILLED, {"client_order_id": order.client_order_id, "order": order.to_dict()})
            elif target_status == OrderStatus.PARTIALLY_FILLED:
                publish(ORDER_PARTIALLY_FILLED, {"client_order_id": order.client_order_id, "order": order.to_dict()})
            elif target_status == OrderStatus.REJECTED:
                publish(ORDER_REJECTED, {"client_order_id": order.client_order_id, "reason": reason})
            elif target_status == OrderStatus.CANCELLED:
                publish(ORDER_CANCELLED, {"client_order_id": order.client_order_id, "reason": reason})

            return saved_order


# Global Singleton Order State Machine
order_state_machine = OrderStateMachine()
