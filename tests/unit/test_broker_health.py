import pytest

from app.broker.adapters.kotak_adapter import KotakBrokerAdapter
from app.broker.cache.broker_cache import broker_cache
from app.broker.services.broker_health_service import (
    BrokerHealthService,
    BrokerStatus,
)


@pytest.fixture(autouse=True)
def clean_cache():
    broker_cache.clear()
    yield
    broker_cache.clear()


def test_health_monitoring_states():
    """Verify health service accurately reports DISCONNECTED, AUTHENTICATED, and EXPIRED."""
    adapter = KotakBrokerAdapter()
    svc = BrokerHealthService(adapter=adapter)

    # 1. Initially DISCONNECTED
    assert svc.is_connected() is False
    assert svc.is_authenticated() is False
    assert svc.broker_status() in (BrokerStatus.DISCONNECTED.value, BrokerStatus.LOGIN_REQUIRED.value)

    # 2. Login -> AUTHENTICATED
    adapter.login({"consumer_key": "k", "consumer_secret": "s"})
    assert svc.is_connected() is True
    assert svc.is_authenticated() is True
    assert svc.broker_status() == BrokerStatus.AUTHENTICATED.value

    # 3. Expire -> SESSION_EXPIRED
    from datetime import datetime, timedelta, timezone

    adapter._expiry_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    adapter.validate_session()
    assert svc.is_connected() is False
    assert svc.broker_status() == BrokerStatus.SESSION_EXPIRED.value


def test_health_check_diagnostic_payload():
    """Verify perform_health_check returns structured payload."""
    adapter = KotakBrokerAdapter()
    svc = BrokerHealthService(adapter=adapter)

    health = svc.perform_health_check(actor="test_runner")
    assert "status" in health
    assert "latency_ms" in health
    assert "connected" in health
    assert "timestamp" in health
