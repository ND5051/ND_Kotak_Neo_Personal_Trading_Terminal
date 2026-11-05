from flask import Blueprint, g, request

from app.auth.decorators import login_required
from app.auth.services.auth_service import auth_service
from app.auth.services.session_manager import session_manager
from app.auth.repositories.user_repository import UserRepository
from app.core.response import api_response, api_error
from app.core.exceptions import ValidationException

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user account."""
    payload = request.get_json(silent=True) or {}
    username = payload.get("username")
    email = payload.get("email")
    password = payload.get("password")

    if not username or not email or not password:
        return api_error(
            error_code="VALIDATION_ERROR",
            message="username, email, and password are required fields",
            status_code=400,
        )

    try:
        user = auth_service.register_user(
            username=username,
            email=email,
            password=password,
        )
        return api_response(
            data={"user": user.to_dict()},
            message="User registered successfully",
            status_code=201,
        )
    except ValidationException as e:
        return api_error(
            error_code=e.error_code,
            message=e.message,
            status_code=e.status_code,
        )


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate credentials and issue a session token."""
    payload = request.get_json(silent=True) or {}
    username_or_email = payload.get("username") or payload.get("email")
    password = payload.get("password")

    if not username_or_email or not password:
        return api_error(
            error_code="VALIDATION_ERROR",
            message="username/email and password are required",
            status_code=400,
        )

    try:
        user, session = auth_service.authenticate_user(
            username_or_email=username_or_email,
            password=password,
        )
        response, code = api_response(
            data={
                "user": user.to_dict(),
                "session": session.to_dict(),
                "token": session.session_id,
            },
            message="Authentication successful",
            status_code=200,
        )
        # Set session cookie
        response.set_cookie(
            "session_id",
            session.session_id,
            httponly=True,
            samesite="Strict",
        )
        return response, code
    except ValidationException as e:
        return api_error(
            error_code=e.error_code,
            message=e.message,
            status_code=e.status_code,
        )


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Terminate the active session."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "X-Session-ID" in request.headers:
        token = request.headers.get("X-Session-ID", "").strip()
    else:
        token = request.cookies.get("session_id")

    if token:
        auth_service.logout_user(token)

    response, code = api_response(
        data={"status": "logged_out"},
        message="Session terminated successfully",
    )
    response.delete_cookie("session_id")
    return response, code


@auth_bp.route("/status", methods=["GET"])
def auth_status():
    """Inspect current authentication state without failing if unauthenticated."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "X-Session-ID" in request.headers:
        token = request.headers.get("X-Session-ID", "").strip()
    else:
        token = request.cookies.get("session_id")

    if not token:
        return api_response(data={"authenticated": False, "user": None})

    session = session_manager.validate_session(token)
    if not session or session.is_expired():
        return api_response(data={"authenticated": False, "user": None})

    user = UserRepository().get_by_id(session.user_id)
    if not user or not user.is_active:
        return api_response(data={"authenticated": False, "user": None})

    return api_response(
        data={
            "authenticated": True,
            "user": user.to_dict(),
            "session": session.to_dict(),
        }
    )


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    """Protected profile endpoint verifying @login_required decorator."""
    return api_response(
        data={
            "user": g.current_user.to_dict(),
            "session": g.current_session.to_dict(),
        }
    )
