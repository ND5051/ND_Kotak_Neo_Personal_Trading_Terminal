import pytest

from app.baskets.models.basket import Basket, BasketState
from app.baskets.repositories.basket_repository import BasketRepositoryInterface
from app.baskets.services.basket_state_machine import BasketStateMachine
from app.core.exceptions import IllegalBasketStateTransitionException


class MockFsmBasketRepository(BasketRepositoryInterface):
    def __init__(self):
        self.transitions = []

    def save_basket(self, basket: Basket) -> Basket:
        return basket

    def get_basket_by_id(self, basket_id: str):
        return None

    def get_basket_by_client_id(self, client_basket_id: str):
        return None

    def find_baskets(self, **kwargs):
        return []

    def record_transition(self, **kwargs):
        self.transitions.append(kwargs)

    def get_basket_events(self, client_basket_id: str):
        return []

    def delete_basket(self, basket_id: str):
        return True


def test_basket_fsm_legal_progression():
    """Verify standard lifecycle progression from DRAFT to EXECUTED."""
    repo = MockFsmBasketRepository()
    fsm = BasketStateMachine(repository=repo)
    basket = Basket(client_basket_id="bkt_fsm_01", status=BasketState.DRAFT)

    # 1. DRAFT -> VALIDATED
    fsm.transition_to(basket, BasketState.VALIDATED, reason="Structure Validated")
    assert basket.status == BasketState.VALIDATED

    # 2. VALIDATED -> READY
    fsm.transition_to(basket, BasketState.READY, reason="Risk Cleared")
    assert basket.status == BasketState.READY

    # 3. READY -> EXECUTING
    fsm.transition_to(basket, BasketState.EXECUTING, reason="Dispatched to Wire")
    assert basket.status == BasketState.EXECUTING

    # 4. EXECUTING -> EXECUTED
    fsm.transition_to(basket, BasketState.EXECUTED, reason="All Legs Filled")
    assert basket.status == BasketState.EXECUTED
    assert basket.is_terminal() is True

    assert len(repo.transitions) == 4


def test_basket_fsm_reconciling_and_recovery():
    """Verify transition into RECONCILING and recovery to EXECUTED or PARTIALLY_EXECUTED."""
    repo = MockFsmBasketRepository()
    fsm = BasketStateMachine(repository=repo)
    basket = Basket(client_basket_id="bkt_fsm_reconcile", status=BasketState.EXECUTING)

    # EXECUTING -> RECONCILING (The Golden Rule)
    fsm.transition_to(basket, BasketState.RECONCILING, reason="Leg 2 unconfirmed")
    assert basket.status == BasketState.RECONCILING
    assert basket.is_open() is True

    # RECONCILING -> PARTIALLY_EXECUTED
    fsm.transition_to(basket, BasketState.PARTIALLY_EXECUTED, reason="Poller confirmed terminal split")
    assert basket.status == BasketState.PARTIALLY_EXECUTED


def test_basket_fsm_illegal_transition_rejected():
    """Verify that illegal transitions (e.g. from terminal states) raise IllegalBasketStateTransitionException."""
    repo = MockFsmBasketRepository()
    fsm = BasketStateMachine(repository=repo)
    basket = Basket(client_basket_id="bkt_fsm_terminal", status=BasketState.EXECUTED)

    with pytest.raises(IllegalBasketStateTransitionException, match="Illegal basket state transition"):
        fsm.transition_to(basket, BasketState.CANCELLED)

    with pytest.raises(IllegalBasketStateTransitionException):
        fsm.transition_to(basket, BasketState.EXECUTING)

