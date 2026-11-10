from flask import Blueprint, render_template, request
from app.auth.repositories.user_repository import UserRepository
from app.auth.services.session_manager import session_manager
from app.core.response import api_response
from app.orders.models.execution_mode import execution_mode_manager

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/", methods=["GET"])
def index():
    """Terminal root dashboard entry point."""
    return render_template("index.html")


@dashboard_bp.route("/terminal", methods=["GET"])
def terminal():
    """Professional Trading Terminal UI (Phase 11A Shell)."""
    current_mode = execution_mode_manager.get_mode().value

    # Check session authentication state
    token = request.cookies.get("session_id")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif "X-Session-ID" in request.headers:
            token = request.headers.get("X-Session-ID", "").strip()

    authenticated = False
    operator_user = None

    if token:
        session = session_manager.validate_session(token)
        if session and not session.is_expired():
            user = UserRepository().get_by_id(session.user_id)
            if user and user.is_active:
                authenticated = True
                operator_user = user.to_dict()

    return render_template(
        "terminal.html",
        execution_mode=current_mode,
        authenticated=authenticated,
        operator=operator_user,
    )


@dashboard_bp.route("/api/system/health", methods=["GET"])
def system_health():
    """System health check endpoint."""
    return api_response(data={"status": "online", "phase": "phase_1_skeleton"})

