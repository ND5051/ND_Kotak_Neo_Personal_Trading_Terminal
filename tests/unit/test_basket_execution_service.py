import pytest
from typing import Any, Dict, List, Optional
import uuid

from app.baskets.models.basket import (
    Basket,
    BasketExecutionMode,
    BasketExposureState,
    BasketFailurePolicy,
    BasketLeg,
    BasketState,
    StrategyType,
)
from app.baskets.repositories.basket_repository import BasketRepositoryInterface
from app.baskets.services.basket_execution_service import BasketExecutionService
from app.baskets.services.basket_exposure_service import BasketExposureService
from app.baskets.services.basket_idempotency_manager import BasketIdempotencyManager
from app.baskets.services.basket_risk_service import BasketRiskService
from app.baskets.services.basket_state_machine import BasketStateMachine
from app.baskets.services.strategy_validator import StrategyValidationService
from app.core.exceptions import ExecutionModeException
from app.orders.models.execution_mode import ExecutionMode, ExecutionModeManager
from app.orders.models.order import Order, OrderSide, OrderStatus, OrderType, ProductType
from app.orders.repositories.order_repository import OrderRepositoryInterface
from app.orders.services.order_execution_service import OrderExecutionService


class MockMemoryBasketRepository(BasketRepositoryInterface):
    def __init__(self):
        self.baskets = {}
        self.events = []

    def save_basket(self, basket: Basket) -> Basket:
        self.baskets[basket.client_basket_id] = basket
        return basket

    def get_basket_by_id(self, basket_id: str):
        for b in self.baskets.values():
            if b.basket_id == basket_id or b.client_basket_id == basket_id:
                return b
        return None

    def get_basket_by_client_id(self, client_basket_id: str):
        return self.baskets.get(client_basket_id)

    def find_baskets(self, **kwargs):
        return list(self.baskets.values())

    def record_transition(self, **kwargs):
        self.events.append(kwargs)

    def get_basket_events(self, client_basket_id: str):
        return []

    def delete_basket(self, basket_id: str):
        return True


class MockOrderExecutionService:
    """Mock order execution service simulating broker order placement."""

    def __init__(self, should_fail_on_leg_index: Optional[int] = None, reconciling_leg_index: Optional[int] = None):
        self.should_fail_on_leg_index = should_fail_on_leg_index
        self.reconciling_leg_index = reconciling_leg_index
        self.placed_orders = []

    def place_order(self, order_data: Dict[str, Any], available_cash: float = 100000.0) -> Dict[str, Any]:
        cid = order_data["client_order_id"]
        self.placed_orders.append(order_data)

        # Check simulated failure
        if self.should_fail_on_leg_index is not None and f"_L{self.should_fail_on_leg_index}_" in cid:
            return {"success": False, "error": "Simulated RMS Rejection"}

        # Check simulated reconciling
        if self.reconciling_leg_index is not None and f"_L{self.reconciling_leg_index}_" in cid:
            return {
                "success": True,
                "order": {
                    "client_order_id": cid,
                    "broker_order_id": f"BROKER_{uuid.uuid4().hex[:8]}",
                    "status": "RECONCILING",
                    "filled_quantity": 0,
                    "average_price": 0.0,
                },
            }

        return {
            "success": True,
            "order": {
                "client_order_id": cid,
                "broker_order_id": f"BROKER_{uuid.uuid4().hex[:8]}",
                "status": "FILLED",
                "filled_quantity": order_data.get("quantity", 25),
                "average_price": order_data.get("price", 100.0),
            },
        }

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        return {"success": True, "message": "Cancelled"}


