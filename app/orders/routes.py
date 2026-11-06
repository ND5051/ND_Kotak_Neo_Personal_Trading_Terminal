"""
Orders REST Blueprint & Controller.
Phase 8: Order Execution Foundation.
Provides full lifecycle live & paper order execution, modification, cancellation,
dry-run pre-flight validation, and status tracking governed by ExecutionMode.
"""

from typing import Any, Dict
import uuid
from flask import Blueprint, g, request

from app.auth.decorators import login_required
from app.core.exceptions import (
    BrokerCircuitBreakerOpenException,
    BrokerException,
    ExecutionModeException,
    OrderRiskException,
    OrderValidationException,
)
from app.core.response import api_error, api_response
from app.logging.logger import get_logger
from app.orders.models.execution_mode import (
    execution_mode_manager,
    ExecutionMode,
)
from app.orders.models.order import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
    Validity,
)
from app.orders.repositories.order_repository import order_repository
from app.orders.services.order_execution_service import order_execution_service
from app.orders.services.order_poller_service import order_poller_service
from app.orders.services.order_risk_service import order_risk_service
from app.orders.services.order_validation_service import order_validation_service

logger = get_logger("app.orders.routes")

orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")


# 1. Operational Status
@orders_bp.route("/status", methods=["GET"])
def orders_status():
    """Retrieve order domain and execution engine operational status."""
    current_mode = execution_mode_manager.get_mode()
    return api_response(
        data={
            "status": "operational",
            "module": "order_execution_foundation",
            "phase": 8,
            "execution_mode": current_mode.value,
            "execution_enabled": current_mode != ExecutionMode.DISABLED,
            "supported_modes": [e.value for e in ExecutionMode],
            "supported_order_types": [e.value for e in OrderType],
            "supported_product_types": [e.value for e in ProductType],
            "supported_order_sides": [e.value for e in OrderSide],
        }
    )


# 2. Execution Mode Configuration
@orders_bp.route("/mode", methods=["POST"])
@login_required
def set_execution_mode():
    """
    Configure global order execution mode (DISABLED, PAPER, LIVE).
    Requires authenticated operator session.
    """
    payload = request.get_json() or {}
    new_mode_str = payload.get("mode")
    if not new_mode_str:
        return api_error(error_code="INVALID_MODE", message="Missing 'mode' parameter. Must be DISABLED, PAPER, or LIVE.", status_code=400)

    user_id = getattr(g, "user_id", 1)
    try:
        updated_mode = execution_mode_manager.set_mode(new_mode_str, actor=f"user_{user_id}")
        return api_response(
            data={
                "success": True,
                "execution_mode": updated_mode.value,
                "message": f"Execution mode updated to {updated_mode.value}",
            }
        )
    except ExecutionModeException as e:
        return api_error(error_code="INVALID_MODE", message=str(e), status_code=400)


# 3. Place Order (Execution Pipeline)
@orders_bp.route("/place", methods=["POST"])
@login_required
def place_order():
    """
    Submit an order for execution (PAPER or LIVE).
    Refused if execution mode is DISABLED.
    """
    payload = request.get_json() or {}
    user_id = getattr(g, "user_id", 1)

    try:
        avail_cash_override = payload.get("available_cash")
        if avail_cash_override is not None:
            avail_cash_override = float(avail_cash_override)

        result = order_execution_service.place_order(
            order_params=payload,
            user_id=user_id,
            available_cash=avail_cash_override,
        )
        return api_response(data=result, status_code=201)

    except ExecutionModeException as e:
        logger.warning(f"Order placement refused due to execution mode: {str(e)}")
        return api_error(
            message=str(e),
            error_code="EXECUTION_MODE_DISABLED",
            status_code=403,
        )
    except (OrderValidationException, OrderRiskException) as e:
        return api_error(
            message=str(e),
            error_code=getattr(e, "error_code", "VALIDATION_ERROR"),
            status_code=400,
            details=getattr(e, "details", {}),
        )
    except BrokerCircuitBreakerOpenException as e:
        return api_error(
            message=str(e),
            error_code="CIRCUIT_BREAKER_OPEN",
            status_code=503,
        )
    except BrokerException as e:
        return api_error(
            message=str(e),
            error_code="BROKER_ERROR",
            status_code=502,
        )
    except Exception as e:
        logger.error(f"Unexpected error in place_order: {str(e)}", exc_info=True)
        return api_error(error_code="EXECUTION_ERROR", message=f"Internal execution error: {str(e)}", status_code=500)


# 4. Modify Order
@orders_bp.route("/<client_order_id>/modify", methods=["PUT"])
@login_required
def modify_order(client_order_id: str):
    """Modify price, quantity, or trigger price of an open order."""
    payload = request.get_json() or {}
    user_id = getattr(g, "user_id", 1)

    try:
        result = order_execution_service.modify_order(
            client_order_id=client_order_id,
            modifications=payload,
            actor=f"user_{user_id}",
        )
        return api_response(data=result)
    except ExecutionModeException as e:
        return api_error(error_code="EXECUTION_MODE_DISABLED", message=str(e), status_code=403)
    except OrderValidationException as e:
        return api_error(error_code="VALIDATION_ERROR", message=str(e), status_code=400)
    except BrokerException as e:
        return api_error(error_code="BROKER_ERROR", message=str(e), status_code=502)


