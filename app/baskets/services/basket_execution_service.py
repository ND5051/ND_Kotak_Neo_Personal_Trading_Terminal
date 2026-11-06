from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, List, Optional
import uuid

from app.baskets.models.basket import (
    Basket,
    BasketExecutionMode,
    BasketExposureState,
    BasketFailurePolicy,
    BasketLeg,
    BasketState,
)
from app.baskets.repositories.basket_repository import (
    BasketRepositoryInterface,
    basket_repository,
)
from app.baskets.services.basket_exposure_service import (
    BasketExposureService,
    basket_exposure_service,
)
from app.baskets.services.basket_idempotency_manager import (
    BasketIdempotencyManager,
    basket_idempotency_manager,
)
from app.baskets.services.basket_risk_service import (
    BasketRiskService,
    basket_risk_service,
)
from app.baskets.services.basket_state_machine import (
    BasketStateMachine,
    basket_state_machine,
)
from app.baskets.services.strategy_validator import (
    StrategyValidationService,
    strategy_validation_service,
)
from app.core.audit import (
    audit_logger,
    AuditCategory,
    AUDIT_BASKET_CANCELLED,
    AUDIT_BASKET_CREATED,
    AUDIT_BASKET_EXECUTION_STARTED,
    AUDIT_BASKET_FAILED,
    AUDIT_BASKET_LEG_FILLED,
    AUDIT_BASKET_RECONCILIATION,
    AUDIT_BASKET_VALIDATED,
)
from app.core.exceptions import (
    BasketRiskException,
    BasketValidationException,
    ExecutionModeException,
)
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import (
    BASKET_CANCELLED,
    BASKET_COMPLETED,
    BASKET_CREATED,
    BASKET_EXECUTION_STARTED,
    BASKET_FAILED,
    BASKET_LEG_FILLED,
    BASKET_RECONCILING,
    BASKET_VALIDATED,
)
from app.logging.logger import get_logger
from app.orders.models.execution_mode import (
    ExecutionMode,
    ExecutionModeManager,
    execution_mode_manager,
)
from app.orders.models.order import OrderStatus
from app.orders.repositories.order_repository import (
    OrderRepositoryInterface,
    order_repository,
)
from app.orders.services.order_execution_service import (
    OrderExecutionService,
    order_execution_service,
)

logger = get_logger("app.baskets.services.executor")


