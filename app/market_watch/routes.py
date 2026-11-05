from flask import Blueprint
from app.core.response import api_response

market_watch_bp = Blueprint("market_watch", __name__, url_prefix="/api/market-watch")


@market_watch_bp.route("/status", methods=["GET"])
def market_watch_status():
    """Placeholder Market Watch endpoint."""
    return api_response(data={"symbols": [], "status": "skeleton_phase_1"})

