import asyncio
from datetime import datetime, timezone
from enum import Enum
import random
import threading
import time
from typing import Any, Dict, Optional

from app.broker.adapters.kotak_stream_adapter import KotakStreamAdapter
from app.broker.cache.broker_cache import broker_cache
from app.broker.services.broker_circuit_breaker import (
    broker_circuit_breaker,
    BrokerCircuitBreaker,
)
from app.broker.services.subscription_manager import (
    subscription_manager,
    SubscriptionManager,
)
from app.broker.services.websocket_telemetry import (
    ws_telemetry_tracker,
    WebSocketTelemetryTracker,
)
from app.core.audit import (
    audit_logger,
    AuditCategory,
    WS_STATE_CHANGE,
    WS_CONNECTED as AUDIT_WS_CONNECTED,
    WS_DISCONNECTED as AUDIT_WS_DISCONNECTED,
    WS_HEARTBEAT_TIMEOUT as AUDIT_WS_HEARTBEAT_TIMEOUT,
)
from app.core.exceptions import (
    BrokerCircuitBreakerOpenException,
    BrokerException,
)
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import (
    WS_STATE_CHANGED,
    WS_CONNECTED as EVT_WS_CONNECTED,
    WS_DISCONNECTED as EVT_WS_DISCONNECTED,
    WS_HEARTBEAT_MISSED as EVT_WS_HEARTBEAT_MISSED,
)
from app.logging.logger import get_logger

logger = get_logger("app.broker.services.websocket_supervisor")


class StreamState(str, Enum):
    """Deterministic connection lifecycle states for streaming supervisor."""

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    FAILED = "FAILED"


