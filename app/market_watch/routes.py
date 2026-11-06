"""
Market Watch REST Blueprint & Controller.
Phase 5: Market Watch Foundation.
Provides REST endpoints for scrip search, multi-watchlist CRUD, pinned item management,
and real-time touchline quote snapshots.
"""

from typing import Any, Dict, List, Tuple
from flask import Blueprint, g, request

from app.auth.decorators import login_required
from app.core.exceptions import ValidationException
from app.core.response import api_error, api_response
from app.logging.logger import get_logger
from app.market_watch.services.instrument_service import instrument_service
from app.market_watch.services.price_engine import price_engine
from app.market_watch.services.watchlist_service import (
    WatchlistQuotaExceededException,
    watchlist_service,
)

logger = get_logger("app.market_watch.routes")

market_watch_bp = Blueprint("market_watch", __name__, url_prefix="/api/market-watch")


@market_watch_bp.route("/status", methods=["GET"])
def market_watch_status():
    """Retrieve market watch operational status and total indexed instruments."""
    return api_response(
        data={
            "status": "active_phase_5",
            "indexed_instruments_count": instrument_service.repository.count(),
        }
    )


@market_watch_bp.route("/search", methods=["GET"])
def search_instruments():
    """
    Search Scrip Master instruments by symbol, name, or token.
    Query parameters:
      q: Search query string (min 2 chars)
      segment: Exchange segment filter (e.g. nse_cm, bse_cm, nse_fo)
      limit: Maximum results (default 20, max 50)
    """
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return api_error(
            error_code="INVALID_QUERY",
            message="Search query 'q' must be at least 2 characters",
            status_code=400,
        )

    segment = request.args.get("segment")
    try:
        limit = min(50, max(1, int(request.args.get("limit", 20))))
    except ValueError:
        limit = 20

    results = instrument_service.search_instruments(
        query=query, segment=segment, limit=limit
    )
    return api_response(data={"count": len(results), "instruments": results})


@market_watch_bp.route("/watchlists", methods=["GET"])
@login_required
def get_user_watchlists():
    """Retrieve all watchlists for authenticated user with real-time quotes attached."""
    user_id = g.current_user.id
    watchlists_data = watchlist_service.get_watchlists_with_quotes(user_id)
    return api_response(data={"watchlists": watchlists_data})


@market_watch_bp.route("/watchlists", methods=["POST"])
@login_required
def create_watchlist():
    """Create a new custom user watchlist."""
    payload = request.get_json(silent=True) or {}
    name = payload.get("name", "").strip()
    is_default = bool(payload.get("is_default", False))

    if not name:
        return api_error(
            error_code="VALIDATION_ERROR",
            message="Watchlist 'name' is required",
            status_code=400,
        )

    try:
        user_id = g.current_user.id
        created = watchlist_service.create_watchlist(
            user_id=user_id, name=name, is_default=is_default
        )
        return api_response(
            data={"watchlist": created.to_dict(include_items=True)},
            status_code=201,
        )
    except (ValidationException, WatchlistQuotaExceededException) as e:
        return api_error(
            error_code=e.error_code, message=str(e), status_code=e.status_code
        )


@market_watch_bp.route("/watchlists/<int:watchlist_id>", methods=["DELETE"])
@login_required
def delete_watchlist(watchlist_id: int):
    """Delete a user watchlist with cascading cleanup and wire unsubscription."""
    user_id = g.current_user.id
    try:
        watchlist_service.delete_watchlist(user_id=user_id, watchlist_id=watchlist_id)
        return api_response(
            data={"deleted": True, "watchlist_id": watchlist_id}
        )
    except ValidationException as e:
        return api_error(
            error_code=e.error_code, message=str(e), status_code=e.status_code
        )


