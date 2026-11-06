from datetime import datetime, timezone
import random
import threading
import time
from typing import Any, Dict, List, Optional
import uuid

from app.broker.adapters.kotak_order_adapter import (
    kotak_order_adapter,
    KotakOrderAdapterInterface,
)
from app.broker.services.broker_circuit_breaker import (
    broker_circuit_breaker,
    BrokerCircuitBreaker,
)
from app.core.audit import (
    audit_logger,
    AuditCategory,
    AUDIT_EMERGENCY_CANCEL_ALL,
    AUDIT_ORDER_CANCEL,
    AUDIT_ORDER_EXECUTION_FAILURE,
    AUDIT_ORDER_MODIFY,
    AUDIT_ORDER_PLACE,
)
from app.core.exceptions import (
    BrokerCircuitBreakerOpenException,
    BrokerException,
    ExecutionModeException,
    OrderRiskException,
    OrderValidationException,
)
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import (
    ORDER_ACKNOWLEDGED,
    ORDER_CANCELLED,
    ORDER_EMERGENCY_CANCELLED,
    ORDER_MODIFIED,
    ORDER_SUBMITTED,
)
from app.logging.logger import get_logger
from app.orders.models.execution_mode import (
    execution_mode_manager,
    ExecutionMode,
    ExecutionModeManager,
)
from app.orders.models.order import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
    Validity,
)
from app.orders.repositories.order_repository import (
    order_repository,
    OrderRepositoryInterface,
)
from app.orders.services.idempotency_manager import (
    idempotency_manager,
    IdempotencyManager,
)
from app.orders.services.order_poller_service import (
    order_poller_service,
    OrderPollerService,
)
from app.orders.services.order_risk_service import (
    order_risk_service,
    OrderRiskService,
)
from app.orders.services.order_state_machine import (
    order_state_machine,
    OrderStateMachine,
)
from app.orders.services.order_validation_service import (
    order_validation_service,
    OrderValidationService,
)

logger = get_logger("app.orders.execution")


