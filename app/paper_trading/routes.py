from flask import Blueprint
from app.core.response import api_response
from app.core.feature_flags import feature_flags

paper_trading_bp = Blueprint("paper_trading", __name__, url_prefix="/api/paper-trading")


@paper_trading_bp.route("/status", methods=["GET"])
def paper_status():
    """Placeholder Paper Trading endpoint (enabled check)."""
    return api_response(
        data={
            "enabled": feature_flags.is_enabled("PAPER_TRADING"),
            "status": "skeleton_phase_1",
        }
    )