def _setup_service(
    mode=ExecutionMode.PAPER,
    should_fail_on_leg_index: Optional[int] = None,
    reconciling_leg_index: Optional[int] = None,
):
    repo = MockMemoryBasketRepository()
    mode_mgr = ExecutionModeManager(default_mode=mode)
    fsm = BasketStateMachine(repository=repo)
    idemp = BasketIdempotencyManager(repository=repo)
    val = StrategyValidationService()
    risk = BasketRiskService(repository=repo)
    exp = BasketExposureService()
    order_svc = MockOrderExecutionService(
        should_fail_on_leg_index=should_fail_on_leg_index,
        reconciling_leg_index=reconciling_leg_index,
    )

    executor = BasketExecutionService(
        repository=repo,
        state_machine=fsm,
        idempotency=idemp,
        validator=val,
        risk_service=risk,
        exposure_service=exp,
        order_service=order_svc,
        mode_manager=mode_mgr,
    )
    return executor, repo, order_svc


def test_basket_execution_refused_when_disabled():
    """Verify ExecutionMode inheritance: Basket execution MUST refuse when DISABLED."""
    executor, repo, _ = _setup_service(mode=ExecutionMode.DISABLED)

    basket = executor.create_basket({
        "client_basket_id": "bkt_disabled_test",
        "strategy_type": "BULL_CALL_SPREAD",
        "legs": [
            {"trading_symbol": "NIFTY26NOV24500CE", "side": "BUY", "quantity": 50, "price": 100.0},
            {"trading_symbol": "NIFTY26NOV24700CE", "side": "SELL", "quantity": 50, "price": 40.0},
        ],
    })

    with pytest.raises(ExecutionModeException, match="Basket execution is strictly DISABLED"):
        executor.execute_basket(basket.client_basket_id)


def test_basket_execution_sequential_paper_success():
    """Verify standard SEQUENTIAL execution in PAPER mode completes with FULLY_HEDGED exposure."""
    executor, repo, order_svc = _setup_service(mode=ExecutionMode.PAPER)

    basket = executor.create_basket({
        "client_basket_id": "bkt_paper_seq_01",
        "strategy_type": "BULL_CALL_SPREAD",
        "basket_execution_mode": "SEQUENTIAL",
        "failure_policy": "ABORT_REMAINING",
        "legs": [
            {"trading_symbol": "NIFTY26NOV24500CE", "side": "BUY", "quantity": 50, "price": 100.0},
            {"trading_symbol": "NIFTY26NOV24700CE", "side": "SELL", "quantity": 50, "price": 40.0},
        ],
    })

    res = executor.execute_basket(basket.client_basket_id)
    assert res["success"] is True
    assert res["status"] == "EXECUTED"
    assert res["exposure_state"] == "FULLY_HEDGED"
    assert len(order_svc.placed_orders) == 2


def test_basket_failure_policy_abort_remaining():
    """
    CRITICAL AUDIT TEST:
    Verify BasketFailurePolicy.ABORT_REMAINING:
    If Leg 0 fills and Leg 1 fails, Leg 2 must NEVER be dispatched!
    Basket transitions to PARTIALLY_EXECUTED and exposure state is PARTIALLY_EXPOSED.
    """
    executor, repo, order_svc = _setup_service(
        mode=ExecutionMode.PAPER,
        should_fail_on_leg_index=1,  # Leg 1 will fail
    )

    basket = executor.create_basket({
        "client_basket_id": "bkt_abort_test_01",
        "strategy_type": "CUSTOM",
        "basket_execution_mode": "SEQUENTIAL",
        "failure_policy": "ABORT_REMAINING",
        "legs": [
            {"trading_symbol": "INFY-EQ", "exchange_segment": "nse_cm", "side": "BUY", "quantity": 10, "price": 1500.0},
            {"trading_symbol": "TCS-EQ", "exchange_segment": "nse_cm", "side": "BUY", "quantity": 10, "price": 3500.0},
            {"trading_symbol": "RELIANCE-EQ", "exchange_segment": "nse_cm", "side": "BUY", "quantity": 10, "price": 2500.0},
        ],
    })

    res = executor.execute_basket(basket.client_basket_id)
    assert res["success"] is False
    assert res["status"] == "PARTIALLY_EXECUTED"
    assert res["exposure_state"] == "PARTIALLY_EXPOSED"

    # Only Leg 0 and Leg 1 were touched. Leg 2 was NEVER dispatched!
    assert len(order_svc.placed_orders) == 2
    assert "_L0_" in order_svc.placed_orders[0]["client_order_id"]
    assert "_L1_" in order_svc.placed_orders[1]["client_order_id"]
    assert not any("_L2_" in o["client_order_id"] for o in order_svc.placed_orders)


