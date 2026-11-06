"""
Option Chain Workbench REST Controller.
Phase 10: Option Chain Workbench.
Provides authenticated endpoints for underlying selection, contract expiries,
symmetrical strike matrix, PCR, favourite toggling, Watchlist addition, and Basket Builder handoff.
"""

from typing import Any, Dict
from flask import Blueprint, g, request

from app.core.exceptions import ApplicationException
from app.core.response import api_error, api_response
from app.market_watch.services.watchlist_service import watchlist_service
from app.auth.decorators import login_required
from app.option_chain.models.underlying import StrikeFilterPreset
from app.option_chain.services.option_chain_service import option_chain_service
from app.option_chain.services.strategy_builder_service import option_strategy_builder
from app.option_chain.services.underlying_service import underlying_service

option_chain_bp = Blueprint("option_chain", __name__, url_prefix="/api/option-chain")


# 1. Underlying Universe
@option_chain_bp.route("/underlyings", methods=["GET"])
@login_required
def list_underlyings():
    """Retrieve catalog of F&O underlyings with live Spot LTP and favourite flags."""
    user_id = getattr(g.current_user, "id", 1)
    underlyings = underlying_service.list_underlyings(user_id=user_id)
    return api_response(data={"underlyings": underlyings, "total": len(underlyings)})


# 2. Contract Expiries
@option_chain_bp.route("/expiries", methods=["GET"])
@login_required
def list_expiries():
    """Retrieve active contract expiries for an underlying symbol."""
    symbol = request.args.get("symbol", "NIFTY")
    try:
        expiries = option_chain_service.get_expiries(symbol)
        return api_response(
            data={
                "symbol": symbol.upper(),
                "expiries": [e.to_dict() for e in expiries],
                "total": len(expiries),
            }
        )
    except ApplicationException as e:
        return api_error(error_code=e.error_code, message=e.message, status_code=e.status_code)
    except Exception as e:
        return api_error(error_code="EXPIRIES_FETCH_FAILED", message=str(e), status_code=500)


# 3. Full Strike Matrix
@option_chain_bp.route("", methods=["GET"])
@login_required
def get_option_chain():
    """
    Retrieve symmetrical Call and Put strike matrix centered around dynamic ATM.
    Enforces strike filter presets (ATM_5, ATM_10, ATM_15, ATM_20).
    """
    symbol = request.args.get("symbol", "NIFTY")
    expiry = request.args.get("expiry")
    raw_preset = request.args.get("preset") or request.args.get("strike_count") or "ATM_10"
    preset = StrikeFilterPreset.from_value(raw_preset)

    try:
        snapshot = option_chain_service.get_option_chain(
            symbol=symbol,
            expiry=expiry,
            preset=preset,
        )
        return api_response(data=snapshot.to_dict())
    except ApplicationException as e:
        return api_error(error_code=e.error_code, message=e.message, status_code=e.status_code)
    except Exception as e:
        return api_error(error_code="OPTION_CHAIN_FETCH_FAILED", message=str(e), status_code=500)


# 4. Put-Call Ratio (PCR) Analytics
@option_chain_bp.route("/pcr", methods=["GET"])
@login_required
def get_pcr():
    """Retrieve lightweight aggregate PCR and Open Interest metrics."""
    symbol = request.args.get("symbol", "NIFTY")
    expiry = request.args.get("expiry")
    try:
        snapshot = option_chain_service.get_option_chain(symbol=symbol, expiry=expiry, preset="ATM_5")
        return api_response(
            data={
                "underlying_symbol": snapshot.underlying_symbol,
                "expiry_date": snapshot.expiry_date,
                "pcr_oi": snapshot.pcr_oi,
                "pcr_volume": snapshot.pcr_volume,
                "total_call_oi": snapshot.total_call_oi,
                "total_put_oi": snapshot.total_put_oi,
                "max_call_oi_strike": snapshot.max_call_oi_strike,
                "max_put_oi_strike": snapshot.max_put_oi_strike,
                "max_pain_strike": snapshot.max_pain_strike,
                "source_timestamp": snapshot.source_timestamp,
                "oi_source_timestamp": snapshot.oi_source_timestamp,
            }
        )
    except ApplicationException as e:
        return api_error(error_code=e.error_code, message=e.message, status_code=e.status_code)
    except Exception as e:
        return api_error(error_code="PCR_FETCH_FAILED", message=str(e), status_code=500)


# 5. Favourite Underlyings
@option_chain_bp.route("/favourites", methods=["GET", "POST"])
@login_required
def user_favourites():
    """Manage pinned favourite underlyings."""
    user_id = getattr(g.current_user, "id", 1)

    if request.method == "GET":
        favs = underlying_service.get_favourites(user_id=user_id)
        return api_response(data={"favourites": favs, "total": len(favs)})

    payload = request.get_json(silent=True) or {}
    symbol = payload.get("symbol")
    is_favourite = bool(payload.get("is_favourite", True))

    if not symbol:
        return api_error(error_code="INVALID_PAYLOAD", message="Symbol is required.", status_code=400)

    success = underlying_service.toggle_favourite(user_id=user_id, symbol=symbol, is_favourite=is_favourite)
    if not success:
        return api_error(error_code="UNDERLYING_NOT_FOUND", message=f"Symbol not found: {symbol}", status_code=404)

    return api_response(
        data={"symbol": symbol.upper(), "is_favourite": is_favourite},
        message=f"{symbol.upper()} favourite status updated",
    )


