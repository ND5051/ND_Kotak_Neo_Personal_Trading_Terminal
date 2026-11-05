from typing import Any, Dict, Optional
from flask import jsonify, Response


def api_response(
    data: Any = None,
    message: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
) -> tuple[Response, int]:
    """Generate a consistent, structured success API response."""
    payload: Dict[str, Any] = {
        "status": "success",
        "data": data if data is not None else {},
    }
    if message:
        payload["message"] = message
    if meta:
        payload["meta"] = meta
    return jsonify(payload), status_code


def api_error(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    status_code: int = 400,
) -> tuple[Response, int]:
    """Generate a consistent, structured error API response."""
    payload: Dict[str, Any] = {
        "status": "error",
        "error_code": error_code,
        "message": message,
        "details": details or {},
    }
    return jsonify(payload), status_code

