import pytest

from app.baskets.models.basket import Basket
from app.baskets.repositories.basket_repository import BasketRepositoryInterface
from app.baskets.services.basket_idempotency_manager import BasketIdempotencyManager


class MockBasketRepository(BasketRepositoryInterface):
    def __init__(self):
        self.baskets = {}

    def save_basket(self, basket: Basket) -> Basket:
        self.baskets[basket.client_basket_id] = basket
        return basket

    def get_basket_by_id(self, basket_id: str):
        return None

    def get_basket_by_client_id(self, client_basket_id: str):
        return self.baskets.get(client_basket_id)

    def find_baskets(self, **kwargs):
        return list(self.baskets.values())

    def record_transition(self, **kwargs):
        pass

    def get_basket_events(self, client_basket_id: str):
        return []

    def delete_basket(self, basket_id: str):
        return True


def test_basket_idempotency_acquire_and_duplicate():
    """Verify check_and_acquire prevents duplicate basket submission."""
    repo = MockBasketRepository()
    mgr = BasketIdempotencyManager(repository=repo, default_ttl_seconds=10)

    cid = "test_bkt_idemp_01"
    key = "hash_signature_123"

    # First acquisition succeeds
    assert mgr.check_and_acquire(cid, key) is True
    assert mgr.is_duplicate(cid) is True

    # Immediate second attempt fails
    assert mgr.check_and_acquire(cid, key) is False

    # Attempt with same key but different cid fails
    assert mgr.check_and_acquire("test_bkt_idemp_02", key) is False

    # Release cid
    mgr.release(cid, key)
    assert mgr.is_duplicate(cid) is False

    # Re-acquire succeeds after release
    assert mgr.check_and_acquire(cid, key) is True


def test_basket_idempotency_db_backing():
    """Verify that existing database records are rejected as duplicates."""
    repo = MockBasketRepository()
    repo.save_basket(Basket(client_basket_id="bkt_in_db_01"))

    mgr = BasketIdempotencyManager(repository=repo)
    assert mgr.is_duplicate("bkt_in_db_01") is True
    assert mgr.check_and_acquire("bkt_in_db_01") is False


def test_compute_basket_hash_deterministic():
    """Verify hash computation produces consistent SHA-256 for identical payloads."""
    legs = [
        {"trading_symbol": "NIFTY26NOV24500CE", "side": "BUY", "quantity": 50, "price": 100.0},
        {"trading_symbol": "NIFTY26NOV24700CE", "side": "SELL", "quantity": 50, "price": 40.0},
    ]

    h1 = BasketIdempotencyManager.compute_basket_hash(1, "BULL_CALL_SPREAD", legs)
    h2 = BasketIdempotencyManager.compute_basket_hash(1, "BULL_CALL_SPREAD", legs)
    assert h1 == h2
    assert len(h1) == 64

    # Modifying quantity alters hash
    legs_mod = [
        {"trading_symbol": "NIFTY26NOV24500CE", "side": "BUY", "quantity": 75, "price": 100.0},
        {"trading_symbol": "NIFTY26NOV24700CE", "side": "SELL", "quantity": 50, "price": 40.0},
    ]
    h3 = BasketIdempotencyManager.compute_basket_hash(1, "BULL_CALL_SPREAD", legs_mod)
    assert h1 != h3