class OrderExecutionService:
    """
    Production Order Execution Orchestrator.
    Safely executes orders across wire adapters while strictly enforcing:
    1. ExecutionMode gating (DISABLED, PAPER, LIVE).
    2. Two-tier atomic idempotency (client_order_id deduplication).
    3. Pre-flight structural and pre-trade risk validation.
    4. Circuit breaker pre-flight checks.
    5. Deterministic FSM state transitions.
    6. Market Protection (MP) on market orders and clean broker-side SL orders.
    7. Asynchronous status polling and reconciliation.
    """

    def __init__(
        self,
        mode_manager: Optional[ExecutionModeManager] = None,
        adapter: Optional[KotakOrderAdapterInterface] = None,
        repository: Optional[OrderRepositoryInterface] = None,
        state_machine: Optional[OrderStateMachine] = None,
        validation_service: Optional[OrderValidationService] = None,
        risk_service: Optional[OrderRiskService] = None,
        circuit_breaker: Optional[BrokerCircuitBreaker] = None,
        idempotency: Optional[IdempotencyManager] = None,
        poller: Optional[OrderPollerService] = None,
    ) -> None:
        self.mode_manager = mode_manager or execution_mode_manager
        self.adapter = adapter or kotak_order_adapter
        self.repository = repository or order_repository
        self.state_machine = state_machine or order_state_machine
        self.validation_service = validation_service or order_validation_service
        self.risk_service = risk_service or order_risk_service
        self.circuit_breaker = circuit_breaker or broker_circuit_breaker
        self.idempotency = idempotency or idempotency_manager
        self.poller = poller or order_poller_service
        self._lock = threading.RLock()

    # 1. Place Order
    def place_order(
        self,
        order_params: Dict[str, Any],
        user_id: int = 1,
        available_cash: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Execute end-to-end order placement pipeline.
        Refuses execution if mode is DISABLED.
        """
        # Step 1: Execution Mode Gate
        self.mode_manager.assert_execution_permitted()
        active_mode = self.mode_manager.get_mode()

        # Step 2: Idempotency Check
        client_order_id = order_params.get("client_order_id") or str(uuid.uuid4())
        order_params["client_order_id"] = client_order_id

        if not self.idempotency.check_and_acquire(client_order_id):
            logger.warning(
                f"Duplicate order request rejected for client_order_id: {client_order_id}",
                event="IDEMPOTENCY_DUPLICATE_DETECTED",
            )
            existing = self.repository.find_by_client_order_id(client_order_id)
            if existing:
                return {
                    "success": True,
                    "is_duplicate": True,
                    "order": existing.to_dict(),
                    "message": "Duplicate order request; returned existing order",
                }

        # Step 3: Instantiate Domain Order
        now_utc = datetime.now(timezone.utc).isoformat()
        side_val = OrderSide(order_params.get("side", "BUY").upper())
        type_val = OrderType(order_params.get("order_type", "LIMIT").upper())
        prod_val = ProductType(order_params.get("product_type", "CNC").upper())
        valid_val = Validity(order_params.get("validity", "DAY").upper())

        price = float(order_params.get("price", 0.0))
        trigger_price = float(order_params.get("trigger_price", 0.0))
        quantity = int(order_params.get("quantity", 1))
        symbol = str(order_params.get("trading_symbol", "")).strip()
        segment = str(order_params.get("exchange_segment", "nse_cm")).strip().lower()

        # Step 4: Defensive Market Protection (MP) Buffering on Market orders
        if type_val == OrderType.MARKET:
            mp_percent = float(order_params.get("market_protection_percent", 2.0))
            ref_price = price if price > 0.0 else 100.0  # reference price
            price = self.validation_service.calculate_market_protection(
                ref_price=ref_price,
                side=side_val,
                mp_percent=mp_percent,
                tick_size=0.05,
            )
            type_val = OrderType.LIMIT
            logger.info(
                f"Applied Market Protection buffer ({mp_percent}%) converting MARKET to LIMIT @ {price:.2f}",
                event="MARKET_PROTECTION_APPLIED",
            )

        # Step 5: Clean Broker-Side Stop Loss Orders
        if type_val == OrderType.SL and trigger_price > 0.0:
            if price == 0.0 or abs(price - trigger_price) > 0.01:
                price = trigger_price  # Enforce price == trigger_price to eliminate slippage

        order = Order(
            client_order_id=client_order_id,
            broker_order_id=None,
            user_id=user_id,
            trading_symbol=symbol,
            exchange_segment=segment,
            instrument_token=str(order_params.get("instrument_token") or order_params.get("token") or "26000"),
            side=side_val,
            order_type=type_val,
            product_type=prod_val,
            validity=valid_val,
            quantity=quantity,
            disclosed_quantity=int(order_params.get("disclosed_quantity", 0)),
            price=price,
            trigger_price=trigger_price,
            status=OrderStatus.PENDING_VALIDATION,
            source_timestamp=now_utc,
            retrieved_timestamp=now_utc,
        )

        try:
            # Step 6: Pre-Flight Structural Validation
            syntax_valid, validation_errors = self.validation_service.validate_order(order)
            if not syntax_valid:
                error_msg = "; ".join(validation_errors)
                self.idempotency.release(client_order_id)
                self.state_machine.transition(order, OrderStatus.REJECTED, reason=error_msg)
                self.repository.save_order(order)
                raise OrderValidationException(error_msg, details={"errors": validation_errors})

            # Step 7: Pre-Trade Risk Evaluation
            risk_passed, risk_metadata = self.risk_service.evaluate_risk(order, available_cash=available_cash)
            if not risk_passed:
                violations = risk_metadata.get("violations", [])
                risk_msg = "; ".join(violations) if violations else "Pre-trade risk check failed"
                self.idempotency.release(client_order_id)
                self.state_machine.transition(order, OrderStatus.REJECTED, reason=risk_msg)
                self.repository.save_order(order)
                raise OrderRiskException(risk_msg, details=risk_metadata)

            # Step 8: Circuit Breaker Inspection
            self.circuit_breaker.allow_request()

            # Step 9: FSM Transitions to VALIDATED then SUBMITTED
            self.state_machine.transition_to(order, OrderStatus.VALIDATED, reason="Pre-flight and risk checks passed")
            self.state_machine.transition_to(order, OrderStatus.SUBMITTED, reason="Dispatching to broker gateway")
            self.repository.save_order(order)
            publish(ORDER_SUBMITTED, {"order": order.to_dict()})

            # Step 10: Execution Routing
            if active_mode == ExecutionMode.PAPER:
                return self._execute_paper_order(order)
            elif active_mode == ExecutionMode.LIVE:
                return self._execute_live_order(order)
            else:
                raise ExecutionModeException("Execution refused: Mode is DISABLED.")

        except (OrderValidationException, OrderRiskException, BrokerCircuitBreakerOpenException):
            raise
        except Exception as e:
            self.idempotency.release(client_order_id)
            logger.error(f"Unhandled error during order placement: {str(e)}", exc_info=True)
            raise

    # 2. Modify Order
    def modify_order(
        self,
        client_order_id: str,
        modifications: Dict[str, Any],
        actor: str = "operator",
    ) -> Dict[str, Any]:
        """Modify an active open order resting on the exchange."""
        self.mode_manager.assert_execution_permitted()

        order = self.repository.find_by_client_order_id(client_order_id)
        if not order:
            raise OrderValidationException(f"Order not found: {client_order_id}")

        if not order.is_open():
            raise OrderValidationException(f"Cannot modify order in terminal state: {order.status.value}")

        new_price = float(modifications.get("price", order.price))
        new_quantity = int(modifications.get("quantity", order.quantity))
        new_trigger = float(modifications.get("trigger_price", order.trigger_price))

        # Validate tick size on new price
        if not self.validation_service.validate_tick_size(new_price, tick_size=0.05):
            raise OrderValidationException(f"Modified price {new_price} is not a valid 0.05 tick multiple")

        active_mode = self.mode_manager.get_mode()

        if active_mode == ExecutionMode.LIVE and order.broker_order_id:
            res = self.adapter.modify_order(
                order=order,
                modifications={"price": new_price, "quantity": new_quantity, "trigger_price": new_trigger},
            )
            if res.get("stat") != "Ok":
                raise BrokerException(f"Broker rejected modification: {res.get('rejection_reason')}")

        # Update local order
        order.price = new_price
        order.quantity = new_quantity
        order.trigger_price = new_trigger
        order.source_timestamp = datetime.now(timezone.utc).isoformat()
        order.retrieved_timestamp = datetime.now(timezone.utc).isoformat()
        self.repository.save_order(order)

        # Audit & Event
        audit_logger.record(
            category=AuditCategory.ORDER,
            action=AUDIT_ORDER_MODIFY,
            actor=actor,
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"client_order_id": client_order_id, "modifications": modifications},
        )
        publish(ORDER_MODIFIED, {"order": order.to_dict(), "modifications": modifications})

        return {"success": True, "order": order.to_dict()}

    # 3. Cancel Order
    def cancel_order(self, client_order_id: str, actor: str = "operator") -> Dict[str, Any]:
        """Cancel an open order resting on the exchange."""
        self.mode_manager.assert_execution_permitted()

        order = self.repository.find_by_client_order_id(client_order_id)
        if not order:
            raise OrderValidationException(f"Order not found: {client_order_id}")

        if order.is_terminal():
            raise OrderValidationException(f"Cannot cancel order already in terminal state: {order.status.value}")

        active_mode = self.mode_manager.get_mode()

        if active_mode == ExecutionMode.LIVE and order.broker_order_id:
            res = self.adapter.cancel_order(order)
            if res.get("stat") != "Ok":
                raise BrokerException(f"Broker rejected cancellation: {res.get('rejection_reason')}")

        # Transition FSM to CANCELLED
        self.state_machine.transition_to(order, OrderStatus.CANCELLED, reason=f"Cancelled by {actor}")
        self.repository.save_order(order)

        # Audit & Event
        audit_logger.record(
            category=AuditCategory.ORDER,
            action=AUDIT_ORDER_CANCEL,
            actor=actor,
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"client_order_id": client_order_id, "broker_order_id": order.broker_order_id},
        )
        publish(ORDER_CANCELLED, {"order": order.to_dict()})

        return {"success": True, "order_id": client_order_id, "status": "CANCELLED"}

    # 4. Emergency Cancel All
    def cancel_all_orders(self, actor: str = "operator") -> Dict[str, Any]:
        """Emergency mass cancellation kill-switch for all resting orders."""
        self.mode_manager.assert_execution_permitted()

        open_statuses = [OrderStatus.ACKNOWLEDGED, OrderStatus.TRIGGER_PENDING, OrderStatus.PARTIALLY_FILLED]
        all_candidates: List[Order] = []
        for st in open_statuses:
            all_candidates.extend(self.repository.find_orders(status=st, limit=100))

        cancelled_count = 0
        failed_count = 0

        for ord_item in all_candidates:
            try:
                self.cancel_order(ord_item.client_order_id, actor=f"emergency_kill_switch({actor})")
                cancelled_count += 1
            except Exception as e:
                logger.error(f"Failed to cancel order {ord_item.client_order_id}: {str(e)}")
                failed_count += 1

        audit_logger.record(
            category=AuditCategory.ORDER,
            action=AUDIT_EMERGENCY_CANCEL_ALL,
            actor=actor,
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"total_candidates": len(all_candidates), "cancelled": cancelled_count, "failed": failed_count},
        )
        publish(ORDER_EMERGENCY_CANCELLED, {"total": len(all_candidates), "cancelled": cancelled_count, "failed": failed_count})

        return {
            "success": True,
            "total_found": len(all_candidates),
            "cancelled": cancelled_count,
            "failed": failed_count,
        }

    # Internal Live Order Wire Dispatch
    def _execute_live_order(self, order: Order) -> Dict[str, Any]:
        """Dispatch order to live Kotak Neo API gateway."""
        try:
            wire_resp = self.adapter.place_order(order)
            stat = wire_resp.get("stat")
            broker_order_id = wire_resp.get("nOrdNo")

            if stat == "Ok" and broker_order_id:
                self.circuit_breaker.record_success()
                order.broker_order_id = str(broker_order_id)
                self.state_machine.transition_to(order, OrderStatus.ACKNOWLEDGED, reason="Broker Gateway Ingestion Successful")
                self.repository.save_order(order)

                # Audit & Events
                audit_logger.record(
                    category=AuditCategory.ORDER,
                    action=AUDIT_ORDER_PLACE,
                    actor="order_execution_service",
                    correlation_id=get_correlation_id(),
                    request_id=get_request_id(),
                    details={"client_order_id": order.client_order_id, "broker_order_id": broker_order_id},
                )
                publish(ORDER_ACKNOWLEDGED, {"order": order.to_dict()})

                # Spawn background poller to resolve exchange fills
                self.poller.spawn_async_poll(order)

                return {
                    "success": True,
                    "mode": "LIVE",
                    "order": order.to_dict(),
                    "execution": wire_resp,
                }
            else:
                rejection = wire_resp.get("rejection_reason") or "Rejected by Kotak Neo Gateway"
                order.rejection_reason = rejection
                self.state_machine.transition_to(order, OrderStatus.REJECTED, reason=rejection)
                self.repository.save_order(order)

                audit_logger.record(
                    category=AuditCategory.ORDER,
                    action=AUDIT_ORDER_EXECUTION_FAILURE,
                    actor="order_execution_service",
                    correlation_id=get_correlation_id(),
                    request_id=get_request_id(),
                    details={"client_order_id": order.client_order_id, "rejection_reason": rejection},
                )

                return {
                    "success": False,
                    "mode": "LIVE",
                    "order": order.to_dict(),
                    "error": rejection,
                }

        except Exception as e:
            # THE GOLDEN RULE OF RECONCILIATION:
            # If wire transmission drops or times out, transition to RECONCILING, NEVER assume dead!
            self.circuit_breaker.record_failure(str(e))
            self.state_machine.transition_to(
                order,
                OrderStatus.RECONCILING,
                reason=f"Wire response timeout or network drop: {str(e)}",
            )
            self.repository.save_order(order)
            logger.warning(
                f"Order {order.client_order_id} entered RECONCILING state due to wire exception: {str(e)}",
                event="ORDER_ENTERED_RECONCILING",
            )
            return {
                "success": False,
                "mode": "LIVE",
                "order": order.to_dict(),
                "warning": "Order status unconfirmed; entered RECONCILING state for background resolution",
                "error": str(e),
            }

    # Internal Paper Order Execution
    def _execute_paper_order(self, order: Order) -> Dict[str, Any]:
        """Simulate execution in paper trading mode."""
        time.sleep(0.02)  # Simulate 20ms network latency
        paper_order_id = f"PAPER_{datetime.now().strftime('%m%d%H%M%S')}{random.randint(100, 999)}"
        order.broker_order_id = paper_order_id

        self.state_machine.transition_to(order, OrderStatus.ACKNOWLEDGED, reason="Paper Gateway Ingestion")
        self.repository.save_order(order)

        # Audit & Event
        audit_logger.record(
            category=AuditCategory.ORDER,
            action=AUDIT_ORDER_PLACE,
            actor="paper_execution_engine",
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"client_order_id": order.client_order_id, "broker_order_id": paper_order_id, "mode": "PAPER"},
        )
        publish(ORDER_ACKNOWLEDGED, {"order": order.to_dict()})

        # Spawn background poller (which simulates fill for paper orders)
        self.poller.spawn_async_poll(order)

        return {
            "success": True,
            "mode": "PAPER",
            "order": order.to_dict(),
            "execution": {"stat": "Ok", "nOrdNo": paper_order_id, "message": "Paper order placed"},
        }


# Global singleton instance
order_execution_service = OrderExecutionService()
