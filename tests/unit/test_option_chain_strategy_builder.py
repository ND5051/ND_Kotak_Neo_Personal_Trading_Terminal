"""
Unit Tests for Option Strategy Builder Service.
Phase 10: Option Chain Workbench.
Verifies that strategy payloads generated from Option Chain strikes
comply strictly with Phase 9 Basket and Strategy invariants.
"""

import pytest

from app.baskets.models.basket import Basket, BasketExecutionMode, BasketLeg, StrategyType
from app.baskets.services.strategy_validator import StrategyValidationService
from app.option_chain.services.strategy_builder_service import OptionStrategyBuilderService


@pytest.fixture
def builder():
    return OptionStrategyBuilderService()


@pytest.fixture
def validator():
    return StrategyValidationService()


def test_build_bull_call_spread_compliance(builder, validator):
    """Verify built Bull Call Spread complies with Phase 9 invariants."""
    payload = builder.build_bull_call_spread(
        underlying="NIFTY",
        expiry_token="26NOV",
        buy_strike=24500.0,
        sell_strike=24700.0,
        lot_size=25,
        lots=2,
        buy_price=150.0,
        sell_price=60.0,
    )

    assert payload["strategy_type"] == "BULL_CALL_SPREAD"
    assert len(payload["legs"]) == 2
    assert payload["legs"][0]["quantity"] == 50
    assert payload["legs"][1]["quantity"] == 50

    # Test compliance against Phase 9 StrategyValidationService
    basket = Basket(
        strategy_type=StrategyType.BULL_CALL_SPREAD,
        legs=[
            BasketLeg(trading_symbol=l["trading_symbol"], side=l["side"], quantity=l["quantity"], price=l["price"])
            for l in payload["legs"]
        ],
    )
    is_valid, errs = validator.validate_basket(basket)
    assert is_valid is True
    assert len(errs) == 0


def test_build_bear_put_spread_compliance(builder, validator):
    """Verify built Bear Put Spread complies with Phase 9 invariants."""
    payload = builder.build_bear_put_spread(
        underlying="NIFTY",
        expiry_token="26NOV",
        buy_strike=24700.0,
        sell_strike=24500.0,
        lot_size=25,
        lots=1,
    )

    assert payload["strategy_type"] == "BEAR_PUT_SPREAD"
    assert len(payload["legs"]) == 2

    basket = Basket(
        strategy_type=StrategyType.BEAR_PUT_SPREAD,
        legs=[
            BasketLeg(trading_symbol=l["trading_symbol"], side=l["side"], quantity=l["quantity"], price=l["price"])
            for l in payload["legs"]
        ],
    )
    is_valid, errs = validator.validate_basket(basket)
    assert is_valid is True
    assert len(errs) == 0


def test_build_straddle_compliance(builder, validator):
    """Verify built Long and Short Straddles comply with Phase 9 invariants."""
    # Long Straddle
    p_long = builder.build_straddle(
        underlying="BANKNIFTY",
        expiry_token="26NOV",
        strike=51200.0,
        lot_size=15,
        is_short=False,
    )
    assert p_long["strategy_type"] == "LONG_STRADDLE"
    b_long = Basket(
        strategy_type=StrategyType.LONG_STRADDLE,
        legs=[
            BasketLeg(trading_symbol=l["trading_symbol"], side=l["side"], quantity=l["quantity"], price=l["price"])
            for l in p_long["legs"]
        ],
    )
    is_valid, errs = validator.validate_basket(b_long)
    assert is_valid is True

    # Short Straddle
    p_short = builder.build_straddle(
        underlying="BANKNIFTY",
        expiry_token="26NOV",
        strike=51200.0,
        lot_size=15,
        is_short=True,
    )
    assert p_short["strategy_type"] == "SHORT_STRADDLE"


def test_build_iron_condor_compliance(builder, validator):
    """Verify built Iron Condor has symmetric wings and valid DAG dependencies."""
    payload = builder.build_iron_condor(
        underlying="NIFTY",
        expiry_token="26NOV",
        put_buy_strike=24100.0,
        put_sell_strike=24300.0,
        call_sell_strike=24700.0,
        call_buy_strike=24900.0,
        lot_size=25,
        lots=1,
    )

    assert payload["strategy_type"] == "IRON_CONDOR"
    assert payload["basket_execution_mode"] == "DEPENDENCY"
    assert len(payload["legs"]) == 4

    # Wing width symmetry: (24300 - 24100) = 200 == (24900 - 24700) = 200
    assert (payload["legs"][1]["price"] > 0)
    assert payload["legs"][0]["depends_on_leg_index"] is None  # Wing Root
    assert payload["legs"][1]["depends_on_leg_index"] == 0     # Body depends on Wing

    basket = Basket(
        strategy_type=StrategyType.IRON_CONDOR,
        legs=[
            BasketLeg(trading_symbol=l["trading_symbol"], side=l["side"], quantity=l["quantity"], price=l["price"])
            for l in payload["legs"]
        ],
    )
    is_valid, errs = validator.validate_basket(basket)
    assert is_valid is True
    assert len(errs) == 0

