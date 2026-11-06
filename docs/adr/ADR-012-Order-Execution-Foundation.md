# ADR-012: Order Execution Foundation & Defensive Broker Routing

## Status
Accepted

## Context
Following the completion of Phase 7 (Order Domain Foundation) and Milestone M3 Baseline, the terminal possesses comprehensive semantic, mathematical, and relational comprehension of orders, FSM lifecycle transitions, Stop Loss invariants, tick modulo, and pre-trade risk controls. However, order execution remained disabled. To transition into an active trading terminal, Phase 8 establishes the live order execution pipeline connecting internal models to the Kotak Neo Broker API (`kotakneoapi>=3.0.13`). In financial systems, sending wire orders is the highest risk surface; the architecture requires defensive gating, atomic idempotency, circuit breaker clearance, execution mode controls, and asynchronous reconciliation.

## Decision
1. **Mandatory Execution Mode Gating (`ExecutionMode`):**
   Implement `ExecutionMode` enum (`DISABLED`, `PAPER`, `LIVE`) managed by `ExecutionModeManager`. The default mode is strictly `DISABLED`. All execution services, routes, and wire adapters must refuse order placement, modification, and cancellation unless the mode is explicitly set to `PAPER` or `LIVE`. In `DISABLED` mode, calls are rejected with `ExecutionModeException` (HTTP 403 Forbidden).
2. **Kotak Neo Live Order Execution Adapter (`KotakOrderAdapter`):**
   Encapsulate official SDK methods (`place_order`, `modify_order`, `cancel_order`, `order_report`, `trade_report`). Normalize polymorphic responses (`stat: "Ok"`, `nOrdNo`, `errMsg`, `rejRsn`). Provide high-fidelity simulated fallback for mock environments.
3. **Atomic Idempotency Deduplication:**
   Implement `IdempotencyManager` providing an in-memory atomic TTL cache combined with the database unique constraint on `orders.client_order_id`. Duplicate requests are intercepted before wire submission and return the existing order record without submitting duplicate orders.
4. **Market Protection (MP) on Market Orders:**
   Intercept pure market orders and convert them into aggressive buffered limit orders (default 2% equity, 5% options) snapped to ₹0.05 ticks to defend against flash crash slippage and RMS rejections on illiquid contracts.
5. **Clean Broker-Side Stop Loss Orders:**
   Place native exchange-resting `order_type="SL"` orders with `price == trigger_price` to eliminate artificial slippage.
6. **Asynchronous Execution Status Poller & Reconciler:**
   Implement `OrderPollerService` polling `get_order_report(broker_order_id)` with exponential backoff and jitter to extract true weighted average fill prices (`avg_price`), update FSM states (`FILLED`, `PARTIALLY_FILLED`, `REJECTED`, `CANCELLED`), and record `TradeExecution` entries.
7. **The Golden Rule & RECONCILING State:**
   If a wire transmission times out or encounters network drops, transition the order immediately to `OrderStatus.RECONCILING`. An unconfirmed order is an UNKNOWN order, NEVER an assumed CANCELLED or REJECTED order.
8. **Emergency Kill-Switch (`cancel_all_orders`):**
   Provide `POST /api/orders/cancel-all` to mass-cancel all open resting orders concurrently within rate limits.
9. **Event Bus & Audit Integration:**
   Register execution events (`ORDER_SUBMITTED`, `ORDER_ACKNOWLEDGED`, `ORDER_MODIFIED`, `ORDER_EMERGENCY_CANCELLED`, `EXECUTION_MODE_CHANGED`) and audit actions (`AUDIT_ORDER_PLACE`, `AUDIT_ORDER_MODIFY`, `AUDIT_ORDER_CANCEL`, `AUDIT_ORDER_EXECUTION_FILL`, `AUDIT_EMERGENCY_CANCEL_ALL`, `AUDIT_EXECUTION_MODE_CHANGED`).

## Consequences
- The terminal transitions from order-aware to safely order-executing.
- Default `DISABLED` mode prevents accidental live capital exposure during restarts or testing.
- Single-execution semantics guaranteed via atomic idempotency.
- Slippage minimized via Market Protection buffering and clean SL pricing.
- Complete regulatory and operational audit trail across every wire transmission.
