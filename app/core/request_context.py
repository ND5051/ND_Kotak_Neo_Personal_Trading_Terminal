from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Optional, Union
from flask import g, has_request_context


@dataclass
class RequestContext:
    """
    Central request execution context.
    Carries correlation identifiers, security identity, and timing across middleware,
    services, and audit logs.
    """

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    user_id: Optional[Union[int, str]] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
        }


def get_current_context() -> RequestContext:
    """
    Retrieve active RequestContext for current execution thread / request.
    Falls back to a default system execution context when invoked outside HTTP request.
    """
    if has_request_context() and hasattr(g, "request_context"):
        return g.request_context
    return RequestContext(
        request_id=f"sys-{uuid.uuid4()}",
        correlation_id=f"sys-corr-{uuid.uuid4()}",
    )


def set_current_context(context: RequestContext) -> None:
    """Store context onto Flask g."""
    if has_request_context():
        g.request_context = context


def get_correlation_id() -> str:
    """Quick accessor for active correlation ID."""
    return get_current_context().correlation_id


def get_request_id() -> str:
    """Quick accessor for active request ID."""
    return get_current_context().request_id
