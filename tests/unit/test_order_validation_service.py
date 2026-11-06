"""
Unit tests for Order Validation Service.
Phase 7: Order Domain Foundation.
"""

from app.orders.models.order import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
    Validity,
)
from app.orders.services.order_validation_service import OrderValidationService


def test_order_validation_nse_tick_size():
    """Verify that prices must be divisible by 0.05 tick size (and 0.0025 for currency)."""
    val = OrderValidationService()

    # Valid NSE equity price
    valid_order = Order(
        client_order_id="tick-val-1",
        user_id=1,
        instrument_token="26000",
        exchange_segment="nse_cm",
        trading_symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.MIS,
        quantity=10,
        price=2450.05,
    )
    is_valid, errors = val.validate_order(valid_order)
    assert is_valid is True
    assert len(errors) == 0

    # Invalid NSE equity price (2450.03 not on 0.05 tick)
    invalid_order = Order(
        client_order_id="tick-val-2",
        user_id=1,
        instrument_token="26000",
        exchange_segment="nse_cm",
        trading_symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.MIS,
        quantity=10,
        price=2450.03,
    )
    is_valid, errors = val.validate_order(invalid_order)
    assert is_valid is False
    assert any("multiple of tick size ₹0.05" in e for e in errors)


def test_order_validation_stop_loss_logic():
    """Verify Buy SL requires price >= trigger_price, Sell SL requires price <= trigger_price."""
    val = OrderValidationService()

    # Invalid Buy SL: Limit price (2400) < Trigger price (2420)
    bad_buy_sl = Order(
        client_order_id="sl-val-1",
        user_id=1,
        instrument_token="26000",
        exchange_segment="nse_cm",
        trading_symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.SL,
        product_type=ProductType.MIS,
        quantity=10,
        price=2400.00,
        trigger_price=2420.00,
    )
    is_valid, errors = val.validate_order(bad_buy_sl)
    assert is_valid is False
    assert any("limit price (₹2400.00) must be greater than or equal to trigger price" in e for e in errors)

    # Valid Buy SL: Limit price (2425) >= Trigger price (2420)
    good_buy_sl = Order(
        client_order_id="sl-val-2",
        user_id=1,
        instrument_token="26000",
        exchange_segment="nse_cm",
        trading_symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.SL,
        product_type=ProductType.MIS,
        quantity=10,
        price=2425.00,
        trigger_price=2420.00,
    )
    is_valid, errors = val.validate_order(good_buy_sl)
    assert is_valid is True

    # Invalid Sell SL: Limit price (2450) > Trigger price (2430)
    bad_sell_sl = Order(
        client_order_id="sl-val-3",
        user_id=1,
        instrument_token="26000",
        exchange_segment="nse_cm",
        trading_symbol="RELIANCE",
        side=OrderSide.SELL,
        order_type=OrderType.SL,
        product_type=ProductType.MIS,
        quantity=10,
        price=2450.00,
        trigger_price=2430.00,
    )
    is_valid, errors = val.validate_order(bad_sell_sl)
    assert is_valid is False
    assert any("limit price (₹2450.00) must be less than or equal to trigger price" in e for e in errors)


def test_order_validation_derivatives_lot_size_and_freeze():
    """Verify lot size multiples and freeze limits for derivatives."""
    val = OrderValidationService()

    # NIFTY lot size is 25; quantity 30 is invalid
    bad_lot_order = Order(
        client_order_id="lot-val-1",
        user_id=1,
        instrument_token="45000",
        exchange_segment="nse_fo",
        trading_symbol="NIFTY26NOV24500CE",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.NRML,
        quantity=30,
        price=150.00,
    )
    is_valid, errors = val.validate_order(bad_lot_order)
    assert is_valid is False
    assert any("must be a multiple of" in e for e in errors)

    # NIFTY freeze limit is 1800; quantity 2000 is invalid
    freeze_breach_order = Order(
        client_order_id="lot-val-2",
        user_id=1,
        instrument_token="45000",
        exchange_segment="nse_fo",
        trading_symbol="NIFTY26NOV24500CE",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.NRML,
        quantity=2000,
        price=150.00,
    )
    is_valid, errors = val.validate_order(freeze_breach_order)
    assert is_valid is False
    assert any("exceeds exchange freeze limit" in e for e in errors)


def test_calculate_market_protection():
    """Verify Market Protection buffering and 0.05 tick rounding."""
    val = OrderValidationService()

    # Buy at 100.00 with 2% buffer -> 102.00
    buy_buffered = val.calculate_market_protection(ref_price=100.00, side=OrderSide.BUY, mp_percent=2.0)
    assert buy_buffered == 102.00

    # Sell at 100.00 with 2% buffer -> 98.00
    sell_buffered = val.calculate_market_protection(ref_price=100.00, side=OrderSide.SELL, mp_percent=2.0)
    assert sell_buffered == 98.00

    # Fractional tick rounding check: 100.12 * 1.02 = 102.1224 -> snaps to 102.10
    snapped = val.calculate_market_protection(ref_price=100.12, side=OrderSide.BUY, mp_percent=2.0)
    assert snapped == 102.10