# 6. Bridge to Phase 9 Basket Builder
@option_chain_bp.route("/build-strategy", methods=["POST"])
@login_required
def build_strategy():
    """
    Template macro bridge converting selected strikes into Phase 9 compliant Basket payload.
    Supports BULL_CALL_SPREAD, BEAR_PUT_SPREAD, LONG_STRADDLE, SHORT_STRADDLE, IRON_CONDOR.
    """
    payload = request.get_json(silent=True) or {}
    strategy_type = payload.get("strategy_type", "BULL_CALL_SPREAD").upper()
    underlying = payload.get("underlying", "NIFTY").upper()
    expiry_token = payload.get("expiry_token", "26NOV")
    lot_size = int(payload.get("lot_size", 25))
    lots = int(payload.get("lots", 1))

    try:
        if strategy_type == "BULL_CALL_SPREAD":
            basket_payload = option_strategy_builder.build_bull_call_spread(
                underlying=underlying,
                expiry_token=expiry_token,
                buy_strike=float(payload.get("buy_strike", 24500)),
                sell_strike=float(payload.get("sell_strike", 24600)),
                lot_size=lot_size,
                lots=lots,
                buy_price=float(payload.get("buy_price", 100.0)),
                sell_price=float(payload.get("sell_price", 40.0)),
            )
        elif strategy_type == "BEAR_PUT_SPREAD":
            basket_payload = option_strategy_builder.build_bear_put_spread(
                underlying=underlying,
                expiry_token=expiry_token,
                buy_strike=float(payload.get("buy_strike", 24600)),
                sell_strike=float(payload.get("sell_strike", 24500)),
                lot_size=lot_size,
                lots=lots,
                buy_price=float(payload.get("buy_price", 100.0)),
                sell_price=float(payload.get("sell_price", 40.0)),
            )
        elif strategy_type in ("LONG_STRADDLE", "SHORT_STRADDLE"):
            basket_payload = option_strategy_builder.build_straddle(
                underlying=underlying,
                expiry_token=expiry_token,
                strike=float(payload.get("strike", 24500)),
                lot_size=lot_size,
                is_short=(strategy_type == "SHORT_STRADDLE"),
                lots=lots,
                call_price=float(payload.get("call_price", 100.0)),
                put_price=float(payload.get("put_price", 100.0)),
            )
        elif strategy_type == "IRON_CONDOR":
            basket_payload = option_strategy_builder.build_iron_condor(
                underlying=underlying,
                expiry_token=expiry_token,
                put_buy_strike=float(payload.get("put_buy_strike", 24100)),
                put_sell_strike=float(payload.get("put_sell_strike", 24300)),
                call_sell_strike=float(payload.get("call_sell_strike", 24700)),
                call_buy_strike=float(payload.get("call_buy_strike", 24900)),
                lot_size=lot_size,
                lots=lots,
                put_buy_price=float(payload.get("put_buy_price", 15.0)),
                put_sell_price=float(payload.get("put_sell_price", 50.0)),
                call_sell_price=float(payload.get("call_sell_price", 50.0)),
                call_buy_price=float(payload.get("call_buy_price", 15.0)),
            )
        else:
            return api_error(
                error_code="UNSUPPORTED_STRATEGY",
                message=f"Unsupported strategy template: {strategy_type}",
                status_code=400,
            )

        return api_response(data=basket_payload, message="Strategy template constructed successfully")
    except Exception as e:
        return api_error(error_code="STRATEGY_BUILD_FAILED", message=str(e), status_code=400)


# 7. Bridge to Phase 5 Watchlist
@option_chain_bp.route("/watchlist/add", methods=["POST"])
@login_required
def add_to_watchlist():
    """One-click addition of an option chain strike contract to a watchlist."""
    user_id = getattr(g.current_user, "id", 1)
    payload = request.get_json(silent=True) or {}
    watchlist_id = payload.get("watchlist_id")
    trading_symbol = payload.get("trading_symbol")
    segment = payload.get("exchange_segment", "nse_fo")
    token = payload.get("instrument_token", "")

    if not trading_symbol:
        return api_error(error_code="INVALID_PAYLOAD", message="trading_symbol is required.", status_code=400)

    try:
        # If watchlist_id not specified, find user default
        if not watchlist_id:
            wl = watchlist_service.get_user_watchlists(user_id=user_id)
            if wl:
                watchlist_id = wl[0].id
            else:
                default_wl = watchlist_service.create_watchlist(user_id=user_id, name="Default Options Watchlist")
                watchlist_id = default_wl.id

        item = watchlist_service.add_item(
            user_id=user_id,
            watchlist_id=watchlist_id,
            instrument_token=token,
            exchange_segment=segment,
            trading_symbol=trading_symbol,
        )
        return api_response(data=item.to_dict(), message=f"Added {trading_symbol} to watchlist.")
    except Exception as e:
        return api_error(error_code="WATCHLIST_ADD_FAILED", message=str(e), status_code=400)
