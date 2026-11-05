from functools import wraps
from typing import Any, Callable
from flask import g, request

from app.auth.repositories.user_repository import UserRepository
from app.auth.services.session_manager import session_manager
from app.core.audit import audit_logger, AuditCategory
from app.core.request_context import get_current_context, get_correlation_id, get_request_id
from app.core.response import api_error
from app.logging.logger import get_logger

logger = get_logger("app.auth.decorators")


def login_required(f: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator protecting API routes from unauthenticated access.
    Validates session token from Authorization Bearer header, X-Session-ID header,
    or session cookie. Enforces active user checks and records audit logs.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        token = None

        # 1. Bearer Token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

        # 2. X-Session-ID Header
        if not token and "X-Session-ID" in request.headers:
            token = request.headers.get("X-Session-ID", "").strip()

        # 3. Cookie fallback
        if not token:
            token = request.cookies.get("session_id")

        corr_id = get_correlation_id()
        req_id = get_request_id()

        if not token:
            audit_logger.record(
                category=AuditCategory.AUTH,
                action="UNAUTHORIZED_ACCESS_ATTEMPT",
                actor="anonymous",
                correlation_id=corr_id,
                request_id=req_id,
                details={"path": request.path, "reason": "MISSING_SESSION_TOKEN"},
            )
            return api_error(
                error_code="UNAUTHORIZED",
                message="Authentication session token is required",
                status_code=401,
            )

        # Validate Session
        session = session_manager.validate_session(token)
        if not session:
            audit_logger.record(
                category=AuditCategory.AUTH,
                action="UNAUTHORIZED_ACCESS_ATTEMPT",
                actor="anonymous",
                correlation_id=corr_id,
                request_id=req_id,
                details={"path": request.path, "reason": "INVALID_OR_EXPIRED_SESSION"},
            )
            return api_error(
                error_code="SESSION_EXPIRED",
                message="Session has expired or is invalid. Please log in again.",
                status_code=401,
            )

        # Fetch and verify active user
        user = UserRepository().get_by_id(session.user_id)
        if not user or not user.is_active:
            audit_logger.record(
                category=AuditCategory.AUTH,
                action="UNAUTHORIZED_ACCESS_ATTEMPT",
                actor=str(session.user_id),
                correlation_id=corr_id,
                request_id=req_id,
                details={"path": request.path, "reason": "USER_INACTIVE_OR_DELETED"},
            )
            return api_error(
                error_code="ACCOUNT_DISABLED",
                message="Your account is not active",
                status_code=403,
            )

        # Populate context and globals
        g.current_user = user
        g.current_session = session

        ctx = get_current_context()
        ctx.user_id = user.id
        ctx.session_id = session.session_id

        return f(*args, **kwargs)

    return decorated_function
