from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Any, Dict


# Predefined Event Constants for Future Expansion
ORDER_CREATED = "ORDER_CREATED"
ORDER_FILLED = "ORDER_FILLED"
LOGIN_SUCCESS = "LOGIN_SUCCESS"
WEBSOCKET_CONNECTED = "WEBSOCKET_CONNECTED"
SYSTEM_INITIALIZED = "SYSTEM_INITIALIZED"
RISK_BREACH_DETECTED = "RISK_BREACH_DETECTED"

# Phase 3 Broker Connectivity Events
BROKER_CONNECTED = "BROKER_CONNECTED"
BROKER_DISCONNECTED = "BROKER_DISCONNECTED"
BROKER_AUTHENTICATED = "BROKER_AUTHENTICATED"
BROKER_SESSION_RESTORED = "BROKER_SESSION_RESTORED"
BROKER_SESSION_EXPIRED = "BROKER_SESSION_EXPIRED"

# Phase 4 Real-Time Streaming & Telemetry Events
WS_STATE_CHANGED = "WS_STATE_CHANGED"
WS_CONNECTED = "WS_CONNECTED"
WS_DISCONNECTED = "WS_DISCONNECTED"
WS_HEARTBEAT_MISSED = "WS_HEARTBEAT_MISSED"
WS_SUBSCRIPTION_ADDED = "WS_SUBSCRIPTION_ADDED"
WS_SUBSCRIPTION_REMOVED = "WS_SUBSCRIPTION_REMOVED"
CIRCUIT_BREAKER_TRIPPED = "CIRCUIT_BREAKER_TRIPPED"
CIRCUIT_BREAKER_RESET = "CIRCUIT_BREAKER_RESET"


@dataclass(frozen=True)
class Event:
    """Immutable event payload container."""

    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
