import os
from flask import Blueprint, g, request

from app.auth.decorators import login_required
from app.broker.adapters.kotak_adapter import KotakBrokerAdapter
from app.broker.services.broker_session_manager import broker_session_manager
from app.broker.services.broker_health_service import broker_health_service
from app.core.audit import audit_logger, AuditCategory, BROKER_LOGIN_SUCCESS, BROKER_LOGIN_FAILED
from app.core.exceptions import BrokerException, ValidationException
from app.core.request_context import get_correlation_id, get_request_id
from app.core.response import api_response, api_error

broker_bp = Blueprint("broker", __name__, url_prefix="/api/broker")

# Shared adapter instance initialized for broker operations
kotak_adapter = KotakBrokerAdapter()
broker_health_service.set_adapter(kotak_adapter)


@broker_bp.route("/status", methods=["GET"])
def broker_status():
    """Retrieve current broker connection health and status."""
    health = broker_health_service.perform_health_check()
    return api_response(data=health)


@broker_bp.route("/capabilities", methods=["GET"])
def broker_capabilities():
    """Retrieve discovered broker capabilities."""
    capabilities = kotak_adapter.get_capabilities()
    return api_response(data=capabilities)


@broker_bp.route("/login", methods=["POST"])
@login_required
def broker_login():
    """
    Authenticate with Kotak Neo broker, encrypt tokens, and store active broker session.
    Accepts payload credentials or falls back to system environment variables.
    """
    payload = request.get_json(silent=True) or {}

    credentials = {
        "consumer_key": payload.get("consumer_key") or os.getenv("NEO_CONSUMER_KEY"),
        "consumer_secret": payload.get("consumer_secret") or os.getenv("NEO_CONSUMER_SECRET"),
        "mobile_number": payload.get("mobile_number") or os.getenv("NEO_MOBILE_NUMBER"),
        "ucc": payload.get("ucc") or os.getenv("NEO_UCC"),
        "mpin": payload.get("mpin") or os.getenv("NEO_MPIN"),
        "totp_secret": payload.get("totp_secret") or os.getenv("NEO_TOTP_SECRET"),
    }

    corr_id = get_correlation_id()
    req_id = get_request_id()
    user_id = g.current_user.id
    username = g.current_user.username

    try:
        session_info = kotak_adapter.login(credentials)

        broker_session = broker_session_manager.create_session(
            user_id=user_id,
            session_token=session_info["session_token"],
            refresh_token=session_info.get("refresh_token"),
            expiry_time=session_info.get("expiry_time"),
            broker_name=session_info.get("broker_name", "KOTAK_NEO"),
            actor=username,
        )

        audit_logger.record(
            category=AuditCategory.BROKER,
            action=BROKER_LOGIN_SUCCESS,
            actor=username,
            correlation_id=corr_id,
            request_id=req_id,
            details={"broker": "KOTAK_NEO", "broker_session_id": broker_session.id},
        )

        return api_response(
            data={
                "broker_session": broker_session.to_dict(),
                "status": "AUTHENTICATED",
            },
            message="Broker login successful",
            status_code=200,
        )

    except (ValidationException, BrokerException) as e:
        audit_logger.record(
            category=AuditCategory.BROKER,
            action=BROKER_LOGIN_FAILED,
            actor=username,
            correlation_id=corr_id,
            request_id=req_id,
            details={"broker": "KOTAK_NEO", "error": str(e)},
        )
        return api_error(
            error_code=e.error_code,
            message=e.message,
            status_code=e.status_code,
        )


@broker_bp.route("/restore", methods=["POST"])
@login_required
def broker_restore():
    """Attempt restoration of active broker session without re-prompting credentials."""
    user_id = g.current_user.id
    username = g.current_user.username

    restored = broker_session_manager.restore_session(
        user_id=user_id,
        adapter=kotak_adapter,
        actor=username,
    )

    if restored:
        return api_response(
            data={"restored": True, "status": "AUTHENTICATED"},
            message="Broker session restored successfully",
        )
    return api_error(
        error_code="BROKER_RESTORE_FAILED",
        message="No valid or active broker session available for restoration. Login required.",
        status_code=400,
    )


@broker_bp.route("/logout", methods=["POST"])
@login_required
def broker_logout():
    """Terminate the active broker session and invalidate stored tokens."""
    user_id = g.current_user.id
    username = g.current_user.username

    broker_session_manager.destroy_session(
        user_id=user_id,
        adapter=kotak_adapter,
        actor=username,
    )

    return api_response(
        data={"status": "DISCONNECTED"},
        message="Broker logged out successfully",
    )
