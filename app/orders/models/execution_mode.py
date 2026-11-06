from enum import Enum
import os
import threading
from typing import Optional

from app.core.audit import (
    audit_logger,
    AuditCategory,
    AUDIT_EXECUTION_MODE_CHANGED,
)
from app.core.exceptions import ExecutionModeException
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import EXECUTION_MODE_CHANGED
from app.logging.logger import get_logger

logger = get_logger("app.orders.execution_mode")


class ExecutionMode(str, Enum):
    """
    Authoritative order execution gating modes.
    - DISABLED: Strict execution refusal across all channels (Default).
    - PAPER: Simulated paper execution (local mocks & database tracking).
    - LIVE: Direct wire submission to Kotak Neo Broker API.
    """
    DISABLED = "DISABLED"
    PAPER = "PAPER"
    LIVE = "LIVE"


class ExecutionModeManager:
    """
    Thread-safe governor controlling global order execution mode.
    Guarantees that all order placement, modification, and cancellation
    pipelines refuse wire submission unless explicitly permitted.
    """

    def __init__(self, default_mode: Optional[ExecutionMode] = None) -> None:
        self._lock = threading.RLock()
        env_mode_str = os.getenv("EXECUTION_MODE", "DISABLED").upper()
        try:
            initial_mode = default_mode or ExecutionMode(env_mode_str)
        except ValueError:
            initial_mode = ExecutionMode.DISABLED
        self._mode: ExecutionMode = initial_mode
        logger.info(f"ExecutionMode initialized to: {self._mode.value}", event="EXECUTION_MODE_INIT")

    @property
    def mode(self) -> ExecutionMode:
        with self._lock:
            return self._mode

    def get_mode(self) -> ExecutionMode:
        return self.mode

    def set_mode(self, new_mode: ExecutionMode | str, actor: str = "operator") -> ExecutionMode:
        """Update active execution mode, dispatches event, and writes audit trail."""
        with self._lock:
            if isinstance(new_mode, str):
                try:
                    mode_enum = ExecutionMode(new_mode.upper())
                except ValueError:
                    raise ExecutionModeException(f"Invalid execution mode: {new_mode}. Allowed: DISABLED, PAPER, LIVE")
            else:
                mode_enum = new_mode

            prev_mode = self._mode
            self._mode = mode_enum

            logger.warning(
                f"Execution mode changed: {prev_mode.value} -> {mode_enum.value} by {actor}",
                event="EXECUTION_MODE_CHANGED",
                previous_mode=prev_mode.value,
                new_mode=mode_enum.value,
                actor=actor,
            )

            # Audit Trail
            audit_logger.record(
                category=AuditCategory.ORDER,
                action=AUDIT_EXECUTION_MODE_CHANGED,
                actor=actor,
                correlation_id=get_correlation_id(),
                request_id=get_request_id(),
                details={
                    "previous_mode": prev_mode.value,
                    "new_mode": mode_enum.value,
                },
            )

            # Event Bus
            publish(
                EXECUTION_MODE_CHANGED,
                {
                    "previous_mode": prev_mode.value,
                    "new_mode": mode_enum.value,
                    "actor": actor,
                },
            )

            return self._mode

    def is_live(self) -> bool:
        with self._lock:
            return self._mode == ExecutionMode.LIVE

    def is_paper(self) -> bool:
        with self._lock:
            return self._mode == ExecutionMode.PAPER

    def is_disabled(self) -> bool:
        with self._lock:
            return self._mode == ExecutionMode.DISABLED

    def assert_execution_permitted(self) -> None:
        """
        Enforce execution mode gate.
        Raises ExecutionModeException if mode is DISABLED.
        """
        with self._lock:
            if self._mode == ExecutionMode.DISABLED:
                raise ExecutionModeException(
                    "Order execution is strictly DISABLED. Wire submission and paper execution are refused."
                )


# Global singleton manager
execution_mode_manager = ExecutionModeManager()

