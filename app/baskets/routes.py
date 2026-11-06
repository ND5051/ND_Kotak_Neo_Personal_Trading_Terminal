"""
Basket Orders REST Controller.
Phase 9: Advanced Orders & Option Strategy Foundation.
Provides authenticated endpoints for multi-leg option strategy basket creation,
validation, execution, cancellation, and lifecycle tracking.
"""

from typing import Any, Dict, Optional
from flask import Blueprint, jsonify, request

from app.baskets.models.basket import BasketState, StrategyType
from app.baskets.services.basket_execution_service import basket_execution_service
from app.baskets.services.strategy_validator import strategy_validation_service
from app.baskets.repositories.basket_repository import basket_repository
from app.core.exceptions import (
    ApplicationException,
    BasketRiskException,
    BasketValidationException,
    ExecutionModeException,
)
from app.core.response import api_error, api_response
from app.orders.models.execution_mode import execution_mode_manager

# Register under both /api/baskets and /api/basket for seamless backward compatibility
baskets_bp = Blueprint("baskets", __name__, url_prefix="/api/baskets")
basket_bp = Blueprint("basket", __name__, url_prefix="/api/basket")


# 1. Public Operational Status
@baskets_bp.route("/status", methods=["GET"])
@basket_bp.route("/status", methods=["GET"])
def basket_status():
    """Retrieve operational status, active ExecutionMode, and supported strategies."""
    active_mode = execution_mode_manager.get_mode()
    return api_response(
        data={
            "status": "operational",
            "phase": "Phase 9 – Advanced Orders & Option Strategy Foundation",
            "execution_mode": active_mode.value,
            "execution_enabled": active_mode != execution_mode_manager.get_mode().DISABLED,
            "supported_strategies": [s.value for s in StrategyType],
            "default_execution_mode": "SEQUENTIAL",
            "default_failure_policy": "ABORT_REMAINING",
        }
    )


# 2. Create Basket Draft
@baskets_bp.route("", methods=["POST"])
@basket_bp.route("", methods=["POST"])
def create_basket():
    """Create a new multi-leg basket draft."""
    payload = request.get_json(silent=True) or {}
    if not payload:
        return api_error(
            error_code="INVALID_PAYLOAD",
            message="Request body must be a valid JSON object.",
            status_code=400,
        )

    try:
        basket = basket_execution_service.create_basket(payload)
        return api_response(data=basket.to_dict(), status_code=201)
    except ApplicationException as e:
        return api_error(error_code=e.error_code, message=e.message, details=e.details, status_code=e.status_code)
    except Exception as e:
        return api_error(error_code="BASKET_CREATION_FAILED", message=str(e), status_code=500)


# 3. Dry-Run Validation
@baskets_bp.route("/validate", methods=["POST"])
@basket_bp.route("/validate", methods=["POST"])
def validate_basket():
    """Dry-run validation of option structure, strike ladder, and pre-trade risk."""
    payload = request.get_json(silent=True) or {}
    if not payload:
        return api_error(
            error_code="INVALID_PAYLOAD",
            message="Request body must be a valid JSON object.",
            status_code=400,
        )

    try:
        # If basket_id provided, validate existing
        basket_id = payload.get("basket_id")
        if basket_id:
            basket = basket_repository.get_basket_by_id(basket_id)
            if not basket:
                return api_error(error_code="BASKET_NOT_FOUND", message=f"Basket not found: {basket_id}", status_code=404)
        else:
            # Temporary in-memory basket instance for dry-run
            basket = basket_execution_service.create_basket(payload)

        res = basket_execution_service.validate_basket(
            basket=basket,
            available_margin=float(payload.get("available_margin", 500000.0)),
            current_daily_pnl=float(payload.get("current_daily_pnl", 0.0)),
        )
        return api_response(data=res)
    except ApplicationException as e:
        return api_error(error_code=e.error_code, message=e.message, details=e.details, status_code=e.status_code)
    except Exception as e:
        return api_error(error_code="VALIDATION_FAILED", message=str(e), status_code=400)


