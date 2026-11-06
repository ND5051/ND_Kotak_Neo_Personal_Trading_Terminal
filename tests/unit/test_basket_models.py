import pytest

from app.baskets.models.basket import (
    Basket,
    BasketEventRecord,
    BasketExecutionMode,
    BasketExposureState,
    BasketFailurePolicy,
    BasketLeg,
    BasketState,
    StrategyType,
)
from app.orders.models.execution_mode import ExecutionMode
from app.orders.models.order import OrderSide, OrderStatus, OrderType, ProductType


def test_basket_models_initialization_and_serialization():
    """Verify Basket and BasketLeg initialization, defaults, and dictionary serialization."""
    leg = BasketLeg(
        leg_index=0,
        trading_symbol="NIFTY26NOV24500CE",
        exchange_segment="nse_fo",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.MIS,
        quantity=50,
        price=120.50,
    )

    assert leg.trading_symbol == "NIFTY26NOV24500CE"
    assert leg.quantity == 50
    assert leg.status == OrderStatus.PENDING_VALIDATION
    assert leg.depends_on_leg_index is None

    leg_dict = leg.to_dict()
    assert leg_dict["trading_symbol"] == "NIFTY26NOV24500CE"
    assert leg_dict["side"] == "BUY"
    assert leg_dict["price"] == 120.50

    basket = Basket(
        client_basket_id="bkt_unit_test_01",
        name="Test Bull Call Spread",
        strategy_type=StrategyType.BULL_CALL_SPREAD,
        execution_mode=ExecutionMode.DISABLED,
        basket_execution_mode=BasketExecutionMode.SEQUENTIAL,
        failure_policy=BasketFailurePolicy.ABORT_REMAINING,
        legs=[leg],
    )

    assert basket.client_basket_id == "bkt_unit_test_01"
    assert basket.strategy_type == StrategyType.BULL_CALL_SPREAD
    assert basket.status == BasketState.DRAFT
    assert basket.exposure_state == BasketExposureState.NEUTRAL
    assert basket.is_terminal() is False
    assert basket.is_open() is False

    bkt_dict = basket.to_dict()
    assert bkt_dict["client_basket_id"] == "bkt_unit_test_01"
    assert bkt_dict["strategy_type"] == "BULL_CALL_SPREAD"
    assert bkt_dict["total_legs"] == 1
    assert len(bkt_dict["legs"]) == 1


def test_basket_status_predicates():
    """Verify is_terminal() and is_open() predicate methods."""
    basket = Basket(client_basket_id="bkt_pred_01")

    # Draft
    basket.status = BasketState.DRAFT
    assert basket.is_terminal() is False
    assert basket.is_open() is False

    # Ready & Executing
    basket.status = BasketState.READY
    assert basket.is_open() is True
    basket.status = BasketState.EXECUTING
    assert basket.is_open() is True
    basket.status = BasketState.PARTIALLY_EXECUTED
    assert basket.is_open() is True
    basket.status = BasketState.RECONCILING
    assert basket.is_open() is True

    # Terminal states
    basket.status = BasketState.EXECUTED
    assert basket.is_terminal() is True
    assert basket.is_open() is False
    basket.status = BasketState.FAILED
    assert basket.is_terminal() is True
    basket.status = BasketState.CANCELLED
    assert basket.is_terminal() is True


def test_basket_event_record_serialization():
    """Verify BasketEventRecord serialization and dual timestamps."""
    evt = BasketEventRecord(
        basket_id="1",
        client_basket_id="bkt_evt_01",
        from_status="DRAFT",
        to_status="VALIDATED",
        from_exposure="NEUTRAL",
        to_exposure="NEUTRAL",
        reason="Syntax passed",
        details={"checks": 5},
    )
    d = evt.to_dict()
    assert d["client_basket_id"] == "bkt_evt_01"
    assert d["from_status"] == "DRAFT"
    assert d["to_status"] == "VALIDATED"
    assert d["reason"] == "Syntax passed"
    assert "retrieved_timestamp" in d

