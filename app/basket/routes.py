from flask import Blueprint
from app.core.response import api_response

basket_bp = Blueprint("basket", __name__, url_prefix="/api/basket")


@basket_bp.route("/status", methods=["GET"])
def basket_status():
    """Placeholder Basket Orders endpoint."""
    return api_response(data={"baskets": [], "status": "skeleton_phase_1"})

