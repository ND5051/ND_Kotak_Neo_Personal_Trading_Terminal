import pytest

from app.broker.adapters.kotak_order_adapter import KotakOrderAdapter
from app.orders.models.order import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
    Validity,
)


def test_kotak_order_adapter_simulated_placement():
    """Verify KotakOrderAdapter simulated order placement and normalization."""
    adapter = KotakOrderAdapter()  # mock mode
    order = Order(
        client_order_id="test_client_order_123",
        user_id=1,
        trading_symbol="RELIANCE-EQ",
        exchange_segment="nse_cm",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.CNC,
        validity=Validity.DAY,
        quantity=5,
        price=2450.05,
    )

    result = adapter.place_order(order)
    assert result["stat"] == "Ok"
    assert result["nOrdNo"] is not None
    assert str(result["nOrdNo"]).startswith("26")
    assert result["rejection_reason"] is None


def test_kotak_order_adapter_simulated_modification_and_cancellation():
    """Verify simulated modification and cancellation."""
    adapter = KotakOrderAdapter()
    order = Order(
        client_order_id="test_client_order_456",
        broker_order_id="260930000169351",
        user_id=1,
        trading_symbol="TCS-EQ",
        exchange_segment="nse_cm",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        product_type=ProductType.MIS,
        quantity=10,
        price=3500.00,
    )

    # Modify
    mod_res = adapter.modify_order(order, {"price": 3510.00, "quantity": 10})
    assert mod_res["stat"] == "Ok"
    assert mod_res["nOrdNo"] == "260930000169351"

    # Cancel
    canc_res = adapter.cancel_order(order)
    assert canc_res["stat"] == "Ok"
    assert canc_res["nOrdNo"] == "260930000169351"


def test_kotak_order_adapter_order_report():
    """Verify execution status report retrieval."""
    adapter = KotakOrderAdapter()
    reports = adapter.get_order_report("260930000169351")
    assert isinstance(reports, list)
    assert len(reports) >= 1
    assert reports[0]["nOrdNo"] == "260930000169351"
    assert reports[0]["ordSt"] == "complete"