class BasketExecutionService:
    """
    Multi-Leg Basket & Option Strategy Execution Orchestrator.
    Guarantees strict ExecutionMode inheritance (refuses execution under DISABLED),
    enforces Level 1 Basket Idempotency, validates option structure parity,
    clears multi-leg pre-trade risk, coordinates leg dispatch sequencing
    (SEQUENTIAL default, PARALLEL, DEPENDENCY), and executes BasketFailurePolicy.ABORT_REMAINING.
    """

    def __init__(
        self,
        repository: Optional[BasketRepositoryInterface] = None,
        order_repo: Optional[OrderRepositoryInterface] = None,
        state_machine: Optional[BasketStateMachine] = None,
        idempotency: Optional[BasketIdempotencyManager] = None,
        validator: Optional[StrategyValidationService] = None,
        risk_service: Optional[BasketRiskService] = None,
        exposure_service: Optional[BasketExposureService] = None,
        order_service: Optional[OrderExecutionService] = None,
        mode_manager: Optional[ExecutionModeManager] = None,
    ) -> None:
        self.repository = repository or basket_repository
        self.order_repo = order_repo or order_repository
        self.state_machine = state_machine or basket_state_machine
        self.idempotency = idempotency or basket_idempotency_manager
        self.validator = validator or strategy_validation_service
        self.risk_service = risk_service or basket_risk_service
        self.exposure_service = exposure_service or basket_exposure_service
        self.order_service = order_service or order_execution_service
        self.mode_manager = mode_manager or execution_mode_manager
        self._lock = threading.RLock()

    def create_basket(self, basket_data: Dict[str, Any]) -> Basket:
        """
        Create a new DRAFT multi-leg basket container.
        """
        client_basket_id = basket_data.get("client_basket_id") or f"BKT_{uuid.uuid4().hex[:12]}"
        user_id = basket_data.get("user_id", 1)
        legs_data = basket_data.get("legs", [])

        # Idempotency check
        idemp_key = self.idempotency.compute_basket_hash(
            user_id=user_id,
            strategy_type=basket_data.get("strategy_type", "CUSTOM"),
            legs=legs_data,
        )

        legs: List[BasketLeg] = []
        for idx, ld in enumerate(legs_data):
            leg = BasketLeg(
                leg_id=ld.get("leg_id") or str(uuid.uuid4()),
                leg_index=idx,
                trading_symbol=ld.get("trading_symbol", ""),
                exchange_segment=ld.get("exchange_segment", "nse_fo"),
                instrument_token=str(ld.get("instrument_token", "")),
                side=ld.get("side", "BUY"),
                order_type=ld.get("order_type", "LIMIT"),
                product_type=ld.get("product_type", "MIS"),
                validity=ld.get("validity", "DAY"),
                quantity=int(ld.get("quantity", 0)),
                price=float(ld.get("price", 0.0)),
                trigger_price=float(ld.get("trigger_price", 0.0)),
                depends_on_leg_index=ld.get("depends_on_leg_index"),
            )
            legs.append(leg)

        basket = Basket(
            client_basket_id=client_basket_id,
            basket_idempotency_key=idemp_key,
            user_id=user_id,
            name=basket_data.get("name", "Option Strategy Basket"),
            strategy_type=basket_data.get("strategy_type", "CUSTOM"),
            strategy_version=basket_data.get("strategy_version", "V1"),
            execution_mode=self.mode_manager.get_mode(),
            basket_execution_mode=basket_data.get("basket_execution_mode", BasketExecutionMode.SEQUENTIAL),
            failure_policy=basket_data.get("failure_policy", BasketFailurePolicy.ABORT_REMAINING),
            status=BasketState.DRAFT,
            exposure_state=BasketExposureState.NEUTRAL,
            legs=legs,
        )

        saved = self.repository.save_basket(basket)

        audit_logger.record(
            category=AuditCategory.BASKET,
            action=AUDIT_BASKET_CREATED,
            actor=f"user_{user_id}",
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"client_basket_id": client_basket_id, "strategy": str(basket.strategy_type)},
        )
        publish(BASKET_CREATED, {"basket": saved.to_dict()})
        return saved

    def validate_basket(
        self, basket: Basket, available_margin: float = 500000.0, current_daily_pnl: float = 0.0
    ) -> Dict[str, Any]:
        """
        Validate structure and evaluate pre-trade capital risk.
        """
        with self._lock:
            # 1. Structural Validation
            is_valid, struct_errors = self.validator.validate_basket(basket)
            if not is_valid:
                raise BasketValidationException(
                    message=f"Basket structural validation failed: {'; '.join(struct_errors)}",
                    details={"errors": struct_errors},
                )

            self.state_machine.transition_to(basket, BasketState.VALIDATED, reason="Structure Verified")

            # 2. Risk Clearance
            risk_passed, margin_snap, risk_errors = self.risk_service.assess_basket_risk(
                basket=basket,
                available_margin=available_margin,
                current_daily_pnl=current_daily_pnl,
            )

            if not risk_passed:
                self.state_machine.transition_to(basket, BasketState.FAILED, reason=risk_errors[0])
                raise BasketRiskException(
                    message=f"Basket risk clearance failed: {'; '.join(risk_errors)}",
                    details={"errors": risk_errors, "margin_snapshot": margin_snap},
                )

            self.state_machine.transition_to(basket, BasketState.READY, reason="Risk Cleared")
            self.repository.save_basket(basket)

            audit_logger.record(
                category=AuditCategory.BASKET,
                action=AUDIT_BASKET_VALIDATED,
                actor="risk_service",
                correlation_id=get_correlation_id(),
                request_id=get_request_id(),
                details={"client_basket_id": basket.client_basket_id, "margin": margin_snap},
            )

            return {
                "valid": True,
                "strategy_syntax_passed": True,
                "risk_checks_passed": True,
                "estimated_margin": basket.estimated_margin,
                "margin_snapshot": margin_snap,
                "errors": [],
            }

    def execute_basket(
        self,
        basket_id: str,
        available_margin: float = 500000.0,
        current_daily_pnl: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Execute multi-leg basket across the wire or paper simulator.
        Mandatory ExecutionMode inheritance and idempotency checks.
        """
        with self._lock:
            # 1. ExecutionMode Inheritance Gate
            active_mode = self.mode_manager.get_mode()
            if active_mode == ExecutionMode.DISABLED:
                logger.error("Basket execution refused: Mode is DISABLED", event="BASKET_EXEC_REFUSED")
                raise ExecutionModeException(
                    message="Basket execution is strictly DISABLED. Wire submission and paper execution are refused."
                )

            basket = self.repository.get_basket_by_id(basket_id)
            if not basket:
                raise BasketValidationException(f"Basket not found: {basket_id}")

            # 2. Level 1 Basket Idempotency Verification
            if not self.idempotency.acquire_execution(basket.client_basket_id, basket.basket_idempotency_key):
                logger.warning(f"Duplicate basket execution detected: {basket.client_basket_id}")
                return {
                    "success": False,
                    "error": "DUPLICATE_BASKET_REQUEST",
                    "message": "Basket is currently executing or has already been submitted.",
                    "basket": basket.to_dict(),
                }

            if basket.is_terminal():
                raise BasketValidationException(f"Cannot execute terminal basket in state {basket.status.value}")

            # Update inherited mode
            basket.execution_mode = active_mode

            # 3. Validate & Risk Check if in DRAFT
            if basket.status == BasketState.DRAFT:
                self.validate_basket(basket, available_margin, current_daily_pnl)

            # 4. Transition to EXECUTING
            self.state_machine.transition_to(basket, BasketState.EXECUTING, reason="Execution Initiated")
            self.exposure_service.update_exposure_state(basket)
            self.repository.save_basket(basket)

            audit_logger.record(
                category=AuditCategory.BASKET,
                action=AUDIT_BASKET_EXECUTION_STARTED,
                actor="basket_executor",
                correlation_id=get_correlation_id(),
                request_id=get_request_id(),
                details={"client_basket_id": basket.client_basket_id, "mode": active_mode.value},
            )

            # 5. Dispatch Legs according to basket_execution_mode
            dispatch_mode = basket.basket_execution_mode
            if dispatch_mode == BasketExecutionMode.DEPENDENCY:
                res = self._dispatch_dependency_legs(basket, available_margin)
            elif dispatch_mode == BasketExecutionMode.PARALLEL:
                res = self._dispatch_parallel_legs(basket, available_margin)
            else:
                # Default: SEQUENTIAL
                res = self._dispatch_sequential_legs(basket, available_margin)

            # Re-evaluate Exposure State and Final Status
            self.exposure_service.update_exposure_state(basket)
            self._evaluate_final_basket_state(basket)
            self.repository.save_basket(basket)

            return {
                "success": res.get("success", False),
                "basket_id": basket.basket_id,
                "client_basket_id": basket.client_basket_id,
                "execution_mode": active_mode.value,
                "basket_execution_mode": dispatch_mode.value,
                "status": basket.status.value,
                "exposure_state": basket.exposure_state.value,
                "legs": [l.to_dict() for l in basket.legs],
                "message": res.get("message", "Execution processed"),
            }

    # 1. Sequential Leg Dispatch (Phase 9 Default)
    def _dispatch_sequential_legs(self, basket: Basket, available_margin: float) -> Dict[str, Any]:
        """
        Dispatch legs strictly one after another.
        Enforces BasketFailurePolicy.ABORT_REMAINING if a leg fails.
        """
        for leg in sorted(basket.legs, key=lambda l: l.leg_index):
            leg_res = self._dispatch_single_leg(basket, leg, available_margin)

            if not leg_res.get("success", False):
                # Failure policy evaluation
                if basket.failure_policy == BasketFailurePolicy.ABORT_REMAINING:
                    logger.warning(
                        f"Leg {leg.leg_index} failed for basket {basket.client_basket_id}. "
                        f"FailurePolicy=ABORT_REMAINING in effect. Halting remaining legs.",
                        event="BASKET_LEG_ABORT",
                    )
                    return {
                        "success": False,
                        "aborted_at_leg": leg.leg_index,
                        "message": f"Execution halted at leg {leg.leg_index} due to failure: {leg_res.get('error', 'Unknown')}",
                    }
                # Else CONTINUE (only on CUSTOM)
                logger.info(f"Leg {leg.leg_index} failed, but failure policy=CONTINUE. Continuing...")

        return {"success": True, "message": "All sequential legs processed"}

    # 2. Dependency Graph Dispatch (DAG)
    def _dispatch_dependency_legs(self, basket: Basket, available_margin: float) -> Dict[str, Any]:
        """
        Dispatch legs following dependency rules (e.g. wings before body).
        """
        executed_indices = set()
        pending_legs = list(basket.legs)

        while pending_legs:
            runnable = [
                l for l in pending_legs
                if l.depends_on_leg_index is None or l.depends_on_leg_index in executed_indices
            ]

            if not runnable:
                # Deadlock / unmet dependency
                err_msg = "Dependency execution deadlocked: unmet dependency cycle detected."
                logger.error(err_msg, event="BASKET_DEPENDENCY_DEADLOCK")
                return {"success": False, "message": err_msg}

            for leg in runnable:
                leg_res = self._dispatch_single_leg(basket, leg, available_margin)
                if not leg_res.get("success", False):
                    if basket.failure_policy == BasketFailurePolicy.ABORT_REMAINING:
                        return {
                            "success": False,
                            "aborted_at_leg": leg.leg_index,
                            "message": f"Dependency leg {leg.leg_index} failed. Aborting remaining legs.",
                        }
                executed_indices.add(leg.leg_index)
                pending_legs.remove(leg)

        return {"success": True, "message": "All dependency legs executed successfully"}

    # 3. Parallel Leg Dispatch
    def _dispatch_parallel_legs(self, basket: Basket, available_margin: float) -> Dict[str, Any]:
        """
        Dispatch all legs concurrently using background threads.
        """
        threads = []
        results = {}

        def _worker(leg: BasketLeg):
            results[leg.leg_index] = self._dispatch_single_leg(basket, leg, available_margin)

        for leg in basket.legs:
            t = threading.Thread(target=_worker, args=(leg,), name=f"BasketLegThread-{leg.leg_index}")
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5.0)

        all_success = all(r.get("success", False) for r in results.values())
        return {"success": all_success, "results": results}

    def _dispatch_single_leg(self, basket: Basket, leg: BasketLeg, available_margin: float) -> Dict[str, Any]:
        """
        Route an individual basket leg to the Phase 8 OrderExecutionService.
        """
        client_order_id = f"{basket.client_basket_id[:16]}_L{leg.leg_index}_{uuid.uuid4().hex[:6]}"
        leg.order_id = client_order_id

        payload = {
            "client_order_id": client_order_id,
            "trading_symbol": leg.trading_symbol,
            "exchange_segment": leg.exchange_segment,
            "side": leg.side.value if hasattr(leg.side, "value") else str(leg.side),
            "order_type": leg.order_type.value if hasattr(leg.order_type, "value") else str(leg.order_type),
            "product_type": leg.product_type.value if hasattr(leg.product_type, "value") else str(leg.product_type),
            "validity": leg.validity.value if hasattr(leg.validity, "value") else str(leg.validity),
            "quantity": leg.quantity,
            "price": leg.price,
            "trigger_price": leg.trigger_price,
            "tag": f"BKT_{basket.client_basket_id[:8]}",
        }

        try:
            order_res = self.order_service.place_order(payload, available_cash=available_margin)
            if order_res.get("success", False):
                order_info = order_res.get("order", {})
                leg.broker_order_id = order_info.get("broker_order_id")
                raw_st = order_info.get("status", "ACKNOWLEDGED")
                if basket.execution_mode == ExecutionMode.PAPER and raw_st in ("ACKNOWLEDGED", "SUBMITTED"):
                    raw_st = "FILLED"
                leg.status = OrderStatus(raw_st) if raw_st in OrderStatus._value2member_map_ else OrderStatus.ACKNOWLEDGED
                leg.filled_quantity = order_info.get(
                    "filled_quantity", leg.quantity if leg.status == OrderStatus.FILLED else 0
                )
                leg.average_price = order_info.get("average_price", leg.price)

                audit_logger.record(
                    category=AuditCategory.BASKET,
                    action=AUDIT_BASKET_LEG_FILLED,
                    actor="basket_executor",
                    correlation_id=get_correlation_id(),
                    request_id=get_request_id(),
                    details={
                        "client_basket_id": basket.client_basket_id,
                        "leg_index": leg.leg_index,
                        "order_id": client_order_id,
                        "status": leg.status.value,
                    },
                )
                publish(
                    BASKET_LEG_FILLED,
                    {
                        "basket_id": basket.basket_id,
                        "client_basket_id": basket.client_basket_id,
                        "leg_index": leg.leg_index,
                        "order_id": client_order_id,
                        "status": leg.status.value,
                    },
                )
                return {"success": True, "leg_index": leg.leg_index, "status": leg.status.value}
            else:
                leg.status = OrderStatus.REJECTED
                return {"success": False, "leg_index": leg.leg_index, "error": order_res.get("error", "RMS Rejection")}

        except Exception as e:
            logger.error(f"Error executing leg {leg.leg_index}: {str(e)}", exc_info=True)
            leg.status = OrderStatus.FAILED
            return {"success": False, "leg_index": leg.leg_index, "error": str(e)}

    def _evaluate_final_basket_state(self, basket: Basket) -> None:
        """
        Evaluate overall basket state based on leg terminal statuses and The Golden Rule.
        """
        statuses = [l.status for l in basket.legs]

        # 1. Any leg RECONCILING -> Basket RECONCILING (The Golden Rule)
        if OrderStatus.RECONCILING in statuses:
            self.state_machine.transition_to(basket, BasketState.RECONCILING, reason="Leg in unconfirmed state")
            return

        # 2. All legs FILLED -> Basket EXECUTED
        if all(s == OrderStatus.FILLED for s in statuses):
            self.state_machine.transition_to(basket, BasketState.EXECUTED, reason="All legs completely filled")
            return

        # 3. Some legs filled, some failed/rejected/unfilled -> PARTIALLY_EXECUTED
        if any(s == OrderStatus.FILLED for s in statuses):
            self.state_machine.transition_to(
                basket, BasketState.PARTIALLY_EXECUTED, reason="Partial fills with remaining legs halted"
            )
            return

        # 4. Zero fills and failures -> FAILED
        if any(s in (OrderStatus.REJECTED, OrderStatus.FAILED) for s in statuses):
            self.state_machine.transition_to(basket, BasketState.FAILED, reason="Initial leg failed execution")

    def cancel_basket(self, basket_id: str) -> Dict[str, Any]:
        """
        Cancel a resting, draft, or executing basket.
        Cancels unfilled orders via Phase 8 order_execution_service.
        """
        with self._lock:
            basket = self.repository.get_basket_by_id(basket_id)
            if not basket:
                raise BasketValidationException(f"Basket not found: {basket_id}")

            if basket.is_terminal():
                return {"success": False, "message": f"Basket is already in terminal state {basket.status.value}"}

            cancelled_legs = 0
            for leg in basket.legs:
                if leg.order_id and leg.status in (OrderStatus.ACKNOWLEDGED, OrderStatus.PENDING_VALIDATION, OrderStatus.SUBMITTED):
                    try:
                        self.order_service.cancel_order(leg.order_id)
                        leg.status = OrderStatus.CANCELLED
                        cancelled_legs += 1
                    except Exception as e:
                        logger.warning(f"Could not cancel leg order {leg.order_id}: {str(e)}")

            self.state_machine.transition_to(basket, BasketState.CANCELLED, reason="Cancelled by Operator")
            self.exposure_service.update_exposure_state(basket)
            self.repository.save_basket(basket)

            audit_logger.record(
                category=AuditCategory.BASKET,
                action=AUDIT_BASKET_CANCELLED,
                actor="operator",
                correlation_id=get_correlation_id(),
                request_id=get_request_id(),
                details={"client_basket_id": basket.client_basket_id, "cancelled_legs": cancelled_legs},
            )
            return {
                "success": True,
                "basket_id": basket.basket_id,
                "status": "CANCELLED",
                "cancelled_legs": cancelled_legs,
            }

    def reconcile_basket(self, basket_id: str) -> Dict[str, Any]:
        """
        Reconcile a basket stuck in RECONCILING or PARTIALLY_EXECUTED.
        Queries underlying order records to resolve unconfirmed broker states.
        """
        with self._lock:
            basket = self.repository.get_basket_by_id(basket_id)
            if not basket:
                raise BasketValidationException(f"Basket not found: {basket_id}")

            updated_legs = 0
            for leg in basket.legs:
                if leg.order_id:
                    order = self.order_repo.find_by_client_order_id(leg.order_id)
                    if order and order.status != leg.status:
                        leg.status = order.status
                        leg.filled_quantity = order.filled_quantity
                        leg.average_price = order.average_price
                        updated_legs += 1

            self.exposure_service.update_exposure_state(basket)
            self._evaluate_final_basket_state(basket)
            self.repository.save_basket(basket)

            audit_logger.record(
                category=AuditCategory.BASKET,
                action=AUDIT_BASKET_RECONCILIATION,
                actor="basket_reconciler",
                correlation_id=get_correlation_id(),
                request_id=get_request_id(),
                details={"client_basket_id": basket.client_basket_id, "updated_legs": updated_legs},
            )

            return {
                "success": True,
                "basket_id": basket.basket_id,
                "status": basket.status.value,
                "exposure_state": basket.exposure_state.value,
                "updated_legs": updated_legs,
            }


# Global singleton
basket_execution_service = BasketExecutionService()
