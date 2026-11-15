import os
from flask import Blueprint, g, request

from app.auth.decorators import login_required
from app.auth.services.session_manager import session_manager
from app.broker.adapters.kotak_adapter import kotak_adapter
from app.broker.adapters.kotak_order_adapter import kotak_order_adapter
from app.broker.cache.broker_cache import broker_cache
from app.broker.services.broker_client_sync import sync_shared_broker_client
from app.broker.services.broker_session_manager import broker_session_manager
from app.broker.services.broker_health_service import broker_health_service
from app.broker.services.websocket_supervisor import ws_supervisor
from app.broker.services.websocket_telemetry import ws_telemetry_tracker
from app.broker.services.broker_circuit_breaker import broker_circuit_breaker
from app.core.audit import audit_logger, AuditCategory, BROKER_LOGIN_SUCCESS, BROKER_LOGIN_FAILED
from app.core.exceptions import BrokerException, ValidationException
from app.core.request_context import get_correlation_id, get_request_id
from app.core.response import api_response, api_error

broker_bp = Blueprint("broker", __name__, url_prefix="/api/broker")

# Bind shared broker adapter singleton to health service
broker_health_service.set_adapter(kotak_adapter)


@broker_bp.route("/status", methods=["GET"])
def broker_status():
    """Retrieve current broker connection health and status."""
    health = broker_health_service.perform_health_check()
    return api_response(data=health)


@broker_bp.route("/client-state", methods=["GET"])
def broker_client_state():
    """Verify shared NeoAPI client wiring across broker, order execution, and streaming adapters."""
    return api_response(
        data={
            "broker_authenticated": kotak_adapter.is_connected(),
            "execution_adapter_connected": kotak_order_adapter.client is not None,
            "streaming_adapter_connected": ws_supervisor.adapter.client is not None,
            "is_mock": kotak_order_adapter._is_mock(),
        }
    )


@broker_bp.route("/session-status", methods=["GET"])
def broker_session_status():
    """Retrieve live broker session, UCC, profile, and expiry status for header & validation UI."""
    # Resolve optional operator session to inspect persisted BrokerSession
    token = request.cookies.get("session_id")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif "X-Session-ID" in request.headers:
            token = request.headers.get("X-Session-ID", "").strip()

    active_db_session = None
    if token:
        op_session = session_manager.validate_session(token)
        if op_session and not op_session.is_expired():
            db_sess = broker_session_manager.repo.get_active_session(user_id=op_session.user_id)
            if db_sess and not db_sess.is_expired():
                active_db_session = db_sess

    broker_connected = kotak_adapter.is_connected()
    meta = broker_cache.get_session_meta()
    last_sync = broker_cache.get_last_validation()

    authenticated = bool(broker_connected or active_db_session is not None)
    ucc = meta.get("ucc") if meta else None
    profile_loaded = bool(broker_connected and ucc)

    session_expiry = None
    if getattr(kotak_adapter, "_expiry_time", None) is not None:
        session_expiry = kotak_adapter._expiry_time.isoformat()
    elif active_db_session is not None and active_db_session.expiry_time is not None:
        session_expiry = active_db_session.expiry_time.isoformat()

    return api_response(
        data={
            "authenticated": authenticated,
            "profile_loaded": profile_loaded,
            "ucc": ucc,
            "session_expiry": session_expiry,
            "broker_connected": broker_connected,
            "last_broker_sync": last_sync,
            "client_name": meta.get("client_name") if meta else None,
            "stream_state": ws_supervisor.state.value,
        }
    )


@broker_bp.route("/capabilities", methods=["GET"])
def broker_capabilities():
    """Retrieve discovered broker capabilities."""
    capabilities = kotak_adapter.get_capabilities()
    return api_response(data=capabilities)


@broker_bp.route("/profile", methods=["GET"])
@login_required
def broker_profile():
    """Retrieve authenticated client profile and authorized market segment permissions."""
    profile_data = kotak_adapter.get_profile()
    return api_response(data=profile_data)


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
        sync_shared_broker_client(kotak_adapter.client)

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
        sync_shared_broker_client(kotak_adapter.client)
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

    # Gracefully stop streaming if active
    ws_supervisor.stop()

    broker_session_manager.destroy_session(
        user_id=user_id,
        adapter=kotak_adapter,
        actor=username,
    )
    sync_shared_broker_client(None)

    return api_response(
        data={"status": "DISCONNECTED"},
        message="Broker logged out successfully",
    )


@broker_bp.route("/stream/metrics", methods=["GET"])
def stream_metrics():
    """Retrieve explicit WebSocket telemetry metrics and circuit breaker state."""
    diagnostics = ws_supervisor.get_diagnostics()
    return api_response(data=diagnostics)


@broker_bp.route("/stream/start", methods=["POST"])
@login_required
def stream_start():
    """Manually initiate streaming supervisor for authenticated broker session."""
    user_id = g.current_user.id
    active_sess = broker_session_manager.repo.get_active_session(user_id=user_id)
    if not active_sess or active_sess.is_expired():
        return api_error(
            error_code="BROKER_SESSION_REQUIRED",
            message="Active broker session required to start streaming supervisor.",
            status_code=400,
        )

    token = broker_session_manager.encryption.decrypt(active_sess.session_token_encrypted)
    started = ws_supervisor.start(session_token=token)
    if started:
        return api_response(
            data={"state": ws_supervisor.state.value, "started": True},
            message="WebSocket streaming supervisor started",
        )
    return api_error(
        error_code="STREAM_START_FAILED",
        message="Failed to start streaming supervisor (check circuit breaker status).",
        status_code=503,
    )


@broker_bp.route("/stream/stop", methods=["POST"])
@login_required
def stream_stop():
    """Stop the WebSocket streaming supervisor."""
    ws_supervisor.stop()
    return api_response(
        data={"state": ws_supervisor.state.value, "stopped": True},
        message="WebSocket streaming supervisor stopped",
    )

