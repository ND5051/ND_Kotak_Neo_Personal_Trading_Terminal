import time
import pytest

from app.broker.services.broker_circuit_breaker import (
    BrokerCircuitBreaker,
    CircuitState,
)
from app.core.exceptions import BrokerCircuitBreakerOpenException


def test_circuit_breaker_normal_closed_state():
    """Verify normal requests pass through when circuit is CLOSED."""
    cb = BrokerCircuitBreaker(name="TEST_BREAKER", failure_threshold=3, window_seconds=10.0, cooldown_seconds=2.0)
    assert cb.state == CircuitState.CLOSED
    assert cb.is_available() is True
    assert cb.allow_request() is True

    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_circuit_breaker_tripping_to_open():
    """Verify exceeding failure threshold trips circuit breaker to OPEN."""
    cb = BrokerCircuitBreaker(name="TEST_BREAKER", failure_threshold=3, window_seconds=10.0, cooldown_seconds=2.0)

    # 1st failure
    cb.record_failure("Socket timeout 1")
    assert cb.state == CircuitState.CLOSED

    # 2nd failure
    cb.record_failure("Socket timeout 2")
    assert cb.state == CircuitState.CLOSED

    # 3rd failure -> Trips to OPEN
    cb.record_failure("Socket timeout 3")
    assert cb.state == CircuitState.OPEN
    assert cb.is_available() is False

    # Immediate call must fail-fast with BrokerCircuitBreakerOpenException
    with pytest.raises(BrokerCircuitBreakerOpenException) as exc_info:
        cb.allow_request()
    assert "is OPEN" in str(exc_info.value)


def test_circuit_breaker_cooldown_and_half_open_recovery():
    """Verify cooldown expiration moves state to HALF_OPEN and canary success restores CLOSED."""
    cb = BrokerCircuitBreaker(name="TEST_BREAKER", failure_threshold=2, window_seconds=5.0, cooldown_seconds=0.1)

    cb.record_failure("err1")
    cb.record_failure("err2")
    assert cb.state == CircuitState.OPEN

    # Wait for cooldown to expire
    time.sleep(0.15)
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.is_available() is True

    # Canary request allowed
    assert cb.allow_request() is True

    # Second concurrent canary request rejected in HALF_OPEN
    with pytest.raises(BrokerCircuitBreakerOpenException):
        cb.allow_request()

    # Canary succeeds -> restores CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.is_available() is True


def test_circuit_breaker_half_open_failure_retrips_with_penalty():
    """Verify canary failure in HALF_OPEN immediately re-trips to OPEN with doubled cooldown."""
    cb = BrokerCircuitBreaker(name="TEST_BREAKER", failure_threshold=2, window_seconds=5.0, cooldown_seconds=0.1)

    cb.record_failure("err1")
    cb.record_failure("err2")
    assert cb.state == CircuitState.OPEN

    time.sleep(0.15)
    assert cb.state == CircuitState.HALF_OPEN

    # Canary trial fails
    cb.record_failure("canary failed")
    assert cb.state == CircuitState.OPEN
    # Cooldown was doubled from 0.1 to 0.2
    assert cb.cooldown_seconds == 0.2


def test_circuit_breaker_manual_reset():
    """Verify manual reset restores CLOSED state and clears failures."""
    cb = BrokerCircuitBreaker(name="TEST_BREAKER", failure_threshold=2, window_seconds=5.0, cooldown_seconds=10.0)
    cb.record_failure("err1")
    cb.record_failure("err2")
    assert cb.state == CircuitState.OPEN

    cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb.is_available() is True
    metrics = cb.get_metrics()
    assert metrics["failure_count"] == 0
    assert metrics["state"] == "CLOSED"
