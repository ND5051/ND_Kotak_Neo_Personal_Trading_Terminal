from flask import Blueprint
from app.core.response import api_response

orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")


@orders_bp.route("/status", methods=["GET"])
def orders_status():
    """Placeholder Orders endpoint."""
    return api_response(data={"orders": [], "status": "skeleton_phase_1"})

