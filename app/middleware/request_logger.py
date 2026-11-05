import time
import uuid
from flask import Flask, g, request
from app.logging.logger import get_logger

logger = get_logger("app.middleware.request")


def register_request_logging(app: Flask) -> None:
    """Register request hooks to trace request execution times and correlation IDs."""

    @app.before_request
    def before_request():
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        g.start_time = time.time()

    @app.after_request
    def after_request(response):
        duration_ms = round((time.time() - getattr(g, "start_time", time.time())) * 1000, 2)
        response.headers["X-Request-ID"] = getattr(g, "request_id", "unknown")

        # Skip noisy static files from detailed audit logging
        if not request.path.startswith("/static"):
            logger.info(
                f"{request.method} {request.path} {response.status_code} ({duration_ms}ms)",
                event="HTTP_REQUEST",
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                request_id=getattr(g, "request_id", None),
            )
        return response

