from flask import Blueprint
from app.core.response import api_response

holdings_bp = Blueprint("holdings", __name__, url_prefix="/api/holdings")


@holdings_bp.route("/status", methods=["GET"])
def holdings_status():
    """Placeholder Holdings endpoint."""
    return api_response(data={"holdings": [], "status": "skeleton_phase_1"})

