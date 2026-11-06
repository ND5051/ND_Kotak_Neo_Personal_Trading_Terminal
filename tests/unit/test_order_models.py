"""
Unit tests for Order Domain Models.
Phase 7: Order Domain Foundation.
"""

from app.orders.models.order import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
    TradeExecution,
    Validity,
)


def test_order_model_initialization_and_serialization():
    """Verify Order dataclass initialization, pending quantity calculation, and dictionary serialization."""
    order = Order(
        client_order_id="test-order-uuid-1",
        user_id=1,
        instrument_token="26000",
        exchange_segment="nse_cm",
        trading_symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.MIS,
        validity=Validity.DAY,
        quantity=50,
        price=2450.05,
    )

    assert order.client_order_id == "test-order-uuid-1"
    assert order.pending_quantity == 50
    assert order.filled_quantity == 0
    assert order.status == OrderStatus.PENDING_VALIDATION
    assert order.is_terminal() is False
    assert order.is_open() is False

    d = order.to_dict()
    assert d["client_order_id"] == "test-order-uuid-1"
    assert d["trading_symbol"] == "RELIANCE"
    assert d["side"] == "BUY"
    assert d["order_type"] == "LIMIT"
    assert d["product_type"] == "MIS"
    assert d["price"] == 2450.05
    assert d["status"] == "PENDING_VALIDATION"
    assert "retrieved_timestamp" in d


def test_order_status_predicates_and_reconciling_state():
    """Verify terminal, open, and RECONCILING state predicates."""
    # Terminal orders
    for terminal_st in (
        OrderStatus.FILLED,
        OrderStatus.REJECTED,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
        OrderStatus.FAILED,
    ):
        ord_term = Order(
            client_order_id="ord-term",
            user_id=1,
            trading_symbol="INFY",
            status=terminal_st,
        )
        assert ord_term.is_terminal() is True
        assert ord_term.is_open() is False

    # Open orders (including RECONCILING)
    for open_st in (
        OrderStatus.ACKNOWLEDGED,
        OrderStatus.TRIGGER_PENDING,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.RECONCILING,
    ):
        ord_open = Order(
            client_order_id="ord-open",
            user_id=1,
            trading_symbol="INFY",
            status=open_st,
        )
        assert ord_open.is_terminal() is False
        assert ord_open.is_open() is True


def test_trade_execution_serialization():
    """Verify TradeExecution fill serialization."""
    trade = TradeExecution(
        trade_id="TRD123456",
        client_order_id="order-uuid-abc",
        broker_order_id="24110600001",
        fill_quantity=25,
        fill_price=2450.00,
        exchange_segment="nse_cm",
        trading_symbol="RELIANCE",
        exchange_timestamp="2026-11-06T09:15:30",
    )

    d = trade.to_dict()
    assert d["trade_id"] == "TRD123456"
    assert d["fill_quantity"] == 25
    assert d["fill_price"] == 2450.00
    assert d["trading_symbol"] == "RELIANCE"
