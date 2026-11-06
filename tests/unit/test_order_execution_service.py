import pytest

from app.core.exceptions import (
    ExecutionModeException,
    OrderRiskException,
    OrderValidationException,
)
from app.orders.models.execution_mode import (
    ExecutionMode,
    ExecutionModeManager,
)
from app.orders.models.order import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
    Validity,
)
from app.orders.repositories.order_repository import OrderRepository
from app.orders.services.idempotency_manager import IdempotencyManager
from app.orders.services.order_execution_service import OrderExecutionService
from app.orders.services.order_poller_service import OrderPollerService
from app.orders.services.order_state_machine import OrderStateMachine


class MockOrderRepository(OrderRepository):
    """Mock repository for isolated unit testing without database session."""

    def __init__(self):
        self.orders = {}
        self.events = []
        self.trades = []

    def save_order(self, order: Order) -> Order:
        self.orders[order.client_order_id] = order
        return order

    def find_by_client_order_id(self, client_order_id: str):
        return self.orders.get(client_order_id)

    def find_by_broker_order_id(self, broker_order_id: str):
        for o in self.orders.values():
            if o.broker_order_id == broker_order_id:
                return o
        return None

    def find_orders(self, user_id=None, status=None, symbol=None, segment=None, limit=100, offset=0):
        res = list(self.orders.values())
        if status:
            st = status.value if hasattr(status, "value") else str(status)
            res = [o for o in res if (o.status.value if hasattr(o.status, "value") else str(o.status)) == st]
        return res

    def record_transition(self, order_id, client_order_id, from_status, to_status, reason=None, snapshot=None):
        self.events.append({
            "client_order_id": client_order_id,
            "from_status": from_status,
            "to_status": to_status,
            "reason": reason,
        })

    def record_trade_execution(self, trade):
        self.trades.append(trade)
        return trade


def _create_test_service(mode=ExecutionMode.PAPER):
    mode_mgr = ExecutionModeManager(default_mode=mode)
    repo = MockOrderRepository()
    fsm = OrderStateMachine(repo=repo)
    idemp = IdempotencyManager()
    poller = OrderPollerService(repository=repo, state_machine=fsm)
    service = OrderExecutionService(
        mode_manager=mode_mgr,
        repository=repo,
        state_machine=fsm,
        idempotency=idemp,
        poller=poller,
    )
    return service, repo


def test_order_execution_service_refuses_when_disabled():
    """Verify execution is refused when mode is DISABLED."""
    service, _ = _create_test_service(mode=ExecutionMode.DISABLED)

    with pytest.raises(ExecutionModeException):
        service.place_order({
            "trading_symbol": "RELIANCE-EQ",
            "quantity": 1,
            "price": 2450.05,
            "side": "BUY",
        })


def test_order_execution_service_paper_mode_placement_and_fill():
    """Verify successful order placement and simulated fill in PAPER mode."""
    service, repo = _create_test_service(mode=ExecutionMode.PAPER)

    res = service.place_order(
        {
            "client_order_id": "test_exec_paper_01",
            "trading_symbol": "RELIANCE-EQ",
            "exchange_segment": "nse_cm",
            "side": "BUY",
            "order_type": "LIMIT",
            "product_type": "MIS",
            "quantity": 5,
            "price": 2450.05,
        },
        available_cash=100000.0,
    )

    assert res["success"] is True
    assert res["mode"] == "PAPER"
    assert res["order"]["client_order_id"] == "test_exec_paper_01"
    assert res["order"]["broker_order_id"].startswith("PAPER_")
    assert res["order"]["status"] in ("ACKNOWLEDGED", "FILLED")


def test_order_execution_service_market_protection():
    """Verify MARKET order is converted to aggressive LIMIT with Market Protection."""
    service, repo = _create_test_service(mode=ExecutionMode.PAPER)

    res = service.place_order(
        {
            "client_order_id": "test_exec_mp_02",
            "trading_symbol": "INFY-EQ",
            "exchange_segment": "nse_cm",
            "side": "BUY",
            "order_type": "MARKET",
            "product_type": "MIS",
            "quantity": 1,
            "price": 1800.00,
            "market_protection_percent": 2.0,
        },
        available_cash=50000.0,
    )

    assert res["success"] is True
    # Converted to LIMIT
    assert res["order"]["order_type"] == "LIMIT"
    # Price was buffered: 1800 * 1.02 = 1836.00
    assert res["order"]["price"] == 1836.00


def test_order_execution_service_modify_and_cancel():
    """Verify modify and cancel operations on open paper order."""
    service, repo = _create_test_service(mode=ExecutionMode.PAPER)

    res = service.place_order(
        {
            "client_order_id": "test_exec_mod_03",
            "trading_symbol": "TCS-EQ",
            "exchange_segment": "nse_cm",
            "side": "BUY",
            "order_type": "LIMIT",
            "product_type": "MIS",
            "quantity": 10,
            "price": 3500.00,
        },
        available_cash=100000.0,
    )
    order_id = res["order"]["client_order_id"]

    # Modify
    mod_res = service.modify_order(order_id, {"price": 3510.05, "quantity": 10})
    assert mod_res["success"] is True
    assert mod_res["order"]["price"] == 3510.05

    # Cancel
    canc_res = service.cancel_order(order_id)
    assert canc_res["success"] is True
    assert canc_res["status"] == "CANCELLED"


def test_order_execution_service_cancel_all():
    """Verify mass cancel all emergency kill switch."""
    service, repo = _create_test_service(mode=ExecutionMode.PAPER)

    # Place two orders
    service.place_order(
        {"client_order_id": "cancel_all_01", "trading_symbol": "RELIANCE-EQ", "quantity": 1, "price": 2400.00, "side": "BUY", "product_type": "MIS"},
        available_cash=50000.0,
    )
    service.place_order(
        {"client_order_id": "cancel_all_02", "trading_symbol": "TCS-EQ", "quantity": 1, "price": 3500.00, "side": "BUY", "product_type": "MIS"},
        available_cash=50000.0,
    )

    cancel_summary = service.cancel_all_orders()
    assert cancel_summary["success"] is True
    assert cancel_summary["cancelled"] >= 2