@market_watch_bp.route("/watchlists/<int:watchlist_id>/items", methods=["POST"])
@login_required
def add_watchlist_item(watchlist_id: int):
    """Add an instrument to a watchlist, triggering dynamic streaming subscription."""
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("instrument_token", "")).strip()
    segment = str(payload.get("exchange_segment", "")).strip().lower()
    symbol = str(payload.get("trading_symbol", "")).strip()
    display_name = payload.get("display_name")

    if not token or not segment or not symbol:
        return api_error(
            error_code="VALIDATION_ERROR",
            message="Fields 'instrument_token', 'exchange_segment', and 'trading_symbol' are required",
            status_code=400,
        )

    user_id = g.current_user.id
    try:
        item = watchlist_service.add_item(
            user_id=user_id,
            watchlist_id=watchlist_id,
            instrument_token=token,
            exchange_segment=segment,
            trading_symbol=symbol,
            display_name=display_name,
        )
        return api_response(data={"item": item.to_dict()}, status_code=201)
    except (ValidationException, WatchlistQuotaExceededException) as e:
        return api_error(
            error_code=e.error_code, message=str(e), status_code=e.status_code
        )


@market_watch_bp.route(
    "/watchlists/<int:watchlist_id>/items/<int:item_id>", methods=["DELETE"]
)
@login_required
def remove_watchlist_item(watchlist_id: int, item_id: int):
    """Remove an instrument from a watchlist and decrement wire subscription."""
    user_id = g.current_user.id
    try:
        watchlist_service.remove_item(
            user_id=user_id, watchlist_id=watchlist_id, item_id=item_id
        )
        return api_response(
            data={"removed": True, "watchlist_id": watchlist_id, "item_id": item_id}
        )
    except ValidationException as e:
        return api_error(
            error_code=e.error_code, message=str(e), status_code=e.status_code
        )


@market_watch_bp.route("/watchlists/<int:watchlist_id>/reorder", methods=["PUT"])
@login_required
def reorder_watchlist_items(watchlist_id: int):
    """Reorder items within a watchlist."""
    payload = request.get_json(silent=True) or {}
    item_ids = payload.get("item_ids", [])
    if not isinstance(item_ids, list):
        return api_error(
            error_code="VALIDATION_ERROR",
            message="'item_ids' must be a list of integer IDs",
            status_code=400,
        )

    user_id = g.current_user.id
    try:
        watchlist_service.reorder_items(
            user_id=user_id, watchlist_id=watchlist_id, ordered_item_ids=item_ids
        )
        return api_response(data={"reordered": True, "watchlist_id": watchlist_id})
    except ValidationException as e:
        return api_error(
            error_code=e.error_code, message=str(e), status_code=e.status_code
        )


@market_watch_bp.route("/quotes", methods=["GET"])
def get_quotes_batch():
    """
    Fetch live touchline quote snapshots.
    Query param:
      tokens: Comma-separated list of 'segment:token', e.g. 'nse_cm:26000,nse_cm:11536'
    """
    raw_tokens = request.args.get("tokens", "").strip()
    if not raw_tokens:
        return api_error(
            error_code="MISSING_TOKENS",
            message="Query parameter 'tokens' is required (e.g. ?tokens=nse_cm:26000)",
            status_code=400,
        )

    parsed_tokens: List[Tuple[str, str]] = []
    for pair in raw_tokens.split(","):
        parts = pair.strip().split(":")
        if len(parts) == 2:
            seg, tok = parts[0].strip().lower(), parts[1].strip()
            parsed_tokens.append((tok, seg))

    quotes = price_engine.get_quotes_batch(parsed_tokens)
    return api_response(data={"quotes": quotes})


@market_watch_bp.route("/tick/simulate", methods=["POST"])
def simulate_tick():
    """Simulation helper endpoint for tests to inject real-time ticks into PriceEngine."""
    payload = request.get_json(silent=True) or {}
    quote = price_engine.ingest_tick(payload)
    if not quote:
        return api_error(
            error_code="INVALID_TICK",
            message="Failed to parse tick payload",
            status_code=400,
        )
    return api_response(data={"quote": quote.to_dict()})
