# ADR-011: Order Domain Foundation & Pre-Trade Risk Framework

## Status
Accepted

## Context
Following the completion of Milestone M2 (Phases 4–6), the terminal possesses streaming tick pipelines, market watch caches, Demat holdings tracking, open position monitoring, and real-time MTM valuation. To prepare for eventual trading operations, the terminal requires an authoritative Order Domain Foundation. In strict accordance with the Project Constitution, all financial execution logic (order placement, modification, cancellation, basket orders, option chain orders) is prohibited. The system must understand, validate, state-model, persist, and audit orders, but under no circumstances execute them.

## Decision
1. **Universal Order Domain Model:** Establish standardized `Order` and `TradeExecution` entities capturing Indian market requirements (`NSE`, `BSE`, `NFO`, `BFO`, `CDS`), supporting order types (`MARKET`, `LIMIT`, `SL`, `SL_M`), product codes (`CNC`, `MIS`, `NRML`), and dual timestamps (`source_timestamp` and `retrieved_timestamp`).
2. **Deterministic 12-State FSM:** Formalize all lifecycle states: `PENDING_VALIDATION`, `VALIDATED`, `SUBMITTED`, `ACKNOWLEDGED`, `TRIGGER_PENDING`, `PARTIALLY_FILLED`, `FILLED`, `REJECTED`, `CANCELLED`, `EXPIRED`, `FAILED`, and `RECONCILING`. Enforce strict transition guards where terminal states (`FILLED`, `REJECTED`, `CANCELLED`, `EXPIRED`, `FAILED`) are irreversible.
3. **The Golden Rule & RECONCILING State:** If an order status query to the broker returns an error or temporary omission, transition the order to `OrderStatus.RECONCILING`. An unconfirmed order is an UNKNOWN order, NEVER an assumed CANCELLED or REJECTED order.
4. **Relational Order Persistence:** Persist orders, immutable state transition events (`order_events`), and trade fills (`trade_executions`) in SQLite via Alembic migration `004_create_order_tables.py` (Revision `f8a9b0c1d2e3`).
5. **Pre-Flight Structural Validation:** Implement `OrderValidationService` enforcing the NSE 0.05 paise tick size rule (0.0025 for currency), contract lot size multiples, exchange freeze limits, Stop Loss trigger logic (Buy SL: price >= trigger, Sell SL: price <= trigger), and Market Protection (MP) buffering.
6. **Passive Pre-Trade Risk Controls:** Implement `OrderRiskService` checking capital margin sufficiency with a 5% safety buffer against Phase 6 `MarginService`, max single order value ceiling (₹5 Lakh), daily account drawdown kill switch against Phase 6 `PortfolioSummary`, short delivery block for equity CNC sales against Phase 6 `HoldingsService`, and open orders quota ($\le 50$).
7. **Read-Only & Dry-Run REST APIs:** Provide public `/api/orders/status` (`execution_enabled: false`), dry-run validation endpoint `POST /api/orders/validate`, and read-only order/trade book endpoints. Explicitly block execution endpoints (`POST /api/orders/place` returns `405 Method Not Allowed`).

## Consequences
- The terminal possesses complete semantic and mathematical comprehension of orders without premature execution risk.
- Zero risk of duplicate orders, orphaned trades, or invalid tick submissions.
- Total regulatory auditability across all state transitions and risk checks.
- Clean architectural bridge ready for future Phase 8 execution pipelines upon explicit authorization.
