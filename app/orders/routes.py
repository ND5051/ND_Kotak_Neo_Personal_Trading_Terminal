"""
Orders REST Blueprint & Controller.
Phase 7: Order Domain Foundation.
Provides read-only order book queries, trade execution lookups, and pre-flight dry-run validation.
Execution routes (place, modify, cancel) are strictly prohibited.
"""

import uuid
from flask import Blueprint, g, request

from app.auth.decorators import login_required
from app.core.response import api_error, api_response
from app.logging.logger import get_logger
from app.orders.models.order import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
    Validity,
)
from app.orders.repositories.order_repository import order_repository
from app.orders.services.order_risk_service import order_risk_service
from app.orders.services.order_validation_service import order_validation_service

logger = get_logger("app.orders.routes")

orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")


@orders_bp.route("/status", methods=["GET"])
def orders_status():
    """Retrieve order domain module operational status."""
    return api_response(
        data={
            "status": "active_phase_7",
            "module": "order_domain_foundation",
            "execution_enabled": False,
            "supported_order_types": [e.value for e in OrderType],
            "supported_product_types": [e.value for e in ProductType],
            "supported_order_sides": [e.value for e in OrderSide],
        }
    )


@orders_bp.route("/validate", methods=["POST"])
@login_required
def validate_order():
    """
    Dry-run order validation and pre-trade risk evaluation endpoint.
    Strictly performs pre-flight checks without submitting, placing, or routing orders.
    """
    payload = request.get_json() or {}
    user_id = getattr(g, "user_id", 1)

    # Parse order parameters
    try:
        side_val = OrderSide(payload.get("side", "BUY").upper())
    except ValueError:
        return api_error(message=f"Invalid side '{payload.get('side')}'. Must be BUY or SELL.", status_code=400)

    try:
        type_val = OrderType(payload.get("order_type", "LIMIT").upper())
    except ValueError:
        return api_error(message=f"Invalid order_type '{payload.get('order_type')}'.", status_code=400)

    try:
        prod_val = ProductType(payload.get("product_type", "MIS").upper())
    except ValueError:
        return api_error(message=f"Invalid product_type '{payload.get('product_type')}'.", status_code=400)

    try:
        val_val = Validity(payload.get("validity", "DAY").upper())
    except ValueError:
        val_val = Validity.DAY

    token = str(payload.get("instrument_token", "")).strip()
    symbol = str(payload.get("trading_symbol", "")).strip()
    segment = str(payload.get("exchange_segment", "nse_cm")).strip().lower()

    try:
        quantity = int(payload.get("quantity", 0))
    except (ValueError, TypeError):
        return api_error(message="Quantity must be a valid integer.", status_code=400)

    try:
        price = float(payload.get("price", 0.0))
    except (ValueError, TypeError):
        price = 0.0

    try:
        trigger_price = float(payload.get("trigger_price", 0.0))
    except (ValueError, TypeError):
        trigger_price = 0.0

    client_order_id = str(payload.get("client_order_id") or uuid.uuid4())

    order = Order(
        client_order_id=client_order_id,
        user_id=user_id,
        instrument_token=token,
        exchange_segment=segment,
        trading_symbol=symbol,
        side=side_val,
        order_type=type_val,
        product_type=prod_val,
        validity=val_val,
        quantity=quantity,
        price=price,
        trigger_price=trigger_price,
    )

    # 1. Structural Validation
    syntax_valid, validation_errors = order_validation_service.validate_order(order)

    # 2. Market Protection Buffer Calculation (if applicable)
    buffered_price = price
    if type_val == OrderType.MARKET and price > 0:
        buffered_price = order_validation_service.calculate_market_protection(
            ref_price=price,
            side=side_val,
            mp_percent=2.0,
            tick_size=0.0025 if segment == "cde_fo" else 0.05,
        )

    # 3. Pre-Trade Risk Evaluation
    avail_cash_override = payload.get("available_cash")
    if avail_cash_override is not None:
        try:
            avail_cash_override = float(avail_cash_override)
        except (ValueError, TypeError):
            avail_cash_override = None

    risk_passed, risk_metadata = order_risk_service.evaluate_risk(
        order, available_cash=avail_cash_override
    )

    overall_valid = syntax_valid and risk_passed

    return api_response(
        data={
            "valid": overall_valid,
            "syntax_valid": syntax_valid,
            "risk_approved": risk_passed,
            "client_order_id": client_order_id,
            "order": order.to_dict(),
            "buffered_limit_price": buffered_price,
            "estimated_margin_required": risk_metadata.get("estimated_margin_required", 0.0),
            "available_cash": risk_metadata.get("available_cash", 0.0),
            "validation_errors": validation_errors,
            "risk_violations": risk_metadata.get("violations", []),
        }
    )


