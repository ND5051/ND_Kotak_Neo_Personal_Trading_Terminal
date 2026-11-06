import time
import pytest

from app.orders.services.idempotency_manager import IdempotencyManager


def test_idempotency_manager_acquire_and_duplicate():
    """Verify single-acquisition semantics and duplicate rejection."""
    mgr = IdempotencyManager(default_ttl_seconds=5)

    key1 = "order_uuid_111"
    # First acquire succeeds
    assert mgr.check_and_acquire(key1) is True
    assert mgr.is_duplicate(key1) is True

    # Second acquire for same key fails
    assert mgr.check_and_acquire(key1) is False


def test_idempotency_manager_release_and_clear():
    """Verify release and clear operations."""
    mgr = IdempotencyManager()
    key = "order_uuid_222"

    assert mgr.check_and_acquire(key) is True
    mgr.release(key)
    assert mgr.is_duplicate(key) is False

    # Should be acquirable again after release
    assert mgr.check_and_acquire(key) is True
    mgr.clear()
    assert mgr.is_duplicate(key) is False

