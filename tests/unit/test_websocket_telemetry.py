import time
from app.broker.services.websocket_telemetry import WebSocketTelemetryTracker


def test_telemetry_connection_counting():
    """Verify connection_count increments and timestamp is updated."""
    tracker = WebSocketTelemetryTracker()
    assert tracker.get_metrics()["connection_count"] == 0

    tracker.record_connection()
    metrics = tracker.get_metrics()
    assert metrics["connection_count"] == 1
    assert metrics["last_connected_time"] is not None

    tracker.record_connection()
    assert tracker.get_metrics()["connection_count"] == 2


def test_telemetry_reconnect_counting_and_cma():
    """Verify reconnect_count and Cumulative Moving Average (CMA) calculation."""
    tracker = WebSocketTelemetryTracker()

    # 1. Start reconnect 1
    tracker.record_reconnect_start()
    assert tracker.get_metrics()["reconnect_count"] == 1
    time.sleep(0.05)  # simulate 50ms recovery
    tracker.record_reconnect_success()

    metrics = tracker.get_metrics()
    assert metrics["total_reconnect_samples"] == 1
    assert metrics["avg_reconnect_time_ms"] > 30.0

    # 2. Start reconnect 2 with artificial duration
    tracker.record_reconnect_start()
    assert tracker.get_metrics()["reconnect_count"] == 2
    # Mock current_reconnect_start to simulate exact duration
    tracker._current_reconnect_start = time.time() - 0.100  # 100ms
    tracker.record_reconnect_success()

    assert tracker.get_metrics()["total_reconnect_samples"] == 2


def test_telemetry_heartbeat_miss():
    """Verify heartbeat_miss_count increments properly."""
    tracker = WebSocketTelemetryTracker()
    assert tracker.get_metrics()["heartbeat_miss_count"] == 0

    tracker.record_heartbeat_miss()
    tracker.record_heartbeat_miss()
    assert tracker.get_metrics()["heartbeat_miss_count"] == 2


def test_telemetry_reset():
    """Verify reset zeroes all metrics."""
    tracker = WebSocketTelemetryTracker()
    tracker.record_connection()
    tracker.record_reconnect_start()
    tracker.record_heartbeat_miss()

    tracker.reset()
    metrics = tracker.get_metrics()
    assert metrics["connection_count"] == 0
    assert metrics["reconnect_count"] == 0
    assert metrics["heartbeat_miss_count"] == 0
    assert metrics["avg_reconnect_time_ms"] == 0.0
    assert metrics["last_connected_time"] is None
