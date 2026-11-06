from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any, Dict, Optional

from app.core.request_context import get_current_context
from app.logging.logger import get_logger

logger = get_logger("app.core.audit")


class AuditCategory(str, Enum):
    """Categories of auditable events per project constitution."""

    AUTH = "AUTH"
    ORDER = "ORDER"
    SESSION = "SESSION"
    BASKET = "BASKET"
    SYSTEM = "SYSTEM"
    BROKER = "BROKER"
    MARKET_WATCH = "MARKET_WATCH"


# Phase 2 Audit Actions
LOGIN_SUCCESS = "LOGIN_SUCCESS"
LOGIN_FAILED = "LOGIN_FAILED"
LOGOUT = "LOGOUT"
SESSION_CREATED = "SESSION_CREATED"
SESSION_EXPIRED = "SESSION_EXPIRED"
PASSWORD_CHANGED = "PASSWORD_CHANGED"

# Phase 3 Broker Connectivity Audit Actions
BROKER_LOGIN_SUCCESS = "BROKER_LOGIN_SUCCESS"
BROKER_LOGIN_FAILED = "BROKER_LOGIN_FAILED"
BROKER_SESSION_CREATED = "BROKER_SESSION_CREATED"
BROKER_SESSION_RESTORED = "BROKER_SESSION_RESTORED"
BROKER_SESSION_EXPIRED = "BROKER_SESSION_EXPIRED"
BROKER_LOGOUT = "BROKER_LOGOUT"
BROKER_HEALTH_CHECK = "BROKER_HEALTH_CHECK"

# Phase 4 Real-Time Streaming & Circuit Breaker Audit Actions
WS_STATE_CHANGE = "WS_STATE_CHANGE"
WS_CONNECTED = "WS_CONNECTED"
WS_DISCONNECTED = "WS_DISCONNECTED"
WS_HEARTBEAT_TIMEOUT = "WS_HEARTBEAT_TIMEOUT"
CIRCUIT_BREAKER_TRIP = "CIRCUIT_BREAKER_TRIP"
CIRCUIT_BREAKER_RESET = "CIRCUIT_BREAKER_RESET"

# Phase 5 Market Watch Audit Actions
WATCHLIST_CREATED = "WATCHLIST_CREATED"
WATCHLIST_DELETED = "WATCHLIST_DELETED"
WATCHLIST_ITEM_ADDED = "WATCHLIST_ITEM_ADDED"
WATCHLIST_ITEM_REMOVED = "WATCHLIST_ITEM_REMOVED"
SCRIP_MASTER_DOWNLOAD = "SCRIP_MASTER_DOWNLOAD"

# Phase 6 Portfolio Foundation Audit Actions
PORTFOLIO_SYNC = "PORTFOLIO_SYNC"
HOLDINGS_RECONCILED = "HOLDINGS_RECONCILED"
POSITIONS_RECONCILED = "POSITIONS_RECONCILED"
MARGIN_SYNC = "MARGIN_SYNC"
POSITION_DISCREPANCY = "POSITION_DISCREPANCY"

# Phase 7 Order Foundation Audit Actions
AUDIT_ORDER_VALIDATION = "ORDER_VALIDATION"
AUDIT_ORDER_RISK_CHECK = "ORDER_RISK_CHECK"
AUDIT_ORDER_STATE_TRANSITION = "ORDER_STATE_TRANSITION"
AUDIT_ORDER_RECONCILIATION = "ORDER_RECONCILIATION"
AUDIT_ORDER_DISCREPANCY = "ORDER_DISCREPANCY"

# Phase 8 Order Execution Audit Actions
AUDIT_ORDER_PLACE = "ORDER_PLACE"
AUDIT_ORDER_MODIFY = "ORDER_MODIFY"
AUDIT_ORDER_CANCEL = "ORDER_CANCEL"
AUDIT_ORDER_EXECUTION_FILL = "ORDER_EXECUTION_FILL"
AUDIT_EMERGENCY_CANCEL_ALL = "EMERGENCY_CANCEL_ALL"
AUDIT_ORDER_EXECUTION_FAILURE = "ORDER_EXECUTION_FAILURE"
AUDIT_EXECUTION_MODE_CHANGED = "EXECUTION_MODE_CHANGED"


@dataclass(frozen=True)
class AuditRecord:
    """Immutable audit record structure with correlation & request tracking."""

    category: AuditCategory
    action: str
    actor: str = "system"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AuditLogger:
    """
    Central Audit Framework.
    Guarantees every critical business action has an immutable log trace
    tied to a correlation_id and request_id.
    """

    def record(
        self,
        category: AuditCategory | str,
        action: str,
        actor: str = "system",
        correlation_id: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditRecord:
        """Record an audit trail event linking correlation context."""
        cat_enum = (
            category if isinstance(category, AuditCategory) else AuditCategory(str(category).upper())
        )

        ctx = get_current_context()
        active_corr_id = correlation_id or ctx.correlation_id
        active_req_id = request_id or ctx.request_id

        record = AuditRecord(
            category=cat_enum,
            action=action,
            actor=actor,
            correlation_id=active_corr_id,
            request_id=active_req_id,
            details=details or {},
        )

        logger.info(
            f"[AUDIT:{cat_enum.value}] {action} by {actor}",
            event="AUDIT_RECORD",
            audit_category=cat_enum.value,
            audit_action=action,
            actor=actor,
            correlation_id=active_corr_id,
            request_id=active_req_id,
            audit_id=record.event_id,
            details=record.details,
        )
        return record


# Global Audit Logger Singleton
audit_logger = AuditLogger()
