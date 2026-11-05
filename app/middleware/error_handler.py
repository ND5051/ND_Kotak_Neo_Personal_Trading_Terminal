from flask import Flask, Request, request
from werkzeug.exceptions import HTTPException

from app.core.exceptions import ApplicationException
from app.core.response import api_error
from app.logging.logger import get_logger

logger = get_logger("app.middleware.error_handler")


def register_error_handlers(app: Flask) -> None:
    """Register global error handlers for standard HTTP and application exceptions."""

    @app.errorhandler(ApplicationException)
    def handle_application_exception(error: ApplicationException):
        logger.warning(
            f"Handled application error: {error.message}",
            event="APPLICATION_EXCEPTION",
            error_code=error.error_code,
            status_code=error.status_code,
            path=request.path,
            details=error.details,
        )
        return api_error(
            error_code=error.error_code,
            message=error.message,
            details=error.details,
            status_code=error.status_code,
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        logger.warning(
            f"HTTP error occurred: {error.description}",
            event="HTTP_EXCEPTION",
            status_code=error.code or 400,
            path=request.path,
        )
        return api_error(
            error_code=f"HTTP_{error.code}",
            message=error.description or "An HTTP error occurred",
            status_code=error.code or 400,
        )

    @app.errorhandler(Exception)
    def handle_unhandled_exception(error: Exception):
        logger.critical(
            f"Unhandled system error: {str(error)}",
            event="UNHANDLED_EXCEPTION",
            exc_info=True,
            path=request.path,
        )
        return api_error(
            error_code="INTERNAL_SERVER_ERROR",
            message="An unexpected server error occurred. Please contact the administrator.",
            status_code=500,
        )

