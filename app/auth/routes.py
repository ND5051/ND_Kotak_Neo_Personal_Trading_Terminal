from flask import Blueprint
from app.core.response import api_response

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/status", methods=["GET"])
def auth_status():
    """Placeholder authentication status endpoint (No trading logic in Phase 1)."""
    return api_response(data={"authenticated": False, "status": "skeleton_phase_1"})

