from datetime import datetime, timedelta, timezone
import pytest

from app.broker.adapters.kotak_adapter import KotakBrokerAdapter
from app.broker.cache.broker_cache import broker_cache
from app.core.exceptions import ValidationException


@pytest.fixture(autouse=True)
def clean_cache():
    broker_cache.clear()
    yield
    broker_cache.clear()


def test_adapter_login_success():
    """Verify KotakBrokerAdapter login succeeds and populates cache."""
    adapter = KotakBrokerAdapter()
    credentials = {
        "consumer_key": "test_consumer_key",
        "consumer_secret": "test_consumer_secret",
        "mobile_number": "9876543210",
        "ucc": "TESTUCC",
        "mpin": "123456",
        "totp_secret": "JBSWY3DPEHPK3PXP",
    }

    result = adapter.login(credentials)
    assert result["session_token"] is not None
    assert result["refresh_token"] is not None
    assert result["broker_name"] == "KOTAK_NEO"
    assert adapter.is_connected() is True
    assert broker_cache.get_status() == "AUTHENTICATED"


def test_adapter_login_missing_credentials():
    """Verify missing consumer key or secret raises ValidationException."""
    adapter = KotakBrokerAdapter()
    with pytest.raises(ValidationException):
        adapter.login({"consumer_key": ""})


def test_adapter_validate_session():
    """Verify session validation when active and after expiration."""
    adapter = KotakBrokerAdapter()
    adapter.login({
        "consumer_key": "key",
        "consumer_secret": "secret",
    })
    assert adapter.validate_session() is True

    # Manually expire
    adapter._expiry_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert adapter.validate_session() is False
    assert adapter.is_connected() is False
    assert broker_cache.get_status() == "SESSION_EXPIRED"


def test_adapter_restore_session():
    """Verify restoring active and expired sessions."""
    adapter = KotakBrokerAdapter()

    # Valid restore
    session_data = {
        "session_token": "valid_token_xyz",
        "refresh_token": "valid_refresh_abc",
        "expiry_time": datetime.now(timezone.utc) + timedelta(hours=4),
    }
    assert adapter.restore_session(session_data) is True
    assert adapter.is_connected() is True
    assert broker_cache.get_status() == "AUTHENTICATED"

    # Expired restore
    expired_data = {
        "session_token": "expired_token_xyz",
        "expiry_time": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    assert adapter.restore_session(expired_data) is False


def test_adapter_logout():
    """Verify logout resets connectivity and clears cache."""
    adapter = KotakBrokerAdapter()
    adapter.login({"consumer_key": "k", "consumer_secret": "s"})
    assert adapter.is_connected() is True

    assert adapter.logout() is True
    assert adapter.is_connected() is False
    assert broker_cache.get_status() == "DISCONNECTED"


def test_adapter_capabilities_and_health_check():
    """Verify capability discovery and health check diagnostics."""
    adapter = KotakBrokerAdapter()
    caps = adapter.get_capabilities()
    assert "NSE" in caps["supported_exchanges"]
    assert "MIS" in caps["supported_products"]
    assert "LIMIT" in caps["supported_order_types"]

    # Health check
    health = adapter.health_check()
    assert "status" in health
    assert "latency_ms" in health
    assert health["connected"] is False
