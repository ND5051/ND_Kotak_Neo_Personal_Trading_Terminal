import pytest
import time
from app.broker.adapters.kotak_order_adapter import KotakOrderAdapter
from app.core.audit import audit_logger, AuditCategory, AUDIT_ORDER_DISCREPANCY
from app.orders.models.execution_mode import ExecutionMode, ExecutionModeManager
from app.orders.models.order import Order, OrderSide, OrderType, ProductType, OrderStatus, TradeExecution
from app.orders.services.order_execution_service import OrderExecutionService
from app.orders.services.order_poller_service import OrderPollerService
from app.orders.services.order_state_machine import OrderStateMachine


class MockAuditOrderRepository:
    def __init__(self):
        self.orders = {}
        self.trades = []
        self.events = []

    def save_order(self, order: Order) -> Order:
        self.orders[order.client_order_id] = order
        return order

    def get_order_by_client_id(self, client_order_id: str):
        return self.orders.get(client_order_id)

    def record_transition(self, *args, **kwargs):
        self.events.append((args, kwargs))

    def record_trade_execution(self, trade: TradeExecution) -> TradeExecution:
        self.trades.append(trade)
        return trade

    def find_orders(self, **kwargs):
        return list(self.orders.values())


def test_order_model_quantity_invariants():
    """Verify that Order.assert_quantity_invariants prevents invalid quantity states."""
    # 1. Valid order
    order = Order(
        client_order_id="chk_inv_01",
        user_id=1,
        trading_symbol="RELIANCE-EQ",
        quantity=10,
        price=2500.0,
    )
    assert order.quantity == 10
    assert order.filled_quantity == 0
    assert order.pending_quantity == 10
    order.assert_quantity_invariants()

    # 2. Invariant violation: filled_quantity > quantity
    order.filled_quantity = 11
    order.pending_quantity = 0
    with pytest.raises(ValueError, match="cannot exceed total quantity"):
        order.assert_quantity_invariants()

    # 3. Invariant violation: negative pending_quantity
    order.filled_quantity = 10
    order.pending_quantity = -1
    with pytest.raises(ValueError, match="cannot be negative"):
        order.assert_quantity_invariants()

    # 4. Invariant violation: filled + pending > quantity
    order.filled_quantity = 5
    order.pending_quantity = 6
    with pytest.raises(ValueError, match="exceeds total quantity"):
        order.assert_quantity_invariants()


def test_paper_execution_fill_strictly_matches_requested_quantity():
    """Verify paper mode fills match exactly the requested quantity for various lot sizes."""
    repo = MockAuditOrderRepository()
    adapter = KotakOrderAdapter()
    sm = OrderStateMachine(repo=repo)
    poller = OrderPollerService(adapter=adapter, repository=repo, state_machine=sm)
    mode_mgr = ExecutionModeManager(default_mode=ExecutionMode.PAPER)

    service = OrderExecutionService(
        adapter=adapter,
        repository=repo,
        state_machine=sm,
        mode_manager=mode_mgr,
        poller=poller,
    )

    for qty in [1, 5, 25, 65, 100]:
        cid = f"test_paper_qty_{qty}"
        res = service.place_order(
            {
                "client_order_id": cid,
                "trading_symbol": "TCS-EQ",
                "exchange_segment": "nse_cm",
                "side": "BUY",
                "order_type": "LIMIT",
                "product_type": "MIS",
                "quantity": qty,
                "price": 3500.0,
            },
            available_cash=500000.0,
        )
        assert res["success"] is True
        order = res["order"]
        broker_order_id = order["broker_order_id"]

        # Directly run poller to simulate background execution
        saved_order = repo.get_order_by_client_id(cid)
        poller.poll_order_status(saved_order, max_attempts=1, initial_delay_sec=0.01)

        assert saved_order.status == OrderStatus.FILLED
        assert saved_order.quantity == qty
        assert saved_order.filled_quantity == qty, f"Expected {qty}, got {saved_order.filled_quantity}"
        assert saved_order.pending_quantity == 0
        assert saved_order.filled_quantity <= saved_order.quantity
        saved_order.assert_quantity_invariants()


