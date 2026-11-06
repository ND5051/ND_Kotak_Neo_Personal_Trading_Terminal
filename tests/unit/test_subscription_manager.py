import pytest

from app.broker.services.subscription_manager import SubscriptionManager
from app.core.exceptions import SubscriptionQuotaExceededException


def test_subscription_manager_subscribe_and_ref_count():
    """Verify first subscribe returns wire_call_needed=True and duplicate increments ref_count."""
    mgr = SubscriptionManager(max_quota=10)

    # First component subscribes -> wire call needed
    need_wire = mgr.subscribe("26000", "nse_cm")
    assert need_wire is True
    assert mgr.get_token_count() == 1
    assert mgr.get_ref_count("26000") == 1

    # Second component subscribes to same token -> no wire call
    need_wire = mgr.subscribe("26000", "nse_cm")
    assert need_wire is False
    assert mgr.get_token_count() == 1
    assert mgr.get_ref_count("26000") == 2


def test_subscription_manager_unsubscribe():
    """Verify unsubscribe decrements ref_count and purges only when reaching zero."""
    mgr = SubscriptionManager(max_quota=10)
    mgr.subscribe("11536", "nse_cm")
    mgr.subscribe("11536", "nse_cm")
    assert mgr.get_ref_count("11536") == 2

    # First unsubscribe -> ref_count drops to 1, no wire call needed
    need_wire = mgr.unsubscribe("11536")
    assert need_wire is False
    assert mgr.get_token_count() == 1
    assert mgr.get_ref_count("11536") == 1

    # Second unsubscribe -> ref_count drops to 0, wire call needed to unsubscribe
    need_wire = mgr.unsubscribe("11536")
    assert need_wire is True
    assert mgr.get_token_count() == 0
    assert mgr.get_ref_count("11536") == 0


def test_subscription_manager_quota_exceeded():
    """Verify adding more tokens than max_quota raises SubscriptionQuotaExceededException."""
    mgr = SubscriptionManager(max_quota=3)

    mgr.subscribe("token1", "nse_cm")
    mgr.subscribe("token2", "nse_cm")
    mgr.subscribe("token3", "nse_cm")
    assert mgr.get_token_count() == 3

    with pytest.raises(SubscriptionQuotaExceededException) as exc_info:
        mgr.subscribe("token4", "nse_cm")
    assert "quota limit" in str(exc_info.value)


def test_subscription_manager_batching():
    """Verify chunking tokens into batch sizes for transmission."""
    mgr = SubscriptionManager(max_quota=100)
    for i in range(12):
        mgr.subscribe(f"tok_{i}", "nse_cm")

    batches = mgr.get_token_batches(batch_size=5)
    assert len(batches) == 3
    assert len(batches[0]) == 5
    assert len(batches[1]) == 5
    assert len(batches[2]) == 2
