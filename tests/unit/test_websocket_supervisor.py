import time
import pytest

from app.broker.adapters.kotak_stream_adapter import KotakStreamAdapter
from app.broker.services.broker_circuit_breaker import BrokerCircuitBreaker
from app.broker.services.subscription_manager import SubscriptionManager
from app.broker.services.websocket_supervisor import (
    StreamState,
    WebSocketSupervisor,
)
from app.broker.services.websocket_telemetry import WebSocketTelemetryTracker


def test_supervisor_initial_state():
    """Verify initial state of WebSocketSupervisor is DISCONNECTED."""
    sup = WebSocketSupervisor()
    assert sup.state == StreamState.DISCONNECTED
    assert sup.is_connected() is False


def test_supervisor_start_and_connect():
    """Verify start() launches loop and transitions to CONNECTED."""
    adapter = KotakStreamAdapter()
    cb = BrokerCircuitBreaker(name="TEST_CB")
    sub = SubscriptionManager()
    sub.subscribe("26000", "nse_cm")
    sub.subscribe("11536", "nse_cm")
    telemetry = WebSocketTelemetryTracker()

    sup = WebSocketSupervisor(
        adapter=adapter,
        circuit_breaker=cb,
        sub_manager=sub,
        telemetry=telemetry,
    )

    started = sup.start(session_token="test_mock_token_123")
    assert started is True

    # Allow async thread to process connection
    for _ in range(20):
        if sup.state == StreamState.CONNECTED:
            break
        time.sleep(0.05)

    assert sup.state == StreamState.CONNECTED
    assert sup.is_connected() is True
    assert telemetry.get_metrics()["connection_count"] == 1

    diag = sup.get_diagnostics()
    assert diag["state"] == "CONNECTED"
    assert diag["subscribed_scrip_count"] == 2
    assert diag["circuit_breaker"]["state"] == "CLOSED"

    # Clean shutdown
    stopped = sup.stop()
    assert stopped is True
    assert sup.state == StreamState.DISCONNECTED


def test_supervisor_blocked_by_open_circuit_breaker():
    """Verify start() fails and transitions to FAILED when circuit breaker is OPEN."""
    adapter = KotakStreamAdapter()
    cb = BrokerCircuitBreaker(name="TEST_CB", failure_threshold=1)
    cb.record_failure("Pre-existing outage")

    sup = WebSocketSupervisor(adapter=adapter, circuit_breaker=cb)
    started = sup.start(session_token="token_xyz")

    assert started is False
    assert sup.state == StreamState.FAILED
    assert sup.is_connected() is False
