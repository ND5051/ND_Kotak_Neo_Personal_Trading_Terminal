from flask import Blueprint
from app.core.response import api_response

positions_bp = Blueprint("positions", __name__, url_prefix="/api/positions")


@positions_bp.route("/status", methods=["GET"])
def positions_status():
    """Placeholder Positions endpoint."""
    return api_response(data={"positions": [], "status": "skeleton_phase_1"})