# 5. Cancel Order
@orders_bp.route("/<client_order_id>/cancel", methods=["DELETE"])
@login_required
def cancel_order(client_order_id: str):
    """Cancel an active open order resting on the exchange."""
    user_id = getattr(g, "user_id", 1)
    try:
        result = order_execution_service.cancel_order(
            client_order_id=client_order_id,
            actor=f"user_{user_id}",
        )
        return api_response(data=result)
    except ExecutionModeException as e:
        return api_error(error_code="EXECUTION_MODE_DISABLED", message=str(e), status_code=403)
    except OrderValidationException as e:
        return api_error(error_code="VALIDATION_ERROR", message=str(e), status_code=400)
    except BrokerException as e:
        return api_error(error_code="BROKER_ERROR", message=str(e), status_code=502)


# 6. Emergency Cancel All
@orders_bp.route("/cancel-all", methods=["POST"])
@login_required
def cancel_all_orders():
    """Emergency kill-switch to mass-cancel all open orders across the account."""
    user_id = getattr(g, "user_id", 1)
    try:
        result = order_execution_service.cancel_all_orders(actor=f"user_{user_id}")
        return api_response(data=result)
    except ExecutionModeException as e:
        return api_error(error_code="EXECUTION_MODE_DISABLED", message=str(e), status_code=403)
    except Exception as e:
        return api_error(error_code="CANCEL_ALL_FAILED", message=f"Cancel all failed: {str(e)}", status_code=500)


# 7. Reconcile Unconfirmed Orders
@orders_bp.route("/reconcile", methods=["POST"])
@login_required
def reconcile_orders():
    """Trigger active reconciliation scan for unconfirmed / RECONCILING orders."""
    result = order_poller_service.reconcile_unconfirmed_orders()
    return api_response(data=result)


# 8. Dry-Run Validation (Zero Execution)
@orders_bp.route("/validate", methods=["POST"])
@login_required
def validate_order():
    """
    Dry-run order validation and pre-trade risk evaluation endpoint.
    Strictly performs pre-flight checks without submitting, placing, or routing orders.
    """
    payload = request.get_json() or {}
    user_id = getattr(g, "user_id", 1)

    try:
        side_val = OrderSide(payload.get("side", "BUY").upper())
    except ValueError:
        return api_error(error_code="INVALID_SIDE", message=f"Invalid side '{payload.get('side')}'. Must be BUY or SELL.", status_code=400)

    try:
        type_val = OrderType(payload.get("order_type", "LIMIT").upper())
    except ValueError:
        return api_error(error_code="INVALID_ORDER_TYPE", message=f"Invalid order_type '{payload.get('order_type')}'.", status_code=400)

    try:
        prod_val = ProductType(payload.get("product_type", "MIS").upper())
    except ValueError:
        return api_error(error_code="INVALID_PRODUCT_TYPE", message=f"Invalid product_type '{payload.get('product_type')}'.", status_code=400)

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
        return api_error(error_code="INVALID_QUANTITY", message="Quantity must be a valid integer.", status_code=400)

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

    # Structural Validation
    syntax_valid, validation_errors = order_validation_service.validate_order(order)

    # Market Protection Buffer Calculation
    buffered_price = price
    if type_val == OrderType.MARKET and price > 0:
        buffered_price = order_validation_service.calculate_market_protection(
            ref_price=price,
            side=side_val,
            mp_percent=2.0,
            tick_size=0.0025 if segment == "cde_fo" else 0.05,
        )

    # Pre-Trade Risk Evaluation
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


# 9. Query Order Book
@orders_bp.route("", methods=["GET"])
@login_required
def get_orders():
    """
    Retrieve filterable order book for the authenticated user.
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


# 10. Query Individual Order Detail & Transition Timeline
@orders_bp.route("/<client_order_id>", methods=["GET"])
@login_required
def get_order_detail(client_order_id: str):
    """Fetch comprehensive order detail including immutable state transition history."""
    order = order_repository.find_by_client_order_id(client_order_id)
    if not order:
        return api_error(error_code="ORDER_NOT_FOUND", message=f"Order '{client_order_id}' not found.", status_code=404)

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


# 11. Query Trade Book
@orders_bp.route("/trades", methods=["GET"])
@login_required
def get_trades():
    """Retrieve executed trade fills (trade book)."""
    user_id = getattr(g, "user_id", 1)
    trades = order_repository.get_trades(user_id=user_id, limit=100)
    return api_response(
        data={
            "count": len(trades),
            "trades": [t.to_dict() for t in trades],
        }
    )


# 12. Query Summary Stats
@orders_bp.route("/stats", methods=["GET"])
@login_required
def get_order_stats():
    """Retrieve daily summary statistics for user orders."""
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
