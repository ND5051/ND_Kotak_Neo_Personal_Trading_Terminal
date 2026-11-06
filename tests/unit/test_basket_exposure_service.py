import pytest

from app.baskets.models.basket import Basket, BasketExposureState, BasketLeg, StrategyType
from app.baskets.services.basket_exposure_service import BasketExposureService
from app.orders.models.order import OrderSide, OrderStatus


@pytest.fixture
def exposure_service():
    return BasketExposureService()


def test_exposure_state_neutral(exposure_service):
    """Verify NEUTRAL state when no fills exist."""
    basket = Basket(
        strategy_type=StrategyType.BULL_CALL_SPREAD,
        legs=[
            BasketLeg(trading_symbol="NIFTY26NOV24500CE", status=OrderStatus.PENDING_VALIDATION),
            BasketLeg(trading_symbol="NIFTY26NOV24700CE", status=OrderStatus.PENDING_VALIDATION),
        ],
    )
    assert exposure_service.compute_exposure_state(basket) == BasketExposureState.NEUTRAL


def test_exposure_state_fully_hedged(exposure_service):
    """Verify FULLY_HEDGED state when all legs are 100% FILLED."""
    basket = Basket(
        strategy_type=StrategyType.BULL_CALL_SPREAD,
        legs=[
            BasketLeg(trading_symbol="NIFTY26NOV24500CE", status=OrderStatus.FILLED, quantity=50, filled_quantity=50),
            BasketLeg(trading_symbol="NIFTY26NOV24700CE", status=OrderStatus.FILLED, quantity=50, filled_quantity=50),
        ],
    )
    assert exposure_service.compute_exposure_state(basket) == BasketExposureState.FULLY_HEDGED


def test_exposure_state_partially_exposed_broken_hedge(exposure_service):
    """Verify PARTIALLY_EXPOSED when one leg fills and second leg is rejected/unexecuted."""
    basket = Basket(
        strategy_type=StrategyType.BULL_CALL_SPREAD,
        legs=[
            BasketLeg(trading_symbol="NIFTY26NOV24500CE", status=OrderStatus.FILLED, quantity=50, filled_quantity=50),
            BasketLeg(trading_symbol="NIFTY26NOV24700CE", status=OrderStatus.REJECTED, quantity=50),
        ],
    )
    assert exposure_service.compute_exposure_state(basket) == BasketExposureState.PARTIALLY_EXPOSED


def test_exposure_state_reconciling_scenarios(exposure_service):
    """Verify exposure states during unconfirmed broker states (The Golden Rule)."""
    # 1. Zero fills + RECONCILING -> UNKNOWN
    bkt_unknown = Basket(
        strategy_type=StrategyType.LONG_STRADDLE,
        legs=[
            BasketLeg(trading_symbol="NIFTY26NOV24500CE", status=OrderStatus.RECONCILING),
            BasketLeg(trading_symbol="NIFTY26NOV24500PE", status=OrderStatus.SUBMITTED),
        ],
    )
    assert exposure_service.compute_exposure_state(bkt_unknown) == BasketExposureState.UNKNOWN

    # 2. Leg 1 FILLED + Leg 2 RECONCILING -> PARTIALLY_EXPOSED
    bkt_partial = Basket(
        strategy_type=StrategyType.LONG_STRADDLE,
        legs=[
            BasketLeg(trading_symbol="NIFTY26NOV24500CE", status=OrderStatus.FILLED, quantity=25, filled_quantity=25),
            BasketLeg(trading_symbol="NIFTY26NOV24500PE", status=OrderStatus.RECONCILING),
        ],
    )
    assert exposure_service.compute_exposure_state(bkt_partial) == BasketExposureState.PARTIALLY_EXPOSED