class WebSocketSupervisor:
    """
    Lifecycle supervisor for Kotak Neo SFeed streaming WebSocket.
    Runs on an isolated daemon background thread with an asyncio event loop.
    Enforces exponential backoff, heartbeat watchdogs, subscription replay,
    circuit breaker guards, and operational metrics tracking.
    """

    PING_INTERVAL_SEC = 5.0
    HEARTBEAT_TIMEOUT_SEC = 15.0
    MAX_RECONNECT_ATTEMPTS = 10
    BASE_BACKOFF_SEC = 1.0
    MAX_BACKOFF_SEC = 30.0

    def __init__(
        self,
        adapter: Optional[KotakStreamAdapter] = None,
        circuit_breaker: Optional[BrokerCircuitBreaker] = None,
        sub_manager: Optional[SubscriptionManager] = None,
        telemetry: Optional[WebSocketTelemetryTracker] = None,
    ) -> None:
        self.adapter = adapter or KotakStreamAdapter()
        self.circuit_breaker = circuit_breaker or broker_circuit_breaker
        self.sub_manager = sub_manager or subscription_manager
        self.telemetry = telemetry or ws_telemetry_tracker

        self._state: StreamState = StreamState.DISCONNECTED
        self._lock = threading.RLock()
        self._ready_event = threading.Event()
        self._credentials: Dict[str, Any] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._reconnect_attempts: int = 0
        self._watchdog_task: Optional[asyncio.Task] = None
        self._stream_task: Optional[asyncio.Task] = None

    @property
    def state(self) -> StreamState:
        with self._lock:
            return self._state

    def is_connected(self) -> bool:
        with self._lock:
            return self._state == StreamState.CONNECTED and self.adapter.is_connected()

    def start(self, session_token: str, **kwargs: Any) -> bool:
        """
        Start the background streaming supervisor with broker session credentials.
        Validates circuit breaker and launches background loop.
        """
        with self._lock:
            if self._state in (StreamState.CONNECTING, StreamState.CONNECTED):
                logger.info("WebSocketSupervisor already running", state=self._state.value)
                return True

            # Verify Circuit Breaker before initiating connection
            try:
                self.circuit_breaker.allow_request()
            except BrokerCircuitBreakerOpenException as e:
                logger.warning(f"Cannot start streaming: {str(e)}", event="WS_START_BLOCKED")
                self._transition_to(StreamState.FAILED, reason=str(e))
                return False

            self._credentials = {"session_token": session_token, **kwargs}
            self._running = True
            self._reconnect_attempts = 0

            # Spawn dedicated daemon thread running asyncio loop
            if self._thread is None or not self._thread.is_alive():
                self._ready_event.clear()
                self._loop = asyncio.new_event_loop()
                self._thread = threading.Thread(
                    target=self._run_event_loop,
                    name="KotakWebSocketSupervisorThread",
                    daemon=True,
                )
                self._thread.start()
                self._ready_event.wait(timeout=3.0)
                logger.info("Spawned WebSocket supervisor daemon thread", event="WS_THREAD_SPAWNED")

            # Schedule connection task on loop
            if self._loop:
                asyncio.run_coroutine_threadsafe(self._initiate_connection(), self._loop)

            return True

    def stop(self) -> bool:
        """Gracefully stop streaming and terminate socket connection."""
        with self._lock:
            if self._state == StreamState.DISCONNECTED:
                return True

            self._running = False
            logger.info("Stopping WebSocket supervisor...", event="WS_STOP_REQUESTED")

            if self._loop and self._loop.is_running():
                future = asyncio.run_coroutine_threadsafe(self._teardown_socket(), self._loop)
                try:
                    future.result(timeout=2.0)
                except Exception as e:
                    logger.warning(f"Timeout or error during graceful socket stop: {str(e)}")
                self._loop.call_soon_threadsafe(self._loop.stop)

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
                self._thread = None
                self._loop = None

            self._transition_to(StreamState.DISCONNECTED, reason="Supervisor stopped by user/system")
            return True

    def get_diagnostics(self) -> Dict[str, Any]:
        """Return comprehensive status and telemetry snapshot."""
        with self._lock:
            return {
                "state": self._state.value,
                "is_connected": self.is_connected(),
                "metrics": self.telemetry.get_metrics(),
                "subscribed_scrip_count": self.sub_manager.get_token_count(),
                "circuit_breaker": self.circuit_breaker.get_metrics(),
            }

    # Internal Async Execution
    def _run_event_loop(self) -> None:
        """Worker thread entrypoint establishing dedicated asyncio loop."""
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.call_soon(self._ready_event.set)

        try:
            self._loop.run_forever()
        except Exception as e:
            logger.error(f"Unhandled exception in WebSocket loop: {str(e)}", exc_info=True)
        finally:
            try:
                # Cancel pending tasks
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
            except Exception:
                pass
            self._loop.close()
            logger.info("WebSocket supervisor event loop closed", event="WS_LOOP_CLOSED")

    async def _initiate_connection(self) -> None:
        """Asynchronous connection handler with handshake and error interception."""
        if not self._running:
            return

        self._transition_to(StreamState.CONNECTING, reason="Initiating socket handshake")

        try:
            # Check Circuit Breaker
            self.circuit_breaker.allow_request()

            success = await self.adapter.connect(self._credentials)
            if success:
                self.circuit_breaker.record_success()
                self._reconnect_attempts = 0

                # Check if this was a recovery reconnect or fresh connection
                if self.telemetry._current_reconnect_start is not None:
                    self.telemetry.record_reconnect_success()
                else:
                    self.telemetry.record_connection()

                self._transition_to(StreamState.CONNECTED, reason="Handshake and authentication successful")

                # Replay active subscriptions
                await self._replay_subscriptions()

                # Launch Heartbeat Watchdog
                if self._watchdog_task and not self._watchdog_task.done():
                    self._watchdog_task.cancel()
                self._watchdog_task = asyncio.create_task(self._heartbeat_watchdog_loop())

            else:
                await self._handle_connection_failure("Adapter returned False on connect")

        except Exception as e:
            await self._handle_connection_failure(str(e))

    async def _handle_connection_failure(self, error_message: str) -> None:
        """Handle connection drop or refusal, triggering circuit breaker and backoff."""
        self.circuit_breaker.record_failure(error_message)

        if not self._running:
            self._transition_to(StreamState.DISCONNECTED, reason="Stopped during failure handling")
            return

        self._reconnect_attempts += 1

        if self._reconnect_attempts > self.MAX_RECONNECT_ATTEMPTS:
            self._transition_to(
                StreamState.FAILED,
                reason=f"Max reconnection attempts ({self.MAX_RECONNECT_ATTEMPTS}) exceeded: {error_message}",
            )
            return

        self.telemetry.record_reconnect_start()
        self._transition_to(StreamState.RECONNECTING, reason=error_message)

        # Exponential backoff with random jitter
        backoff = min(
            self.MAX_BACKOFF_SEC,
            self.BASE_BACKOFF_SEC * (2 ** (self._reconnect_attempts - 1)),
        )
        jitter = random.uniform(0.1, 0.5) * backoff
        delay = backoff + jitter

        logger.info(
            f"Scheduling reconnect attempt {self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS} in {delay:.2f}s",
            event="WS_RECONNECT_SCHEDULED",
            attempt=self._reconnect_attempts,
            delay=round(delay, 2),
        )

        await asyncio.sleep(delay)

        if self._running:
            await self._initiate_connection()

    async def _heartbeat_watchdog_loop(self) -> None:
        """Continuous liveness watchdog sending pings and detecting silent dead sockets."""
        logger.debug("Heartbeat watchdog started", event="WS_WATCHDOG_START")

        while self._running and self._state == StreamState.CONNECTED:
            try:
                await asyncio.sleep(self.PING_INTERVAL_SEC)

                if self._state != StreamState.CONNECTED:
                    break

                now = time.time()
                last_rx = self.adapter.get_last_rx_timestamp()
                silence_delta = now - last_rx

                # Check if ping frame is needed
                if silence_delta >= self.PING_INTERVAL_SEC:
                    await self.adapter.send_ping()

                # Check if socket is silent-dead (missed 3 heartbeat cycles = 15s)
                if silence_delta >= self.HEARTBEAT_TIMEOUT_SEC:
                    logger.warning(
                        f"Heartbeat silence threshold breached ({silence_delta:.1f}s >= {self.HEARTBEAT_TIMEOUT_SEC}s)",
                        event="WS_HEARTBEAT_TIMEOUT",
                        silence_sec=round(silence_delta, 1),
                    )
                    self.telemetry.record_heartbeat_miss()

                    audit_logger.record(
                        category=AuditCategory.BROKER,
                        action=AUDIT_WS_HEARTBEAT_TIMEOUT,
                        actor="heartbeat_watchdog",
                        correlation_id=get_correlation_id(),
                        request_id=get_request_id(),
                        details={"silence_sec": round(silence_delta, 1)},
                    )
                    publish(
                        EVT_WS_HEARTBEAT_MISSED,
                        {"silence_sec": round(silence_delta, 1)},
                    )

                    # Forcibly abort socket and trigger reconnect
                    await self.adapter.disconnect()
                    await self._handle_connection_failure("Heartbeat silence timeout")
                    break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat watchdog loop: {str(e)}", exc_info=True)

    async def _replay_subscriptions(self) -> None:
        """Replay all active instruments from SubscriptionManager upon connection."""
        batches = self.sub_manager.get_token_batches(batch_size=500)
        total_tokens = self.sub_manager.get_token_count()

        if not batches:
            logger.debug("No active subscriptions to replay", event="WS_REPLAY_NONE")
            return

        logger.info(
            f"Replaying {total_tokens} instrument subscriptions across {len(batches)} batches",
            event="WS_REPLAY_START",
            token_count=total_tokens,
            batch_count=len(batches),
        )

        for batch in batches:
            if not self._running or self._state != StreamState.CONNECTED:
                break
            await self.adapter.send_subscription(batch)
            await asyncio.sleep(0.02)  # small inter-frame pause to prevent socket buffering spikes

    async def _teardown_socket(self) -> None:
        """Clean teardown of active socket and cancel watchdog tasks."""
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
            self._watchdog_task = None

        await self.adapter.disconnect()

    def _transition_to(self, new_state: StreamState, reason: str) -> None:
        """Execute state transition, telemetry sync, audit trail, and event publishing."""
        old_state = self._state
        self._state = new_state

        logger.info(
            f"WebSocket state changed: {old_state.value} -> {new_state.value} ({reason})",
            event="WS_STATE_TRANSITION",
            old_state=old_state.value,
            new_state=new_state.value,
            reason=reason,
        )

        # Audit Logging
        action_map = {
            StreamState.CONNECTED: AUDIT_WS_CONNECTED,
            StreamState.DISCONNECTED: AUDIT_WS_DISCONNECTED,
        }
        audit_action = action_map.get(new_state, WS_STATE_CHANGE)

        audit_logger.record(
            category=AuditCategory.BROKER,
            action=audit_action,
            actor="websocket_supervisor",
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={
                "previous_state": old_state.value,
                "current_state": new_state.value,
                "reason": reason,
                "metrics": self.telemetry.get_metrics(),
            },
        )

        # Event Bus Dispatch
        publish(
            WS_STATE_CHANGED,
            {
                "previous_state": old_state.value,
                "current_state": new_state.value,
                "reason": reason,
            },
        )

        if new_state == StreamState.CONNECTED:
            publish(EVT_WS_CONNECTED, {"timestamp": datetime.now(timezone.utc).isoformat()})
        elif new_state == StreamState.DISCONNECTED:
            publish(EVT_WS_DISCONNECTED, {"timestamp": datetime.now(timezone.utc).isoformat()})


# Global singleton supervisor instance
ws_supervisor = WebSocketSupervisor()