def test_dependency_execution_dag():
    """
    CRITICAL AUDIT TEST:
    Verify DEPENDENCY execution mode routes roots (wings) first before dependent body legs.
    """
    executor, repo, order_svc = _setup_service(mode=ExecutionMode.PAPER)

    basket = executor.create_basket({
        "client_basket_id": "bkt_dag_test_01",
        "strategy_type": "CUSTOM",
        "basket_execution_mode": "DEPENDENCY",
        "legs": [
            # Leg 0: Wing Buy Hedge (Root)
            {"trading_symbol": "NIFTY26NOV24000PE", "side": "BUY", "quantity": 25, "price": 15.0, "depends_on_leg_index": None},
            # Leg 1: Body Sell Short (Depends on Leg 0)
            {"trading_symbol": "NIFTY26NOV24200PE", "side": "SELL", "quantity": 25, "price": 45.0, "depends_on_leg_index": 0},
        ],
    })

    res = executor.execute_basket(basket.client_basket_id)
    assert res["success"] is True
    assert res["status"] == "EXECUTED"
    assert res["exposure_state"] == "FULLY_HEDGED"

    # Verify Leg 0 was dispatched before Leg 1
    assert "_L0_" in order_svc.placed_orders[0]["client_order_id"]
    assert "_L1_" in order_svc.placed_orders[1]["client_order_id"]


def test_golden_rule_reconciling_exposure():
    """
    CRITICAL AUDIT TEST:
    Verify that if any leg is unconfirmed (RECONCILING), the basket status
    transitions to RECONCILING and exposure state is PARTIALLY_EXPOSED.
    """
    executor, repo, order_svc = _setup_service(
        mode=ExecutionMode.PAPER,
        reconciling_leg_index=1,  # Leg 1 in unconfirmed broker state
    )

    basket = executor.create_basket({
        "client_basket_id": "bkt_reconcile_test_01",
        "strategy_type": "BULL_CALL_SPREAD",
        "basket_execution_mode": "SEQUENTIAL",
        "legs": [
            {"trading_symbol": "NIFTY26NOV24500CE", "side": "BUY", "quantity": 50, "price": 100.0},
            {"trading_symbol": "NIFTY26NOV24700CE", "side": "SELL", "quantity": 50, "price": 40.0},
        ],
    })

    res = executor.execute_basket(basket.client_basket_id)
    assert res["status"] == "RECONCILING"
    assert res["exposure_state"] == "PARTIALLY_EXPOSED"


def test_basket_level_idempotency_deduplication():
    """Verify Level 1 Basket Idempotency blocks duplicate basket execution calls."""
    executor, repo, _ = _setup_service(mode=ExecutionMode.PAPER)

    basket = executor.create_basket({
        "client_basket_id": "bkt_double_click_test",
        "strategy_type": "BULL_CALL_SPREAD",
        "legs": [
            {"trading_symbol": "NIFTY26NOV24500CE", "side": "BUY", "quantity": 50, "price": 100.0},
            {"trading_symbol": "NIFTY26NOV24700CE", "side": "SELL", "quantity": 50, "price": 40.0},
        ],
    })

    res1 = executor.execute_basket(basket.client_basket_id)
    assert res1["success"] is True

    # Immediate second call (double-click simulation)
    res2 = executor.execute_basket(basket.client_basket_id)
    assert res2["success"] is False
    assert res2["error"] == "DUPLICATE_BASKET_REQUEST"

