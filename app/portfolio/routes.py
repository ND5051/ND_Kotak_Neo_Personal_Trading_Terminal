"""
Portfolio REST Blueprint & Controller.
Phase 6: Portfolio Foundation.
Provides REST endpoints for Demat holdings, Day/Net open positions, margin limits,
live MTM updates, and unified portfolio summary.
"""

from typing import Any, Dict, List
from flask import Blueprint, g, request

from app.auth.decorators import login_required
from app.core.response import api_error, api_response
from app.logging.logger import get_logger
from app.portfolio.models.position import PositionType
from app.portfolio.services.portfolio_service import portfolio_service

logger = get_logger("app.portfolio.routes")

portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/api/portfolio")


@portfolio_bp.route("/status", methods=["GET"])
def portfolio_status():
    """Retrieve portfolio module status."""
    return api_response(
        data={
            "status": "active_phase_6",
            "module": "portfolio_foundation",
        }
    )


@portfolio_bp.route("/summary", methods=["GET"])
@login_required
def get_portfolio_summary():
    """
    Retrieve unified executive portfolio summary combining holdings valuation,
    positions PnL, live MTM, and margin utilization.
    """
    summary = portfolio_service.get_summary()
    return api_response(data={"summary": summary.to_dict()})


@portfolio_bp.route("/holdings", methods=["GET"])
@login_required
def get_portfolio_holdings():
    """
    Retrieve Demat equity holdings with custody details, acquisition cost, and day PnL.
    """
    holdings = portfolio_service.get_holdings()
    return api_response(
        data={
            "count": len(holdings),
            "holdings": [h.to_dict() for h in holdings],
        }
    )


@portfolio_bp.route("/positions", methods=["GET"])
@login_required
def get_portfolio_positions():
    """
    Retrieve Day or Net positions with realized PnL and floating MTM.
    Query parameters:
      type: 'net' (default) or 'day'
      status: 'all' (default), 'open', or 'closed'
    """
    pos_type_str = request.args.get("type", "net").strip().upper()
    status_filter = request.args.get("status", "all").strip().lower()

    position_type = (
        PositionType.DAY if pos_type_str == "DAY" else PositionType.NET
    )

    positions = portfolio_service.get_positions(position_type=position_type)

    if status_filter == "open":
        filtered = [p for p in positions if p.is_open]
    elif status_filter == "closed":
        filtered = [p for p in positions if not p.is_open]
    else:
        filtered = positions

    open_count = sum(1 for p in filtered if p.is_open)
    closed_count = len(filtered) - open_count

    return api_response(
        data={
            "position_type": position_type.value,
            "status_filter": status_filter,
            "total_count": len(filtered),
            "open_count": open_count,
            "closed_count": closed_count,
            "positions": [p.to_dict() for p in filtered],
        }
    )


@portfolio_bp.route("/margins", methods=["GET"])
@login_required
def get_portfolio_margins():
    """
    Retrieve account cash balances, collateral limits, and live margin utilization %.
    """
    margins = portfolio_service.get_margins()
    return api_response(data={"margins": margins.to_dict()})


@portfolio_bp.route("/pnl", methods=["GET"])
@login_required
def get_portfolio_pnl():
    """
    Retrieve real-time profit and loss snapshot broken down by realized, open MTM, and holdings.
    """
    summary = portfolio_service.get_summary()
    return api_response(
        data={
            "realized_pnl": round(summary.realized_pnl, 2),
            "unrealized_mtm": round(summary.unrealized_mtm, 2),
            "total_trading_pnl": round(summary.total_trading_pnl, 2),
            "holdings_unrealized_pnl": round(summary.holdings_unrealized_pnl, 2),
            "holdings_day_pnl": round(summary.holdings_day_pnl, 2),
            "total_portfolio_pnl": round(summary.total_portfolio_pnl, 2),
            "source_timestamp": summary.source_timestamp,
            "retrieved_timestamp": summary.retrieved_timestamp,
            "updated_at": round(summary.updated_at, 3),
        }
    )


@portfolio_bp.route("/refresh", methods=["POST"])
@login_required
def force_refresh_portfolio():
    """
    Bypass TTL caches, force authoritative broker re-query, and publish update events.
    """
    summary = portfolio_service.force_refresh()
    return api_response(
        data={
            "refreshed": True,
            "summary": summary.to_dict(),
        }
    )
