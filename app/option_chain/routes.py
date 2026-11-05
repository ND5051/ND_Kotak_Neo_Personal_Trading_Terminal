from flask import Blueprint
from app.core.response import api_response

option_chain_bp = Blueprint("option_chain", __name__, url_prefix="/api/option-chain")


@option_chain_bp.route("/status", methods=["GET"])
def option_chain_status():
    """Placeholder Option Chain endpoint."""
    return api_response(data={"expiries": [], "chain": [], "status": "skeleton_phase_1"})

