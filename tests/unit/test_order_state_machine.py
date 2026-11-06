"""
Unit tests for Order State Machine.
Phase 7: Order Domain Foundation.
"""

import pytest

from app.core.exceptions import IllegalOrderStateTransitionException
from app.orders.models.order import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
)
from app.orders.repositories.order_repository import OrderRepository
from app.orders.services.order_state_machine import OrderStateMachine


class MockOrderRepository(OrderRepository):
    """Mock repository for isolated unit testing."""
    def __init__(self):
        self.orders = {}
        self.events = []

    def save_order(self, order: Order) -> Order:
        self.orders[order.client_order_id] = order
        return order

    def record_transition(self, order_id, client_order_id, from_status, to_status, reason=None, snapshot=None):
        self.events.append({
            "client_order_id": client_order_id,
            "from_status": from_status,
            "to_status": to_status,
            "reason": reason,
        })


def test_order_state_machine_legal_progression():
    """Verify normal execution progression from PENDING_VALIDATION through FILLED."""
    mock_repo = MockOrderRepository()
    fsm = OrderStateMachine(repo=mock_repo)

    order = Order(
        client_order_id="progression-uuid-1",
        user_id=1,
        trading_symbol="RELIANCE",
        status=OrderStatus.PENDING_VALIDATION,
    )

    # 1. PENDING_VALIDATION -> VALIDATED
    order = fsm.transition(order, OrderStatus.VALIDATED)
    assert order.status == OrderStatus.VALIDATED

    # 2. VALIDATED -> SUBMITTED
    order = fsm.transition(order, OrderStatus.SUBMITTED)
    assert order.status == OrderStatus.SUBMITTED

    # 3. SUBMITTED -> ACKNOWLEDGED
    order = fsm.transition(order, OrderStatus.ACKNOWLEDGED)
    assert order.status == OrderStatus.ACKNOWLEDGED

    # 4. ACKNOWLEDGED -> PARTIALLY_FILLED
    order = fsm.transition(order, OrderStatus.PARTIALLY_FILLED)
    assert order.status == OrderStatus.PARTIALLY_FILLED

    # 5. PARTIALLY_FILLED -> FILLED
    order = fsm.transition(order, OrderStatus.FILLED)
    assert order.status == OrderStatus.FILLED
    assert order.is_terminal() is True


def test_order_state_machine_reconciling_flow():
    """Verify Golden Rule RECONCILING transition flow."""
    mock_repo = MockOrderRepository()
    fsm = OrderStateMachine(repo=mock_repo)

    order = Order(
        client_order_id="reconcile-uuid-2",
        user_id=1,
        trading_symbol="INFY",
        status=OrderStatus.ACKNOWLEDGED,
    )

    # Temporary network dropout during status query -> RECONCILING
    order = fsm.transition(order, OrderStatus.RECONCILING, reason="Broker response timed out")
    assert order.status == OrderStatus.RECONCILING
    assert order.is_open() is True

    # Authoritative check completes -> FILLED
    order = fsm.transition(order, OrderStatus.FILLED, reason="Reconciled via order report")
    assert order.status == OrderStatus.FILLED
    assert order.is_terminal() is True


def test_order_state_machine_illegal_transition_rejection():
    """Verify that illegal transitions raise IllegalOrderStateTransitionException."""
    mock_repo = MockOrderRepository()
    fsm = OrderStateMachine(repo=mock_repo)

    # Terminal state cannot transition to any other state
    filled_order = Order(
        client_order_id="filled-uuid-3",
        user_id=1,
        trading_symbol="TCS",
        status=OrderStatus.FILLED,
    )

    with pytest.raises(IllegalOrderStateTransitionException) as excinfo:
        fsm.transition(filled_order, OrderStatus.CANCELLED)
    assert "Illegal state transition from FILLED to CANCELLED" in str(excinfo.value)

    # PENDING_VALIDATION cannot skip directly to FILLED
    new_order = Order(
        client_order_id="skip-uuid-4",
        user_id=1,
        trading_symbol="WIPRO",
        status=OrderStatus.PENDING_VALIDATION,
    )

    with pytest.raises(IllegalOrderStateTransitionException) as excinfo:
        fsm.transition(new_order, OrderStatus.FILLED)
    assert "Illegal state transition from PENDING_VALIDATION to FILLED" in str(excinfo.value)
