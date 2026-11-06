from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import threading
import time
from typing import Any, Dict, List, Optional

from app.core.audit import (
    audit_logger,
    AuditCategory,
    CIRCUIT_BREAKER_TRIP,
    CIRCUIT_BREAKER_RESET,
)
from app.core.exceptions import BrokerCircuitBreakerOpenException
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import (
    CIRCUIT_BREAKER_TRIPPED,
    CIRCUIT_BREAKER_RESET as EVT_CIRCUIT_BREAKER_RESET,
)
from app.logging.logger import get_logger

logger = get_logger("app.broker.services.circuit_breaker")


class CircuitState(str, Enum):
    """Operational states of the Broker Circuit Breaker."""

    CLOSED = "CLOSED"        # Normal operation: requests pass through
    OPEN = "OPEN"            # Outage detected: fail-fast, block calls
    HALF_OPEN = "HALF_OPEN"  # Quarantine expired: allow canary trial request


@dataclass
class FailureRecord:
    timestamp: float
    error_message: str


class BrokerCircuitBreaker:
    """
    Three-state sliding-window Circuit Breaker guarding downstream Kotak Neo
    APIs and WebSocket endpoints from outage cascades and rate-limit penalties.
    """

    def __init__(
        self,
        name: str = "KOTAK_STREAMING",
        failure_threshold: int = 3,
        window_seconds: float = 30.0,
        cooldown_seconds: float = 30.0,
        half_open_canary_count: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self.half_open_canary_count = half_open_canary_count

        self._state: CircuitState = CircuitState.CLOSED
        self._lock = threading.RLock()
        self._failures: List[FailureRecord] = []
        self._cooldown_until: Optional[float] = None
        self._canary_trials_in_flight: int = 0
        self._total_trips: int = 0
        self._last_state_change: datetime = datetime.now(timezone.utc)

    @property
    def state(self) -> CircuitState:
        """Evaluate and return current state, checking cooldown expiry."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                now = time.time()
                if self._cooldown_until and now >= self._cooldown_until:
                    self._transition_to(CircuitState.HALF_OPEN, reason="Cooldown expired")
            return self._state

    def is_available(self) -> bool:
        """Check if calls are currently permitted without raising an exception."""
        with self._lock:
            curr_state = self.state
            if curr_state == CircuitState.CLOSED:
                return True
            if curr_state == CircuitState.HALF_OPEN:
                return self._canary_trials_in_flight < self.half_open_canary_count
            return False

    def allow_request(self) -> bool:
        """
        Verify request authorization. Raises BrokerCircuitBreakerOpenException
        if state is OPEN.
        """
        with self._lock:
            curr_state = self.state
            if curr_state == CircuitState.CLOSED:
                return True

            if curr_state == CircuitState.HALF_OPEN:
                if self._canary_trials_in_flight < self.half_open_canary_count:
                    self._canary_trials_in_flight += 1
                    return True
                raise BrokerCircuitBreakerOpenException(
                    message=f"Circuit Breaker '{self.name}' is HALF-OPEN: canary request already in flight."
                )

            # OPEN state
            cooldown_remaining = max(0.0, (self._cooldown_until or 0) - time.time())
            raise BrokerCircuitBreakerOpenException(
                message=(
                    f"Circuit Breaker '{self.name}' is OPEN. "
                    f"Fail-fast active; cooldown remaining: {cooldown_remaining:.1f}s."
                ),
                details={
                    "breaker": self.name,
                    "state": self._state.value,
                    "cooldown_remaining_seconds": round(cooldown_remaining, 1),
                    "total_trips": self._total_trips,
                },
            )

    def record_success(self) -> None:
        """Record successful upstream interaction."""
        with self._lock:
            curr_state = self.state
            if curr_state == CircuitState.HALF_OPEN:
                # Canary succeeded -> restore CLOSED
                self._transition_to(CircuitState.CLOSED, reason="Canary trial succeeded")
                self._failures.clear()
                self._canary_trials_in_flight = 0
            elif curr_state == CircuitState.CLOSED:
                self._prune_expired_failures()

    def record_failure(self, error: Optional[Exception | str] = None) -> None:
        """Record upstream interaction failure and evaluate threshold tripping."""
        now = time.time()
        err_msg = str(error) if error else "Unknown broker communication error"

        with self._lock:
            curr_state = self.state
            self._failures.append(FailureRecord(timestamp=now, error_message=err_msg))
            self._prune_expired_failures()

            if curr_state == CircuitState.HALF_OPEN:
                # Canary trial failed -> re-trip OPEN with double cooldown
                self.cooldown_seconds = min(120.0, self.cooldown_seconds * 2)
                self._transition_to(
                    CircuitState.OPEN,
                    reason=f"Canary failed: {err_msg}",
                    cooldown=self.cooldown_seconds,
                )
                self._canary_trials_in_flight = 0

            elif curr_state == CircuitState.CLOSED:
                if len(self._failures) >= self.failure_threshold:
                    self._transition_to(
                        CircuitState.OPEN,
                        reason=f"Exceeded {self.failure_threshold} failures in {self.window_seconds}s",
                        cooldown=self.cooldown_seconds,
                    )

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED, reason="Manual operator reset")
            self._failures.clear()
            self._canary_trials_in_flight = 0
            self._cooldown_until = None

    def get_metrics(self) -> Dict[str, Any]:
        """Retrieve diagnostic telemetry metrics."""
        with self._lock:
            curr_state = self.state
            cooldown_left = (
                max(0.0, (self._cooldown_until or 0) - time.time())
                if curr_state == CircuitState.OPEN and self._cooldown_until
                else 0.0
            )
            return {
                "name": self.name,
                "state": curr_state.value,
                "is_available": self.is_available(),
                "failure_count": len(self._failures),
                "failure_threshold": self.failure_threshold,
                "cooldown_remaining_seconds": round(cooldown_left, 1),
                "total_trips": self._total_trips,
                "last_state_change": self._last_state_change.isoformat(),
            }

    def _prune_expired_failures(self) -> None:
        """Remove failure events outside the rolling window."""
        cutoff = time.time() - self.window_seconds
        self._failures = [f for f in self._failures if f.timestamp >= cutoff]

    def _transition_to(
        self,
        new_state: CircuitState,
        reason: str,
        cooldown: Optional[float] = None,
    ) -> None:
        """Execute state transition, auditing, and event notification."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = datetime.now(timezone.utc)

        if new_state == CircuitState.OPEN:
            self._total_trips += 1
            duration = cooldown or self.cooldown_seconds
            self._cooldown_until = time.time() + duration

            audit_logger.record(
                category=AuditCategory.BROKER,
                action=CIRCUIT_BREAKER_TRIP,
                actor="circuit_breaker",
                correlation_id=get_correlation_id(),
                request_id=get_request_id(),
                details={
                    "breaker": self.name,
                    "previous_state": old_state.value,
                    "current_state": new_state.value,
                    "reason": reason,
                    "cooldown_seconds": duration,
                    "total_trips": self._total_trips,
                },
            )
            publish(
                CIRCUIT_BREAKER_TRIPPED,
                {
                    "breaker": self.name,
                    "state": new_state.value,
                    "reason": reason,
                    "cooldown_seconds": duration,
                },
            )
            logger.warning(
                f"Broker Circuit Breaker '{self.name}' TRIPPED to OPEN ({reason})",
                event="CIRCUIT_BREAKER_TRIPPED",
                breaker=self.name,
                cooldown=duration,
            )

        elif new_state == CircuitState.CLOSED and old_state != CircuitState.CLOSED:
            audit_logger.record(
                category=AuditCategory.BROKER,
                action=CIRCUIT_BREAKER_RESET,
                actor="circuit_breaker",
                correlation_id=get_correlation_id(),
                request_id=get_request_id(),
                details={"breaker": self.name, "reason": reason},
            )
            publish(
                EVT_CIRCUIT_BREAKER_RESET,
                {"breaker": self.name, "state": new_state.value, "reason": reason},
            )
            logger.info(
                f"Broker Circuit Breaker '{self.name}' RESET to CLOSED ({reason})",
                event="CIRCUIT_BREAKER_RESET",
                breaker=self.name,
            )


# Global singleton instance for broker communication
broker_circuit_breaker = BrokerCircuitBreaker()