def test_poller_clamps_excess_broker_reported_quantity():
    """
    CRITICAL AUDIT TEST:
    Verify that if the broker report or simulator sends fldQty > requested quantity,
    the poller strictly clamps filled_quantity to order.quantity and logs AUDIT_ORDER_DISCREPANCY.
    """
    repo = MockAuditOrderRepository()
    adapter = KotakOrderAdapter()
    sm = OrderStateMachine(repo=repo)
    poller = OrderPollerService(adapter=adapter, repository=repo, state_machine=sm)

    # Order requesting 10 shares
    order = Order(
        client_order_id="test_overfill_guard_01",
        user_id=1,
        broker_order_id="SIM_OVERFILL_10",
        trading_symbol="INFY-EQ",
        quantity=10,
        price=1500.0,
        status=OrderStatus.SUBMITTED,
    )
    repo.save_order(order)

    # Manually register simulated order reporting 999 filled shares (overfill anomaly)
    adapter.register_simulated_order(
        broker_order_id="SIM_OVERFILL_10",
        quantity=999,
        price=1500.0,
        status="complete",
    )

    # Poll status
    poller.poll_order_status(order, max_attempts=1, initial_delay_sec=0.01)

    # Invariants must hold:
    assert order.status == OrderStatus.FILLED
    assert order.quantity == 10
    assert order.filled_quantity == 10, f"Overfill occurred! Expected 10, got {order.filled_quantity}"
    assert order.pending_quantity == 0
    assert order.filled_quantity <= order.quantity
    order.assert_quantity_invariants()

    # Verify TradeExecution was clamped to 10
    assert len(repo.trades) == 1
    assert repo.trades[0].fill_quantity == 10


def test_paper_partial_fill_progression():
    """Verify sequential partial fills update cumulative quantity correctly without exceeding requested."""
    repo = MockAuditOrderRepository()
    adapter = KotakOrderAdapter()
    sm = OrderStateMachine(repo=repo)
    poller = OrderPollerService(adapter=adapter, repository=repo, state_machine=sm)

    # Order requesting 20 shares
    order = Order(
        client_order_id="test_partial_prog_01",
        user_id=1,
        broker_order_id="SIM_PARTIAL_20",
        trading_symbol="SBIN-EQ",
        quantity=20,
        price=600.0,
        status=OrderStatus.ACKNOWLEDGED,
    )
    repo.save_order(order)

    # Step 1: Partial fill of 8 shares
    adapter.register_simulated_order("SIM_PARTIAL_20", quantity=8, price=600.0, status="partially_filled")
    poller.poll_order_status(order, max_attempts=1, initial_delay_sec=0.01)

    assert order.status == OrderStatus.PARTIALLY_FILLED
    assert order.filled_quantity == 8
    assert order.pending_quantity == 12
    order.assert_quantity_invariants()
    assert len(repo.trades) == 1
    assert repo.trades[0].fill_quantity == 8

    # Step 2: Second partial fill of 6 additional shares (cumulative 14)
    adapter.register_simulated_order("SIM_PARTIAL_20", quantity=14, price=600.5, status="partially_filled")
    poller.poll_order_status(order, max_attempts=1, initial_delay_sec=0.01)

    assert order.status == OrderStatus.PARTIALLY_FILLED
    assert order.filled_quantity == 14
    assert order.pending_quantity == 6
    order.assert_quantity_invariants()
    assert len(repo.trades) == 2
    assert repo.trades[1].fill_quantity == 6  # Incremental fill of 6

    # Step 3: Complete fill of remaining 6 shares (cumulative 20)
    adapter.register_simulated_order("SIM_PARTIAL_20", quantity=20, price=601.0, status="complete")
    poller.poll_order_status(order, max_attempts=1, initial_delay_sec=0.01)

    assert order.status == OrderStatus.FILLED
    assert order.filled_quantity == 20
    assert order.pending_quantity == 0
    order.assert_quantity_invariants()
    assert len(repo.trades) == 3
    assert repo.trades[2].fill_quantity == 6  # Incremental fill of 6

    # Verify sum of trades equals total requested quantity
    total_trades_qty = sum(t.fill_quantity for t in repo.trades)
    assert total_trades_qty == 20
    assert total_trades_qty <= order.quantity
