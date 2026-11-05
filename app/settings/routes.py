from flask import Blueprint
from app.core.response import api_response
from app.core.feature_flags import feature_flags

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")


@settings_bp.route("/feature-flags", methods=["GET"])
def get_flags():
    """Retrieve all current feature flag states."""
    return api_response(data=feature_flags.get_all())

