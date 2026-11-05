from flask import Blueprint, render_template
from app.core.response import api_response

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/", methods=["GET"])
def index():
    """Terminal root dashboard entry point."""
    return render_template("index.html")


@dashboard_bp.route("/api/system/health", methods=["GET"])
def system_health():
    """System health check endpoint."""
    return api_response(data={"status": "online", "phase": "phase_1_skeleton"})

