import time
import uuid
from flask import Flask, g, request, Response

from app.core.request_context import RequestContext, set_current_context, get_current_context
from app.logging.logger import get_logger

logger = get_logger("app.middleware.request_context")


class RequestContextMiddleware:
    """
    Middleware framework responsible for request tracing, correlation ID injection,
    security header enforcement, and execution timing logs.
    """

    @classmethod
    def init_app(cls, app: Flask) -> None:
        """Register before_request and after_request hooks on Flask app."""

        @app.before_request
        def before_request():
            req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
            corr_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

            # Attempt to extract session token from Authorization or X-Session-ID header
            auth_header = request.headers.get("Authorization", "")
            session_id = None
            if auth_header.startswith("Bearer "):
                session_id = auth_header[7:].strip()
            elif "X-Session-ID" in request.headers:
                session_id = request.headers.get("X-Session-ID")

            ctx = RequestContext(
                request_id=req_id,
                correlation_id=corr_id,
                session_id=session_id,
            )
            set_current_context(ctx)
            g.start_time = time.time()

        @app.after_request
        def after_request(response: Response) -> Response:
            ctx = get_current_context()
            duration_ms = round((time.time() - getattr(g, "start_time", time.time())) * 1000, 2)

            # Security Headers (Phase 2 Requirement)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            # Correlation Headers
            response.headers["X-Request-ID"] = ctx.request_id
            response.headers["X-Correlation-ID"] = ctx.correlation_id

            # Skip logging noise for static assets
            if not request.path.startswith("/static"):
                logger.info(
                    f"{request.method} {request.path} {response.status_code} ({duration_ms}ms)",
                    event="HTTP_REQUEST",
                    request_id=ctx.request_id,
                    correlation_id=ctx.correlation_id,
                    user_id=ctx.user_id,
                    method=request.method,
                    path=request.path,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )

            return response


def register_request_logging(app: Flask) -> None:
    """Convenience bootstrap for middleware."""
    RequestContextMiddleware.init_app(app)
