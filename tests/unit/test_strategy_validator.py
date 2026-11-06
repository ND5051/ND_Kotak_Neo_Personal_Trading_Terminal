import pytest

from app.baskets.models.basket import Basket, BasketLeg, StrategyType
from app.baskets.services.strategy_validator import StrategyValidationService
from app.orders.models.order import OrderSide, OrderType, ProductType


@pytest.fixture
def validator():
    return StrategyValidationService()


def test_parse_option_symbol(validator):
    """Verify regex parsing of standard Indian option symbols."""
    p1 = validator.parse_option_symbol("NIFTY26NOV24500CE")
    assert p1 is not None
    assert p1["underlying"] == "NIFTY"
    assert p1["strike"] == 24500.0
    assert p1["option_type"] == "CE"

    p2 = validator.parse_option_symbol("BANKNIFTY26NOV51000PE")
    assert p2 is not None
    assert p2["underlying"] == "BANKNIFTY"
    assert p2["strike"] == 51000.0
    assert p2["option_type"] == "PE"


def test_validate_bull_call_spread(validator):
    """Verify Bull Call Spread validation rules."""
    # 1. Valid Spread
    basket = Basket(
        strategy_type=StrategyType.BULL_CALL_SPREAD,
        legs=[
            BasketLeg(trading_symbol="NIFTY26NOV24500CE", side=OrderSide.BUY, quantity=50, price=150.0),
            BasketLeg(trading_symbol="NIFTY26NOV24700CE", side=OrderSide.SELL, quantity=50, price=60.0),
        ],
    )
    is_valid, errs = validator.validate_basket(basket)
    assert is_valid is True
    assert len(errs) == 0

    # 2. Strike Inversion (Buy strike >= Sell strike)
    bad_strike_basket = Basket(
        strategy_type=StrategyType.BULL_CALL_SPREAD,
        legs=[
            BasketLeg(trading_symbol="NIFTY26NOV24800CE", side=OrderSide.BUY, quantity=50, price=50.0),
            BasketLeg(trading_symbol="NIFTY26NOV24500CE", side=OrderSide.SELL, quantity=50, price=150.0),
        ],
    )
    is_valid, errs = validator.validate_basket(bad_strike_basket)
    assert is_valid is False
    assert any("strike violation" in e for e in errs)

    # 3. Quantity mismatch
    qty_mismatch_basket = Basket(
        strategy_type=StrategyType.BULL_CALL_SPREAD,
        legs=[
            BasketLeg(trading_symbol="NIFTY26NOV24500CE", side=OrderSide.BUY, quantity=50, price=150.0),
            BasketLeg(trading_symbol="NIFTY26NOV24700CE", side=OrderSide.SELL, quantity=75, price=60.0),
        ],
    )
    is_valid, errs = validator.validate_basket(qty_mismatch_basket)
    assert is_valid is False
    assert any("identical quantity" in e for e in errs)


def test_validate_iron_condor(validator):
    """Verify Iron Condor 4-leg ladder and wing symmetry validation."""
    # 1. Valid Iron Condor (24000 PE / 24200 PE / 24800 CE / 25000 CE)
    # Wing widths: 24200 - 24000 = 200, 25000 - 24800 = 200
    basket = Basket(
        strategy_type=StrategyType.IRON_CONDOR,
        legs=[
            BasketLeg(trading_symbol="NIFTY26NOV24000PE", side=OrderSide.BUY, quantity=25, price=15.0),
            BasketLeg(trading_symbol="NIFTY26NOV24200PE", side=OrderSide.SELL, quantity=25, price=45.0),
            BasketLeg(trading_symbol="NIFTY26NOV24800CE", side=OrderSide.SELL, quantity=25, price=50.0),
            BasketLeg(trading_symbol="NIFTY26NOV25000CE", side=OrderSide.BUY, quantity=25, price=18.0),
        ],
    )
    is_valid, errs = validator.validate_basket(basket)
    assert is_valid is True
    assert len(errs) == 0

    # 2. Asymmetric Wings (Put wing width 200 vs Call wing width 300)
    asym_basket = Basket(
        strategy_type=StrategyType.IRON_CONDOR,
        legs=[
            BasketLeg(trading_symbol="NIFTY26NOV24000PE", side=OrderSide.BUY, quantity=25, price=15.0),
            BasketLeg(trading_symbol="NIFTY26NOV24200PE", side=OrderSide.SELL, quantity=25, price=45.0),
            BasketLeg(trading_symbol="NIFTY26NOV24800CE", side=OrderSide.SELL, quantity=25, price=50.0),
            BasketLeg(trading_symbol="NIFTY26NOV25100CE", side=OrderSide.BUY, quantity=25, price=12.0),
        ],
    )
    is_valid, errs = validator.validate_basket(asym_basket)
    assert is_valid is False
    assert any("wing asymmetry" in e for e in errs)


def test_universal_invariants_expiry_and_lot_multiples(validator):
    """Verify expiry mismatch and lot size multiple checks."""
    # 1. Expiry mismatch
    expiry_mismatch = Basket(
        strategy_type=StrategyType.LONG_STRADDLE,
        legs=[
            BasketLeg(trading_symbol="NIFTY26NOV24500CE", side=OrderSide.BUY, quantity=25, price=100.0),
            BasketLeg(trading_symbol="NIFTY03DEC24500PE", side=OrderSide.BUY, quantity=25, price=105.0),
        ],
    )
    is_valid, errs = validator.validate_basket(expiry_mismatch)
    assert is_valid is False
    assert any("Expiry mismatch" in e for e in errs)

    # 2. Lot size multiple violation (NIFTY lot is 25; quantity=30 is invalid)
    bad_lot = Basket(
        strategy_type=StrategyType.LONG_STRADDLE,
        legs=[
            BasketLeg(trading_symbol="NIFTY26NOV24500CE", side=OrderSide.BUY, quantity=30, price=100.0),
            BasketLeg(trading_symbol="NIFTY26NOV24500PE", side=OrderSide.BUY, quantity=30, price=100.0),
        ],
    )
    is_valid, errs = validator.validate_basket(bad_lot)
    assert is_valid is False
    assert any("multiple of lot size" in e for e in errs)

