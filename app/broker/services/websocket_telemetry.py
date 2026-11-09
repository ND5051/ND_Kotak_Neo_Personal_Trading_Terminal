from dataclasses import dataclass
from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, Optional

from app.logging.logger import get_logger

logger = get_logger("app.broker.services.websocket_telemetry")


@dataclass
class WebSocketMetrics:
    """Immutable snapshot of streaming connectivity telemetry."""

    connection_count: int = 0
    reconnect_count: int = 0
    heartbeat_miss_count: int = 0
    avg_reconnect_time_ms: float = 0.0
    last_connected_time: Optional[str] = None
    total_reconnect_samples: int = 0
    total_ticks_processed: int = 0
    cma_tick_latency_ms: float = 0.0
    last_tick_latency_ms: float = 0.0


class WebSocketTelemetryTracker:
    """
    Thread-safe operational telemetry tracker monitoring WebSocket connection health,
    reconnection frequency, heartbeat timeouts, and carrier recovery latency.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._connection_count: int = 0
        self._reconnect_count: int = 0
        self._heartbeat_miss_count: int = 0
        self._avg_reconnect_time_ms: float = 0.0
        self._last_connected_time: Optional[str] = None
        self._total_reconnect_samples: int = 0
        self._current_reconnect_start: Optional[float] = None
        self._total_ticks_processed: int = 0
        self._cma_tick_latency_ms: float = 0.0
        self._last_tick_latency_ms: float = 0.0

    def record_connection(self) -> None:
        """Record successful transition to CONNECTED state."""
        with self._lock:
            self._connection_count += 1
            self._last_connected_time = datetime.now(timezone.utc).isoformat()
            logger.debug(
                f"WebSocket connected. Total connections: {self._connection_count}",
                event="WS_METRIC_CONNECTED",
                connection_count=self._connection_count,
            )

    def record_reconnect_start(self) -> None:
        """Mark initiation of reconnection loop following unexpected disconnection."""
        with self._lock:
            self._reconnect_count += 1
            self._current_reconnect_start = time.time()
            logger.debug(
                f"WebSocket reconnect cycle started. Reconnect count: {self._reconnect_count}",
                event="WS_METRIC_RECONNECT_START",
                reconnect_count=self._reconnect_count,
            )

    def record_reconnect_success(self) -> None:
        """
        Record successful reconnection recovery, updating Cumulative Moving Average (CMA)
        reconnect duration in milliseconds.
        """
        with self._lock:
            if self._current_reconnect_start is not None:
                duration_ms = (time.time() - self._current_reconnect_start) * 1000.0
                self._current_reconnect_start = None
                self._total_reconnect_samples += 1

                # Cumulative Moving Average: CMA_k = CMA_{k-1} + (x_k - CMA_{k-1}) / k
                k = self._total_reconnect_samples
                self._avg_reconnect_time_ms += (duration_ms - self._avg_reconnect_time_ms) / k
                logger.info(
                    f"WebSocket reconnected in {duration_ms:.1f}ms. Avg reconnect: {self._avg_reconnect_time_ms:.1f}ms",
                    event="WS_METRIC_RECONNECT_SUCCESS",
                    duration_ms=round(duration_ms, 2),
                    avg_reconnect_ms=round(self._avg_reconnect_time_ms, 2),
                )

            # Mark connected
            self.record_connection()

    def record_heartbeat_miss(self) -> None:
        """Record heartbeat silence timeout (e.g. 15s elapsed without data or pong)."""
        with self._lock:
            self._heartbeat_miss_count += 1
            logger.warning(
                f"WebSocket heartbeat silence timeout. Total misses: {self._heartbeat_miss_count}",
                event="WS_METRIC_HEARTBEAT_MISS",
                heartbeat_miss_count=self._heartbeat_miss_count,
            )

    def record_tick_latency(self, latency_ms: float) -> None:
        """
        Record tick latency between upstream exchange source timestamp and local gateway ingestion.
        Maintains Cumulative Moving Average (CMA) latency.
        """
        with self._lock:
            self._total_ticks_processed += 1
            self._last_tick_latency_ms = round(max(0.0, latency_ms), 2)
            n = self._total_ticks_processed
            # CMA: CMA_n = CMA_{n-1} + (x_n - CMA_{n-1}) / n
            self._cma_tick_latency_ms += (self._last_tick_latency_ms - self._cma_tick_latency_ms) / n

    def get_metrics(self) -> Dict[str, Any]:
        """Retrieve thread-safe diagnostic dictionary."""
        with self._lock:
            return {
                "connection_count": self._connection_count,
                "reconnect_count": self._reconnect_count,
                "heartbeat_miss_count": self._heartbeat_miss_count,
                "avg_reconnect_time_ms": round(self._avg_reconnect_time_ms, 2),
                "last_connected_time": self._last_connected_time,
                "total_reconnect_samples": self._total_reconnect_samples,
                "total_ticks_processed": self._total_ticks_processed,
                "cma_tick_latency_ms": round(self._cma_tick_latency_ms, 2),
                "last_tick_latency_ms": self._last_tick_latency_ms,
            }

    def reset(self) -> None:
        """Reset all metrics (used during teardown and testing)."""
        with self._lock:
            self._connection_count = 0
            self._reconnect_count = 0
            self._heartbeat_miss_count = 0
            self._avg_reconnect_time_ms = 0.0
            self._last_connected_time = None
            self._total_reconnect_samples = 0
            self._current_reconnect_start = None
            self._total_ticks_processed = 0
            self._cma_tick_latency_ms = 0.0
            self._last_tick_latency_ms = 0.0


# Global singleton tracker
ws_telemetry_tracker = WebSocketTelemetryTracker()
