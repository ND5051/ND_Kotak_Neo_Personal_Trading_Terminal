import pytest

from app.core.exceptions import ExecutionModeException
from app.events.event_bus import subscribe
from app.events.event_types import EXECUTION_MODE_CHANGED
from app.orders.models.execution_mode import (
    ExecutionMode,
    ExecutionModeManager,
)


def test_execution_mode_default_and_gating():
    """Verify default execution mode is DISABLED and enforces refusal."""
    mgr = ExecutionModeManager(default_mode=ExecutionMode.DISABLED)
    assert mgr.get_mode() == ExecutionMode.DISABLED
    assert mgr.is_disabled() is True
    assert mgr.is_paper() is False
    assert mgr.is_live() is False

    with pytest.raises(ExecutionModeException) as exc_info:
        mgr.assert_execution_permitted()
    assert "DISABLED" in str(exc_info.value)


def test_execution_mode_transitions_and_events():
    """Verify valid mode transitions and EventBus dispatch."""
    mgr = ExecutionModeManager(default_mode=ExecutionMode.DISABLED)

    events_received = []

    def on_mode_change(payload):
        events_received.append(payload)

    sub_id = subscribe(EXECUTION_MODE_CHANGED, on_mode_change)

    # Switch to PAPER
    mgr.set_mode(ExecutionMode.PAPER, actor="test_runner")
    assert mgr.get_mode() == ExecutionMode.PAPER
    assert mgr.is_paper() is True
    # Should not raise
    mgr.assert_execution_permitted()

    # Switch to LIVE
    mgr.set_mode("LIVE", actor="test_runner")
    assert mgr.get_mode() == ExecutionMode.LIVE
    assert mgr.is_live() is True
    mgr.assert_execution_permitted()

    # Switch back to DISABLED
    mgr.set_mode("DISABLED", actor="test_runner")
    assert mgr.is_disabled() is True
    with pytest.raises(ExecutionModeException):
        mgr.assert_execution_permitted()

    assert len(events_received) == 3
    assert events_received[0].data["new_mode"] == "PAPER"
    assert events_received[1].data["new_mode"] == "LIVE"
    assert events_received[2].data["new_mode"] == "DISABLED"


def test_execution_mode_invalid_rejection():
    """Verify setting an unknown mode raises ExecutionModeException."""
    mgr = ExecutionModeManager(default_mode=ExecutionMode.DISABLED)
    with pytest.raises(ExecutionModeException):
        mgr.set_mode("HYPOTHETICAL_MODE")