# 4. Execute Basket
@baskets_bp.route("/<basket_id>/execute", methods=["POST"])
@basket_bp.route("/<basket_id>/execute", methods=["POST"])
def execute_basket(basket_id: str):
    """
    Trigger execution of a multi-leg basket.
    Gated by ExecutionMode (refuses wire/paper dispatch if DISABLED).
    """
    payload = request.get_json(silent=True) or {}
    available_margin = float(payload.get("available_margin", 500000.0))
    current_daily_pnl = float(payload.get("current_daily_pnl", 0.0))

    try:
        res = basket_execution_service.execute_basket(
            basket_id=basket_id,
            available_margin=available_margin,
            current_daily_pnl=current_daily_pnl,
        )
        return api_response(data=res, status_code=200 if res.get("success") else 400)
    except ExecutionModeException as e:
        return api_error(error_code=e.error_code, message=e.message, details=e.details, status_code=403)
    except ApplicationException as e:
        return api_error(error_code=e.error_code, message=e.message, details=e.details, status_code=e.status_code)
    except Exception as e:
        return api_error(error_code="BASKET_EXECUTION_FAILED", message=str(e), status_code=500)


# 5. Cancel Basket
@baskets_bp.route("/<basket_id>/cancel", methods=["POST"])
@basket_bp.route("/<basket_id>/cancel", methods=["POST"])
def cancel_basket(basket_id: str):
    """Cancel unfilled legs in an executing or draft basket."""
    try:
        res = basket_execution_service.cancel_basket(basket_id)
        return api_response(data=res)
    except ApplicationException as e:
        return api_error(error_code=e.error_code, message=e.message, details=e.details, status_code=e.status_code)
    except Exception as e:
        return api_error(error_code="BASKET_CANCEL_FAILED", message=str(e), status_code=500)


# 6. Reconcile Basket
@baskets_bp.route("/<basket_id>/reconcile", methods=["POST"])
@basket_bp.route("/<basket_id>/reconcile", methods=["POST"])
def reconcile_basket(basket_id: str):
    """Reconcile unconfirmed or partially executed basket against underlying order reports."""
    try:
        res = basket_execution_service.reconcile_basket(basket_id)
        return api_response(data=res)
    except ApplicationException as e:
        return api_error(error_code=e.error_code, message=e.message, details=e.details, status_code=e.status_code)
    except Exception as e:
        return api_error(error_code="BASKET_RECONCILE_FAILED", message=str(e), status_code=500)


# 7. List Baskets
@baskets_bp.route("", methods=["GET"])
@basket_bp.route("", methods=["GET"])
def list_baskets():
    """Retrieve filterable basket collection."""
    status_filter = request.args.get("status")
    strat_filter = request.args.get("strategy_type")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    baskets = basket_repository.find_baskets(
        status=status_filter,
        strategy_type=strat_filter,
        limit=limit,
        offset=offset,
    )
    return api_response(
        data={
            "baskets": [b.to_dict() for b in baskets],
            "count": len(baskets),
            "limit": limit,
            "offset": offset,
        }
    )


# 8. Get Basket Details & Events Timeline
@baskets_bp.route("/<basket_id>", methods=["GET"])
@basket_bp.route("/<basket_id>", methods=["GET"])
def get_basket_detail(basket_id: str):
    """Retrieve full basket details and audit timeline."""
    basket = basket_repository.get_basket_by_id(basket_id)
    if not basket:
        return api_error(error_code="BASKET_NOT_FOUND", message=f"Basket not found: {basket_id}", status_code=404)

    events = basket_repository.get_basket_events(basket.client_basket_id)
    basket_dict = basket.to_dict()
    basket_dict["events"] = [e.to_dict() for e in events]
    return api_response(data=basket_dict)
