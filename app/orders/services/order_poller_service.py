from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, List, Optional
import uuid

from app.broker.adapters.kotak_order_adapter import (
    kotak_order_adapter,
    KotakOrderAdapterInterface,
)
from app.core.audit import (
    audit_logger,
    AuditCategory,
    AUDIT_ORDER_DISCREPANCY,
    AUDIT_ORDER_EXECUTION_FILL,
    AUDIT_ORDER_RECONCILIATION,
)
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import (
    ORDER_CANCELLED,
    ORDER_FILLED,
    ORDER_PARTIALLY_FILLED,
    ORDER_RECONCILED,
    ORDER_REJECTED,
)
from app.logging.logger import get_logger
from app.orders.models.order import (
    Order,
    OrderStatus,
    OrderType,
    TradeExecution,
)
from app.orders.repositories.order_repository import (
    order_repository,
    OrderRepositoryInterface,
)
from app.orders.services.order_state_machine import (
    order_state_machine,
    OrderStateMachine,
)

logger = get_logger("app.orders.poller")


class OrderPollerService:
    """
    Asynchronous order status poller and state reconciliation worker.
    Tracks execution progression from Kotak Neo order reports, extracts
    true weighted average fill prices, records TradeExecution models,
    and updates the Order FSM and repository.
    """

    def __init__(
        self,
        adapter: Optional[KotakOrderAdapterInterface] = None,
        repository: Optional[OrderRepositoryInterface] = None,
        state_machine: Optional[OrderStateMachine] = None,
    ) -> None:
        self.adapter = adapter or kotak_order_adapter
        self.repository = repository or order_repository
        self.state_machine = state_machine or order_state_machine
        self._lock = threading.RLock()

    @staticmethod
    def _safe_float(val: Any, default: float = 0.0) -> float:
        if val is None:
            return default
        try:
            s = str(val).strip().replace(",", "")
            return float(s) if s else default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_int(val: Any, default: int = 0) -> int:
        if val is None:
            return default
        try:
            s = str(val).strip().replace(",", "")
            return int(float(s)) if s else default
        except (ValueError, TypeError):
            return default

    def _apply_broker_record(
        self,
        order: Order,
        record: Dict[str, Any],
        fallback_trade_price: float = 0.0,
    ) -> bool:
        """
        Apply a broker execution report record to update order FSM, prices, quantities, and trades.
        Returns True if the order reached a terminal state (FILLED, CANCELLED, REJECTED).
        """
        raw_st = str(record.get("ordSt") or record.get("status") or "").strip().lower()
        rej_rsn = str(record.get("rejRsn") or record.get("cancelRejectReason") or record.get("errMsg") or "")
        avg_prc = self._safe_float(
            record.get("avgPrc") or record.get("price") or record.get("trdPrc") or record.get("prc") or fallback_trade_price
        )
        fld_qty = self._safe_int(
            record.get("fldQty") or record.get("filledQuantity") or record.get("trdQty") or record.get("flQty")
        )

        logger.info(
            f"Applying broker record for {order.client_order_id} (broker_id: {order.broker_order_id}): "
            f"raw_st='{raw_st}', fld_qty={fld_qty}, avg_prc={avg_prc}"
        )

        # If order price is 0.0 (e.g. MARKET order) and we now have execution price, record it
        if avg_prc > 0 and (order.price == 0.0 or order.order_type == OrderType.MARKET):
            order.price = avg_prc

        # Extract broker total quantity if present
        broker_qty = self._safe_int(
            record.get("qty") or record.get("orderQuantity") or record.get("quantity") or 0
        )
        if broker_qty > 0 and broker_qty != order.quantity:
            logger.info(
                f"Syncing order quantity with broker authoritative quantity: "
                f"local={order.quantity} -> broker={broker_qty} for {order.client_order_id}"
            )
            order.quantity = broker_qty

        # Extract order type from broker if present
        broker_type_raw = str(record.get("prcTp") or record.get("orderType") or "").upper().strip()
        if broker_type_raw in ["MKT", "MARKET"]:
            order.order_type = OrderType.MARKET
        elif broker_type_raw in ["L", "LMT", "LIMIT"]:
            order.order_type = OrderType.LIMIT

        # Status checks
        is_filled_status = any(s in raw_st for s in ["complete", "traded", "filled", "executed"])
        is_cancelled_status = any(s in raw_st for s in ["cancel", "canc"])
        is_rejected_status = any(s in raw_st for s in ["reject", "rej", "failed"])
        is_partial_status = any(s in raw_st for s in ["partial", "partially"])

        # 1. Complete / Traded / Filled Status:
        # If exchange says COMPLETE or TRADED, or if filled quantity equals/exceeds total quantity:
        if is_filled_status or (fld_qty >= order.quantity and fld_qty > 0):
            # If broker marked complete and fld_qty > 0, align order.quantity to fld_qty
            if fld_qty > 0:
                order.quantity = fld_qty

            incremental_fill = max(0, order.quantity - order.filled_quantity)
            order.filled_quantity = order.quantity
            order.pending_quantity = 0
            order.average_price = avg_prc or order.price
            order.source_timestamp = datetime.now(timezone.utc).isoformat()
            order.retrieved_timestamp = datetime.now(timezone.utc).isoformat()
            order.assert_quantity_invariants()

            trade = None
            existing_trades = self.repository.get_trades(client_order_id=order.client_order_id)
            if incremental_fill > 0 or not existing_trades:
                trade_fill_qty = incremental_fill if incremental_fill > 0 else order.filled_quantity
                trade = TradeExecution(
                    trade_id=str(uuid.uuid4()),
                    client_order_id=order.client_order_id,
                    broker_order_id=order.broker_order_id,
                    trading_symbol=order.trading_symbol,
                    exchange_segment=order.exchange_segment,
                    fill_quantity=trade_fill_qty,
                    fill_price=order.average_price,
                    exchange_timestamp=datetime.now(timezone.utc).isoformat(),
                    retrieved_timestamp=order.retrieved_timestamp,
                )
                self.repository.record_trade_execution(trade)

            self.state_machine.transition_to(order, OrderStatus.FILLED, reason="Exchange Execution Complete")
            self.repository.save_order(order)

            audit_logger.record(
                category=AuditCategory.ORDER,
                action=AUDIT_ORDER_EXECUTION_FILL,
                actor="order_poller",
                correlation_id=get_correlation_id(),
                request_id=get_request_id(),
                details={
                    "client_order_id": order.client_order_id,
                    "broker_order_id": order.broker_order_id,
                    "fill_quantity": order.filled_quantity,
                    "fill_price": order.average_price,
                },
            )
            publish(ORDER_FILLED, {"order": order.to_dict(), "trade": trade.to_dict() if trade else {}})
            return True

        # 2. Rejected Status
        elif is_rejected_status:
            order.rejection_reason = rej_rsn or "Exchange / Broker RMS Rejection"
            self.state_machine.transition_to(
                order, OrderStatus.REJECTED, reason=order.rejection_reason
            )
            self.repository.save_order(order)
            publish(ORDER_REJECTED, {"order": order.to_dict(), "reason": order.rejection_reason})
            return True

        # 3. Cancelled Status
        elif is_cancelled_status:
            self.state_machine.transition_to(
                order, OrderStatus.CANCELLED, reason=rej_rsn or "Order Cancelled on Exchange"
            )
            self.repository.save_order(order)
            publish(ORDER_CANCELLED, {"order": order.to_dict()})
            return True

        # 4. Partial Execution Status (Only when resting and genuinely partially filled)
        elif is_partial_status or (0 < fld_qty < order.quantity):
            target_fld_qty = min(fld_qty, order.quantity)
            if fld_qty > order.quantity:
                logger.warning(
                    f"Broker reported partial fldQty {fld_qty} exceeds order.quantity {order.quantity} "
                    f"for {order.client_order_id}. Clamping to {order.quantity}."
                )
                audit_logger.record(
                    category=AuditCategory.ORDER,
                    action=AUDIT_ORDER_DISCREPANCY,
                    actor="order_poller",
                    correlation_id=get_correlation_id(),
                    request_id=get_request_id(),
                    details={
                        "client_order_id": order.client_order_id,
                        "broker_order_id": order.broker_order_id,
                        "reported_fld_qty": fld_qty,
                        "requested_quantity": order.quantity,
                        "action": "clamped_to_requested_quantity",
                    },
                )

            incremental_fill = max(0, target_fld_qty - order.filled_quantity)
            order.filled_quantity = target_fld_qty
            order.pending_quantity = max(0, order.quantity - order.filled_quantity)
            order.average_price = avg_prc or order.price
            order.source_timestamp = datetime.now(timezone.utc).isoformat()
            order.retrieved_timestamp = datetime.now(timezone.utc).isoformat()
            order.assert_quantity_invariants()

            if incremental_fill > 0:
                trade = TradeExecution(
                    trade_id=str(uuid.uuid4()),
                    client_order_id=order.client_order_id,
                    broker_order_id=order.broker_order_id,
                    trading_symbol=order.trading_symbol,
                    exchange_segment=order.exchange_segment,
                    fill_quantity=incremental_fill,
                    fill_price=order.average_price,
                    exchange_timestamp=datetime.now(timezone.utc).isoformat(),
                    retrieved_timestamp=order.retrieved_timestamp,
                )
                self.repository.record_trade_execution(trade)

            self.state_machine.transition_to(
                order, OrderStatus.PARTIALLY_FILLED, reason="Partial Execution Fill"
            )
            self.repository.save_order(order)
            publish(ORDER_PARTIALLY_FILLED, {"order": order.to_dict()})
            return False

        return False

    def poll_order_status(
        self,
        order: Order,
        max_attempts: int = 5,
        initial_delay_sec: float = 0.1,
    ) -> Order:
        """
        Poll Kotak Neo order execution report to extract terminal or fill status.
        Uses exponential backoff with jitter.
        """
        if not order.broker_order_id:
            return order

        broker_id = str(order.broker_order_id).strip()
        delay = initial_delay_sec

        for attempt in range(1, max_attempts + 1):
            if order.is_terminal():
                return order
            time.sleep(delay)
            if order.is_terminal():
                return order
            try:
                records = self.adapter.get_order_report(broker_id)
                if not records:
                    delay = min(delay * 1.5, 1.0)
                    continue

                for record in records:
                    done = self._apply_broker_record(order, record)
                    if done:
                        return order

            except Exception as e:
                err_str = str(e).lower()
                if "no such table" in err_str or "closed file" in err_str:
                    return order
                logger.warning(f"Poller attempt {attempt} failed for {broker_id}: {str(e)}")

            delay = min(delay * 1.5, 1.0)

        return order

    def spawn_async_poll(self, order: Order, max_attempts: int = 6) -> None:
        """Spawn dedicated background daemon thread to poll order without blocking REST caller."""
        thread = threading.Thread(
            target=self.poll_order_status,
            args=(order, max_attempts, 0.1),
            name=f"OrderPoller-{order.client_order_id[:8]}",
            daemon=True,
        )
        thread.start()

    def reconcile_unconfirmed_orders(self) -> Dict[str, Any]:
        """
        Reconcile orders stuck in RECONCILING, SUBMITTED, or open resting status.
        Upholds The Golden Rule of Order Reconciliation.
        """
        with self._lock:
            all_orders = self.repository.find_orders(limit=100)
            candidates = [o for o in all_orders if o.is_open() and o.broker_order_id]

            reconciled_count = 0
            discrepancy_count = 0

            # Step 1: Batch fetch the entire day's order book from Kotak Neo
            broker_book_map: Dict[str, Dict[str, Any]] = {}
            try:
                book = self.adapter.get_order_book()
                for rec in book:
                    n_ord = str(rec.get("nOrdNo") or rec.get("ordNo") or "").strip()
                    if n_ord:
                        broker_book_map[n_ord] = rec
                logger.info(f"Reconciliation: fetched {len(broker_book_map)} orders from broker order book")
            except Exception as e:
                logger.warning(f"Failed to fetch daily order book for batch reconciliation: {e}")

            # Step 2: Batch fetch trade book to resolve execution fill prices if needed
            trade_price_map: Dict[str, float] = {}
            try:
                trades = self.adapter.get_trade_book()
                for t in trades:
                    n_ord = str(t.get("nOrdNo") or t.get("ordNo") or "").strip()
                    prc = self._safe_float(t.get("trdPrc") or t.get("price") or t.get("avgPrc"))
                    if n_ord and prc > 0:
                        trade_price_map[n_ord] = prc
            except Exception as e:
                logger.debug(f"Trade book lookup during reconciliation: {e}")

            # Step 3: Match each local open candidate against broker state
            for order in candidates:
                broker_id = str(order.broker_order_id).strip()
                prev_status = order.status
                fallback_px = trade_price_map.get(broker_id, 0.0)

                if broker_id in broker_book_map:
                    self._apply_broker_record(order, broker_book_map[broker_id], fallback_trade_price=fallback_px)
                else:
                    self.poll_order_status(order, max_attempts=2, initial_delay_sec=0.1)

                if order.status != prev_status:
                    reconciled_count += 1
                    publish(ORDER_RECONCILED, {
                        "client_order_id": order.client_order_id,
                        "broker_order_id": order.broker_order_id,
                        "previous_status": prev_status.value,
                        "reconciled_status": order.status.value,
                    })
                    audit_logger.record(
                        category=AuditCategory.ORDER,
                        action=AUDIT_ORDER_RECONCILIATION,
                        actor="order_reconciler",
                        correlation_id=get_correlation_id(),
                        request_id=get_request_id(),
                        details={
                            "client_order_id": order.client_order_id,
                            "previous_status": prev_status.value,
                            "reconciled_status": order.status.value,
                        },
                    )
                else:
                    discrepancy_count += 1
                    audit_logger.record(
                        category=AuditCategory.ORDER,
                        action=AUDIT_ORDER_DISCREPANCY,
                        actor="order_reconciler",
                        correlation_id=get_correlation_id(),
                        request_id=get_request_id(),
                        details={
                            "client_order_id": order.client_order_id,
                            "broker_order_id": order.broker_order_id,
                            "status": order.status.value,
                        },
                    )

            return {
                "total_candidates": len(candidates),
                "reconciled": reconciled_count,
                "discrepancies": discrepancy_count,
            }


# Global singleton instance
order_poller_service = OrderPollerService()