@orders_bp.route("", methods=["GET"])
@login_required
def get_orders():
    """
    Retrieve filterable order book for the authenticated user.
    Query parameters:
      status: 'open', 'completed', 'rejected', 'all' (default: all)
      symbol: substring search on trading_symbol
      segment: exchange segment filter
      limit: pagination limit (default: 50)
      offset: pagination offset (default: 0)
    """
    user_id = getattr(g, "user_id", 1)
    status_filter = request.args.get("status", "all").strip()
    symbol_filter = request.args.get("symbol")
    segment_filter = request.args.get("segment")

    try:
        limit = min(100, max(1, int(request.args.get("limit", 50))))
        offset = max(0, int(request.args.get("offset", 0)))
    except (ValueError, TypeError):
        limit = 50
        offset = 0

    orders = order_repository.find_orders(
        user_id=user_id,
        status=status_filter,
        symbol=symbol_filter,
        segment=segment_filter,
        limit=limit,
        offset=offset,
    )

    open_count = sum(1 for o in orders if o.is_open())
    terminal_count = len(orders) - open_count

    return api_response(
        data={
            "total_count": len(orders),
            "open_count": open_count,
            "terminal_count": terminal_count,
            "status_filter": status_filter,
            "orders": [o.to_dict() for o in orders],
        }
    )


@orders_bp.route("/<client_order_id>", methods=["GET"])
@login_required
def get_order_detail(client_order_id: str):
    """
    Fetch comprehensive order detail including immutable state transition history.
    """
    order = order_repository.find_by_client_order_id(client_order_id)
    if not order:
        return api_error(message=f"Order '{client_order_id}' not found.", status_code=404)

    events = order_repository.get_order_events(client_order_id)

    return api_response(
        data={
            "order": order.to_dict(),
            "timeline": [
                {
                    "from_status": ev.from_status,
                    "to_status": ev.to_status,
                    "reason": ev.reason,
                    "timestamp": ev.created_at.isoformat() if ev.created_at else None,
                }
                for ev in events
            ],
        }
    )


@orders_bp.route("/trades", methods=["GET"])
@login_required
def get_trades():
    """
    Retrieve executed trade fills (trade book).
    """
    user_id = getattr(g, "user_id", 1)
    trades = order_repository.get_trades(user_id=user_id, limit=100)
    return api_response(
        data={
            "count": len(trades),
            "trades": [t.to_dict() for t in trades],
        }
    )


@orders_bp.route("/stats", methods=["GET"])
@login_required
def get_order_stats():
    """
    Retrieve daily summary statistics for user orders.
    """
    user_id = getattr(g, "user_id", 1)
    orders = order_repository.find_orders(user_id=user_id, limit=500)

    total = len(orders)
    filled = sum(1 for o in orders if o.status == OrderStatus.FILLED)
    open_orders = sum(1 for o in orders if o.is_open())
    rejected = sum(1 for o in orders if o.status in (OrderStatus.REJECTED, OrderStatus.FAILED))
    cancelled = sum(1 for o in orders if o.status == OrderStatus.CANCELLED)

    return api_response(
        data={
            "total_orders": total,
            "open_orders": open_orders,
            "filled_orders": filled,
            "rejected_orders": rejected,
            "cancelled_orders": cancelled,
        }
    )


# Explicit Prohibitions: Return 405 Method Not Allowed if execution attempted
@orders_bp.route("/place", methods=["POST"])
def place_order_prohibited():
    """Explicitly prohibited in Phase 7."""
    return api_error(
        message="Order placement is strictly prohibited in Phase 7 (Order Domain Foundation). Use /api/orders/validate for dry-run verification.",
        error_code="EXECUTION_PROHIBITED_IN_PHASE_7",
        status_code=405,
    )
