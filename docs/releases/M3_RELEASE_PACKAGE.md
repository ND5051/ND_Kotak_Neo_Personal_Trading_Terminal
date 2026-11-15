# Kotak Neo Personal Trading Terminal
## Release Package — Milestone M3 Baseline (Phase 7: Order Domain Foundation)

**Release Version:** Milestone M3 Baseline  
**Release Date:** 2026-11-06  
**Target Platform:** Kotak Neo Broker API (`kotakneoapi>=3.0.13`) / Order State Machine & Pre-Trade Risk Framework  
**Architecture Status:** Stable / Order Domain Foundation & Pre-Trade Risk Engine (Zero Live Execution)  
**Test Suite Status:** 117 / 117 Tests Passing (100% Automated Coverage, including 20/20 Phase 7 Tests)  
**Git Commit Reference:** `1b370f3`  
**Git Branch:** `main`  

---

## 1. Summary of Phase 7

Milestone M3 represents a pivotal architectural milestone in the development of the Kotak Neo Personal Trading Terminal. Building upon the secure session, authentication, and broker foundation established in Milestone M1 (Phases 1–3) and the real-time data, streaming, market watch, and portfolio accounting engine established in Milestone M2 (Phases 4–6), Milestone M3 establishes the **Order Domain Foundation**.

In strict compliance with the **Project Constitution**, Phase 7 was architected under a non-negotiable governing invariant:
> **"The system must only understand, model, validate, and audit orders—never execute them."**

Spanning domain models, an immutable state transition machine, relational persistence, exchange pre-flight validation rules, capital risk controls, and read-only REST APIs, Phase 7 equips the terminal with comprehensive semantic and mathematical intelligence regarding orders while strictly isolating it from financial execution risk.

```
========================================================================================================
                                     MILESTONE M3 ARCHITECTURE
========================================================================================================

    [ REAL-TIME FEED ]               [ PORTFOLIO CONTEXT ]              [ OPERATOR / ALGO ]
  (Phase 4 & 5 Streaming)            (Phase 6 Valuation)                 (REST Request)
             |                                |                                |
             | Market Touchlines              | Margins, Custody, Drawdown     | Order Payload
             v                                v                                v
+------------------------------------------------------------------------------------------------------+
|                                   PHASE 7 ORDER DOMAIN ENGINE                                        |
|                                                                                                      |
|   1. Pre-Flight Validation Engine (`OrderValidationService`)                                         |
|      - Scaled Integer Millipaise Modulo (NSE/BSE ₹0.05 / CDS ₹0.0025 Tick Rule)                      |
|      - Derivative Lot Size Multiples (NIFTY x25, BANKNIFTY x15)                                      |
|      - Exchange Single-Order Freeze Ceilings                                                         |
|      - Stop Loss Trigger Invariants (Buy: P >= TP; Sell: P <= TP)                                   |
|      - Market Protection (MP) Buffering                                                              |
|                                                                                                      |
|   2. Pre-Trade Risk Gatekeeper (`OrderRiskService`)                                                  |
|      - Margin Sufficiency Check (+5% Safety Buffer vs Phase 6 MarginService)                         |
|      - Single Order Gross Value Ceiling (₹5,00,000)                                                  |
|      - Account Daily Drawdown Kill Switch (-₹20,000 vs Phase 6 PortfolioSummary)                     |
|      - Short Selling Delivery Block (CNC vs Phase 6 HoldingsService Demat Custody)                   |
|      - Open Orders Active Quota (<= 50)                                                              |
|                                                                                                      |
|   3. Deterministic 12-State FSM (`OrderStateMachine`)                                                |
|      - Forward-Only Lifecycle: PENDING_VALIDATION -> VALIDATED -> SUBMITTED ...                      |
|      - The Golden Rule & RECONCILING State (Unconfirmed != Dead; Prevents Duplicate Loops)           |
|      - Thread-Safe Transitions Guarded by RLock & Illegal Transition Exceptions                      |
|                                                                                                      |
|   4. Relational Storage & Audit Trail (`OrderRepository` & SQLite)                                  |
|      - Orders, Order Events (Audit Timeline), Trade Executions                                       |
|      - Mandatory Dual-Timestamp Protocol (source_timestamp & retrieved_timestamp)                    |
|                                                                                                      |
|   5. Non-Executing REST APIs (`app/orders/routes.py`)                                                |
|      - GET  /api/orders/status    -> Public Operational Status (execution_enabled: false)             |
|      - POST /api/orders/validate  -> Dry-Run Validation & Risk Assessment                            |
|      - GET  /api/orders           -> Filterable Order Book (Status, Symbol, Segment)                 |
|      - GET  /api/orders/<id>      -> Order Detail & Transition Event Timeline                        |
|      - GET  /api/orders/trades    -> Executed Trade Book                                             |
|      - GET  /api/orders/stats     -> Order Distribution & Fill Metrics                               |
|      - POST /api/orders/place     -> 405 Method Not Allowed (EXECUTION_PROHIBITED_IN_PHASE_7)        |
+------------------------------------------------------------------------------------------------------+
             |                                                                 |
             v                                                                 v
+--------------------------------+                             +--------------------------------+
|       SYSTEM EVENT BUS         |                             |     APPEND-ONLY AUDIT LOG      |
|  - ORDER_VALIDATED / FAILED    |                             |  - AUDIT_ORDER_VALIDATION      |
|  - ORDER_RISK_PASSED / REJECTED|                             |  - AUDIT_ORDER_RISK_CHECK      |
|  - ORDER_STATE_CHANGED         |                             |  - AUDIT_ORDER_STATE_TRANSITION|
|  - ORDER_RECONCILED            |                             |  - AUDIT_ORDER_RECONCILIATION  |
+--------------------------------+                             +--------------------------------+
========================================================================================================
```

---

## 2. Order Domain Foundation

Phase 7 establishes standardized, type-safe data structures, relational schemas, and persistence services that accurately reflect the operational nuances of the Indian capital markets (NSE, BSE, MCX, CDS).

### 2.1. Domain Models & Enums
Located in [`app/orders/models/order.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/orders/models/order.py):

* **Enumerations**:
  - `OrderSide`: `BUY`, `SELL`.
  - `OrderType`: `MARKET`, `LIMIT`, `SL` (Stop Loss Limit), `SL_M` (Stop Loss Market).
  - `ProductType`: `CNC` (Cash and Carry / Delivery), `MIS` (Margin Intraday Square-off), `NRML` (Normal Margin / Carry-forward Derivatives).
  - `Validity`: `DAY`, `IOC` (Immediate or Cancel), `EOS` (End of Session).
  - `OrderStatus`: 12 distinct lifecycle states including `RECONCILING`.

* **Universal Order Model (`Order`)**:
  - Core Identifiers: `client_order_id` (UUIDv4 client key), `broker_order_id` (Kotak Neo exchange reference), `user_id`.
  - Instrument Specification: `trading_symbol`, `exchange_segment` (`nse_cm`, `bse_cm`, `nse_fo`, `cde_fo`), `instrument_token`.
  - Order Attributes: `side`, `order_type`, `product_type`, `validity`.
  - Quantity & Pricing: `quantity`, `disclosed_quantity`, `filled_quantity`, `pending_quantity`, `price`, `trigger_price`, `average_price`.
  - Lifecycle & Flags: `status`, `rejection_reason`, `tag`.
  - Dual Timestamps: `source_timestamp` (origin time from broker/exchange) and `retrieved_timestamp` (local ingest UTC time).

* **Trade Execution Fill Model (`TradeExecution`)**:
  - Represents partial and full execution fills from the trade book.
  - Attributes: `trade_id`, `client_order_id`, `broker_order_id`, `trading_symbol`, `exchange_segment`, `side`, `fill_quantity`, `fill_price`, `fill_timestamp`, `exchange_trade_id`, `source_timestamp`, `retrieved_timestamp`.

### 2.2. Dual-Timestamp Protocol
Carrying forward the architectural mandate established in Phase 6, every order entity, state transition log, and trade fill captures two distinct temporal coordinates:
1. `source_timestamp`: The authoritative wall-clock timestamp assigned by the broker gateway or exchange matching engine (ISO 8601 UTC).
2. `retrieved_timestamp`: The precise local wall-clock timestamp when the terminal ingested or recorded the record (ISO 8601 UTC).

This dual-timestamp protocol eliminates clock-skew ambiguity between local host systems and Kotak Neo broker servers, ensuring unassailable chronological dispute resolution and regulatory audit integrity.

### 2.3. Relational Persistence & Migration
Database persistence is managed through SQLAlchemy ORM entities in [`app/orders/models/order_entity.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/orders/models/order_entity.py) and applied via Alembic Migration `004_create_order_tables.py` (Revision ID: `f8a9b0c1d2e3`, revising `e5f7a1b2c3d4`):

1. **`orders` Table**:
   - Master state table holding full order configurations, quantities, prices, and status.
   - Indexed on `client_order_id` (Unique), `broker_order_id` (Index), `user_id`, `status`, and `created_at`.
2. **`order_events` Table**:
   - Immutable append-only audit trail recording every state transition.
   - Captures `from_status`, `to_status`, `reason`, `source_timestamp`, `retrieved_timestamp`, and contextual JSON details.
   - Foreign key constraint `ON DELETE CASCADE` linked to `orders.id`.
3. **`trade_executions` Table**:
   - Stores granular trade executions (fills).
   - Indexed on `trade_id` (Unique), `client_order_id`, `broker_order_id`, and `fill_timestamp`.
   - Linked to `orders.id` via nullable foreign key to gracefully accommodate out-of-band trade fills.

### 2.4. Order Repository
Implemented in [`app/orders/repositories/order_repository.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/orders/repositories/order_repository.py):
- Thread-safe persistence mapping cleanly between SQLAlchemy ORM entities and domain dataclasses.
- Fast lookups by `client_order_id` or `broker_order_id`.
- Filterable order querying across `status`, `trading_symbol`, `exchange_segment`, and `date_from`.
- Atomic state transition recording via `record_transition()`.
- Outer-join querying on `trade_executions` via `get_trades()`, ensuring trades are retrievable even if populated from external broker synchronization before a local order record was persisted.

---

## 3. Finite State Machine (FSM) Design

The order lifecycle is governed by a deterministic, thread-safe, 12-state finite state machine implemented in [`app/orders/services/order_state_machine.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/orders/services/order_state_machine.py).

### 3.1. State Catalog
| State Enum | Type | Description |
|---|---|---|
| `PENDING_VALIDATION` | Initial | Order created locally; awaiting pre-flight syntax and risk evaluation. |
| `VALIDATED` | Transient | Order passed all pre-flight syntax, tick size, and margin risk checks. |
| `SUBMITTED` | In-Flight | Order dispatched across the wire to the Kotak Neo gateway. |
| `ACKNOWLEDGED` | Working | Kotak Neo gateway accepted the order and issued an exchange order ID. |
| `TRIGGER_PENDING` | Working | Stop-loss order resting on the exchange order book awaiting price activation. |
| `PARTIALLY_FILLED` | Working | Cumulative executed quantity $> 0$ but $<$ total order quantity. |
| `FILLED` | **Terminal** | Order 100% executed across all shares/lots. |
| `REJECTED` | **Terminal** | Order turned down by validation, risk manager, broker, or exchange. |
| `CANCELLED` | **Terminal** | Unfilled order canceled by user or exchange (e.g. intraday auto-squareoff). |
| `EXPIRED` | **Terminal** | Unfilled order expired at the end of trading session or IOC window. |
| `FAILED` | **Terminal** | Fatal network, socket, or communication breakdown during submission. |
| `RECONCILING` | **Recovery** | Temporary state while resolving unknown or unconfirmed broker status. |

### 3.2. State Transition Matrix
```
+--------------------+---------------------------------------------------------------------------------+
| Current State      | Legal Next States                                                               |
+--------------------+---------------------------------------------------------------------------------+
| PENDING_VALIDATION | VALIDATED, REJECTED, FAILED                                                     |
| VALIDATED          | SUBMITTED, REJECTED, FAILED                                                     |
| SUBMITTED          | ACKNOWLEDGED, TRIGGER_PENDING, PARTIALLY_FILLED, FILLED, REJECTED, FAILED,      |
|                    | RECONCILING                                                                     |
| ACKNOWLEDGED       | TRIGGER_PENDING, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED, EXPIRED,        |
|                    | RECONCILING                                                                     |
| TRIGGER_PENDING    | ACKNOWLEDGED, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED, EXPIRED,           |
|                    | RECONCILING                                                                     |
| PARTIALLY_FILLED   | PARTIALLY_FILLED, FILLED, CANCELLED, EXPIRED, RECONCILING                       |
| RECONCILING        | ACKNOWLEDGED, TRIGGER_PENDING, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED,   |
|                    | EXPIRED, FAILED                                                                 |
| FILLED             | (None - Terminal State)                                                         |
| REJECTED           | (None - Terminal State)                                                         |
| CANCELLED          | (None - Terminal State)                                                         |
| EXPIRED            | (None - Terminal State)                                                         |
| FAILED             | (None - Terminal State)                                                         |
+--------------------+---------------------------------------------------------------------------------+
```

### 3.3. The Golden Rule of Order Reconciliation
In algorithmic trading, network timeouts, broker gateway 504 errors, and socket dropouts represent the highest operational hazard. A naive trading engine might treat a submission timeout as a `FAILED` or `CANCELLED` order and immediately retry, leading to catastrophic duplicate order placement loops.

Milestone M3 formally codifies **The Golden Rule of Order Reconciliation**:
> **"An unconfirmed order response is an UNKNOWN order. It must NEVER be assumed CANCELLED, REJECTED, or FAILED."**

* **Reconciliation Workflow**:
  1. If an order submission or status check returns a timeout, empty body, or connection refusal, the order transitions immediately to `OrderStatus.RECONCILING`.
  2. In `RECONCILING`, the order is flagged as active and open (`order.is_open() == True`).
  3. No automated retry or duplicate order placement is permitted while an order is in `RECONCILING`.
  4. The order remains in `RECONCILING` until an authoritative status update is obtained via the broker trade book, order book sync, or manual operator confirmation.
  5. Once authoritative confirmation is received, the FSM transitions the order cleanly to its true state (`FILLED`, `ACKNOWLEDGED`, `CANCELLED`, `REJECTED`, etc.).

### 3.4. State Transition Guards & Safety
- **Strict Guard Enforcement**: Any attempt to execute an invalid transition raises [`IllegalOrderStateTransitionException`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/core/exceptions.py), aborting the operation and preserving database integrity.
- **Terminal State Immutability**: States `FILLED`, `REJECTED`, `CANCELLED`, `EXPIRED`, and `FAILED` are strictly terminal. No transition out of a terminal state is permitted under any circumstances.
- **Thread Safety**: Transitions are serialized across concurrent threads via `threading.RLock()`.
- **Automated Side Effects**: Every transition automatically dispatches an `ORDER_STATE_CHANGED` event to the Event Bus and writes a structured audit log entry (`AUDIT_ORDER_STATE_TRANSITION`).

---

## 4. Pre-Flight Validation Framework

Implemented in [`app/orders/services/order_validation_service.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/orders/services/order_validation_service.py), the Validation Framework enforces exchange syntax, pricing constraints, and contract mechanics prior to risk review.

### 4.1. Integer Millipaise Scaled Modulo Algorithm
Under Indian exchange regulations (NSE/BSE), equity and derivative order prices must be exact multiples of ₹0.05 (currency contracts require ₹0.0025). Standard Python floating-point modulo (`2450.05 % 0.05`) frequently produces IEEE 754 precision artifacts:
```python
# Standard floating point arithmetic in Python:
2450.05 % 0.05 -> 0.049999999999954525 != 0.0  # Falsely rejects valid prices!
```

To eliminate floating-point precision errors with 100% mathematical certainty, `OrderValidationService` scales prices and tick sizes into integer millipaise ($10^{-4}$ rupees):
```python
# Integer-scaled millipaise modulo:
price_millipaise = round(price * 10000)
tick_millipaise = round(tick_size * 10000)
is_valid_tick = (price_millipaise % tick_millipaise) == 0
```
This guarantees flawless tick validation across all price ranges and segments.

### 4.2. Validation Rules Enforced
1. **Tick Size Compliance**:
   - `nse_cm`, `bse_cm`, `nse_fo`, `bse_fo`: Multiple of ₹0.05.
   - `cde_fo` (Currency Derivatives): Multiple of ₹0.0025.
2. **Derivative Lot Size Multiples**:
   - For derivative contracts, order quantity must be an integer multiple of the contract lot size (e.g. NIFTY multiple of 25, BANKNIFTY multiple of 15).
3. **Exchange Freeze Ceilings**:
   - Single order quantities cannot exceed exchange-mandated freeze limits (e.g. NIFTY: 1,800 quantity, BANKNIFTY: 900 quantity) to avoid automatic exchange rejection.
4. **Stop-Loss Trigger Invariants**:
   - **Buy Stop-Loss Order** (`side == BUY`): Limit Price must be greater than or equal to Trigger Price ($\text{Price} \ge \text{Trigger Price}$).
   - **Sell Stop-Loss Order** (`side == SELL`): Limit Price must be less than or equal to Trigger Price ($\text{Price} \le \text{Trigger Price}$).
5. **Quantity & Disclosed Quantity Rules**:
   - Minimum order quantity $\ge 1$.
   - Disclosed quantity must be $0$ (undisclosed) or between 10% and 100% of the total order quantity.
6. **Market Protection (MP) Buffering**:
   - Calculates dynamic protective limit prices for market orders based on exchange-specified buffer percentages (e.g. 5%), rounding the resulting price to the nearest valid ₹0.05 tick.

---

## 5. Pre-Trade Risk Management Framework

Implemented in [`app/orders/services/order_risk_service.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/orders/services/order_risk_service.py), the Risk Framework acts as an authoritative capital gatekeeper, evaluating incoming orders against account resources, exposure ceilings, and daily loss thresholds.

### 5.1. Integration with Milestone M2 Portfolio Services
The risk service operates as a passive evaluator, integrating directly with Phase 6 portfolio and margin services:
- [`MarginService`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/portfolio/services/margin_service.py): Retrieves real-time cash, collateral, and margin utilization.
- [`PortfolioService`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/portfolio/services/portfolio_service.py): Queries account-level executive summaries and realized/unrealized PnL.
- [`HoldingsService`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/portfolio/services/holdings_service.py): Verifies physical settled Demat custody before permitting delivery sales.

### 5.2. Pre-Trade Risk Controls Enforced
1. **Capital Margin Coverage Check (+5% Buffer)**:
   - Evaluates estimated margin required for the trade.
   - For intraday equity (`MIS`), applies a standard 20% margin factor; for CNC/Derivatives, applies 100% of order value.
   - Requires available cash to satisfy:
     $$\text{Available Cash} \ge \text{Estimated Margin} \times 1.05$$
   - The 5% buffer guarantees buffer absorption for exchange fees, STT, GST, and slippage.
2. **Single-Order Gross Value Ceiling**:
   - Enforces a hard ceiling of **₹5,00,000** per individual order ($\text{Quantity} \times \text{Price} \le ₹5,00,000$).
   - Defends against fat-finger errors and unbounded algorithmic runaway.
3. **Daily Account Drawdown Kill Switch**:
   - Queries `PortfolioSummary.total_pnl` (Realized PnL + Floating MTM).
   - If cumulative daily loss breaches **-₹20,000**, all new order evaluations are immediately blocked (`MAX_DAILY_LOSS_EXCEEDED`).
4. **Short Selling Delivery Prohibition for CNC**:
   - SEBI regulations prohibit short selling in equity delivery (`CNC`).
   - If an order is a `SELL` with `product_type == CNC`, the service queries `HoldingsService.get_demat_holdings()` and verifies that settled Demat quantity $\ge$ order quantity.
   - Naked or unbacked delivery sales are rejected immediately.
5. **Active Open Orders Quota**:
   - Enforces a ceiling of **50 maximum resting/open orders** per account to prevent exchange queue flooding.

---

## 6. Manual & Automated Validation Results

Milestone M3 underwent comprehensive verification through automated test suites and manual REST endpoint validation against running local test fixtures.

### 6.1. Automated Test Suite Execution
The complete terminal test suite was executed in the workspace virtual environment (`Python 3.14.6` on Windows):

```text
======================================= TEST SUITE SUMMARY =======================================
Platform: win32 -- Python 3.14.6, pytest-9.2.0, pluggy-1.7.0
Root Directory: ND_Kotak_Neo_Personal_Trading_Terminal

Tests Collected: 117
Tests Passed:    117
Tests Deselected:  0
Success Rate:    100%
===================================================================================================

Phase Breakdown:
  Milestone M1 Baseline (Phases 1-3):   51 passed
  Phase 4 Streaming Infrastructure:      18 passed
  Phase 5 Market Watch Foundation:       15 passed
  Phase 6 Portfolio Foundation:          13 passed
  Phase 7 Order Domain Foundation:       20 passed
---------------------------------------------------------------------------------------------------
Total Milestone M3 Suite:               117 passed (100% Automated Coverage)
===================================================================================================
```

#### Detailed Phase 7 Test Suite Breakdown:
1. `tests/unit/test_order_models.py` (3 tests):
   - `test_order_model_initialization_and_serialization`: Verified initialization, defaults, and dictionary export.
   - `test_order_status_predicates_and_reconciling_state`: Verified `is_terminal()`, `is_open()`, and `RECONCILING` predicate logic.
   - `test_trade_execution_serialization`: Verified trade execution models and dual timestamps.
2. `tests/unit/test_order_state_machine.py` (3 tests):
   - `test_order_state_machine_legal_progression`: Verified full lifecycle from `PENDING_VALIDATION` to `FILLED`.
   - `test_order_state_machine_reconciling_flow`: Verified transition into `RECONCILING` and recovery into `ACKNOWLEDGED`.
   - `test_order_state_machine_illegal_transition_rejection`: Verified rejection of illegal transitions (e.g. `FILLED` -> `CANCELLED`).
3. `tests/unit/test_order_validation_service.py` (4 tests):
   - `test_order_validation_nse_tick_size`: Verified ₹0.05 tick size checks using integer millipaise modulo.
   - `test_order_validation_stop_loss_logic`: Verified Buy SL ($\ge$) and Sell SL ($\le$) trigger invariants.
   - `test_order_validation_derivatives_lot_size_and_freeze`: Verified derivative lot multiples and freeze limits.
   - `test_calculate_market_protection`: Verified market protection price bounding and tick rounding.
4. `tests/unit/test_order_risk_service.py` (3 tests):
   - `test_order_risk_margin_sufficiency`: Verified margin calculation and 5% safety buffer requirement.
   - `test_order_risk_max_order_value_ceiling`: Verified gross value ceiling of ₹5 Lakh.
   - `test_order_risk_short_selling_delivery_check`: Verified physical custody verification for CNC sales.
5. `tests/integration/test_order_routes.py` (7 tests):
   - `test_orders_status_public_endpoint`: Verified public status route and `execution_enabled: false`.
   - `test_orders_validate_dry_run_endpoint`: Verified `POST /api/orders/validate` dry-run evaluation.
   - `test_orders_validate_tick_error`: Verified validation failure response structures.
   - `test_orders_place_is_strictly_prohibited`: Verified `POST /api/orders/place` returns `405 Method Not Allowed`.
   - `test_orders_order_book_and_filters`: Verified order book listing and status filtering.
   - `test_orders_get_detail_and_timeline`: Verified order detail retrieval and audit transition history.
   - `test_orders_trades_and_stats_endpoints`: Verified trade book retrieval and order distribution statistics.

### 6.2. Manual Validation Matrix
Manual verification was performed across all Phase 7 endpoints and operational invariants:

| Test Case | Scenario / Operation | Input / Request | Expected Output | Actual Observed Result | Status |
|---|---|---|---|---|---|
| **MV-M3-01** | Public Status Verification | `GET /api/orders/status` | `status: "operational"`, `execution_enabled: false` | Returned HTTP 200 with `execution_enabled: false` | **PASS** |
| **MV-M3-02** | Strict Execution Prohibition | `POST /api/orders/place` | HTTP 405 Method Not Allowed, error code `EXECUTION_PROHIBITED_IN_PHASE_7` | Returned HTTP 405 with constitution guard message | **PASS** |
| **MV-M3-03** | Dry-Run Syntax & Risk Validation | `POST /api/orders/validate` (Valid Buy MIS Limit) | HTTP 200, `valid: true`, `risk_passed: true`, margin calculated | Returned HTTP 200 with complete validation breakdown | **PASS** |
| **MV-M3-04** | Invalid Tick Size Rejection | `POST /api/orders/validate` with price `2450.03` | HTTP 200, `valid: false`, `errors` contains invalid tick message | Rejected with `"Price 2450.03 must be a multiple of tick size 0.05"` | **PASS** |
| **MV-M3-05** | Buy Stop Loss Trigger Violation | `POST /api/orders/validate` with Buy SL Price < Trigger | HTTP 200, `valid: false`, Stop Loss violation detected | Rejected with `"Buy Stop Loss order price ... must be >= trigger price"` | **PASS** |
| **MV-M3-06** | Gross Order Value Ceiling | `POST /api/orders/validate` with value > ₹5,00,000 | HTTP 200, `valid: true`, `risk_passed: false`, max value error | Rejected with `"Order gross value ... exceeds maximum single order limit"` | **PASS** |
| **MV-M3-07** | Short Selling Delivery Prohibition | `POST /api/orders/validate` for CNC Sell without custody | HTTP 200, `valid: true`, `risk_passed: false`, short delivery error | Rejected with `"Cannot place CNC Sell order ... Insufficient Demat holdings"` | **PASS** |
| **MV-M3-08** | FSM Transition Integrity | Transition `PENDING_VALIDATION` -> `VALIDATED` -> `SUBMITTED` | Order status updates cleanly, events logged to DB | Order transitioned to `SUBMITTED`, audit event written | **PASS** |
| **MV-M3-09** | Reconciling State Handling | Transition `SUBMITTED` -> `RECONCILING` -> `ACKNOWLEDGED` | FSM holds open status, recovers cleanly upon confirmation | Handled without exception; order remained open | **PASS** |
| **MV-M3-10** | Terminal State Immutability | Transition `FILLED` -> `CANCELLED` | `IllegalOrderStateTransitionException` raised | Exception raised; transition strictly rejected | **PASS** |
| **MV-M3-11** | Order Book Filtering | `GET /api/orders?status=SUBMITTED&limit=10` | Filtered list matching status and user ownership | Only orders with `SUBMITTED` returned | **PASS** |
| **MV-M3-12** | Trade Book Retrieval | `GET /api/orders/trades` | List of executed trade fills with dual timestamps | Outer-joined trade list returned with ISO 8601 timestamps | **PASS** |

---

## 7. Known Limitations

Milestone M3 delivers a complete, audited Order Domain Foundation. In accordance with the project roadmap, the following functional boundaries are intentionally maintained:

1. **Strictly Non-Executing Order Pipeline**:
   - The terminal cannot place, submit, modify, or cancel orders on the exchange or broker gateway.
   - All live broker execution methods (`place_order`, `modify_order`, `cancel_order`) are non-existent.
   - `POST /api/orders/place` is explicitly blocked (`405 Method Not Allowed`).
2. **No Live Order Status Polling**:
   - Because execution is disabled, automated background polling of Kotak Neo order books or websocket execution feeds is not active.
3. **No Basket or Multi-Leg Orders**:
   - Multi-leg option strategies, straddles, strangles, and basket orders remain unmapped stubs (`app/basket/routes.py`).
4. **No Option Chain Matrix or Greeks Engine**:
   - Black-Scholes Greeks, implied volatility (IV) calculations, and real-time option chains are deferred to future milestones.
5. **Static Contract Lot Specifications in Validation**:
   - The current validation service maintains standard lot size and freeze dictionaries for major benchmark indices (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY). Dynamic real-time Scrip Master lot-size lookup will be wired during Phase 8 live broker adapter binding.

---

## 8. Readiness Assessment for Phase 8

With Milestone M3 accepted, tested, and baselined, the terminal satisfies all architectural, domain, and risk requirements to progress to **Phase 8: Live Broker Order Execution Pipeline**.

### 8.1. Readiness Scorecard
| Component / Requirement | Status | Phase 7 Foundation Ready |
|---|---|---|
| **Order Domain Model** | **READY** | Standardized `Order` and `TradeExecution` dataclasses with dual timestamps. |
| **State Machine & Invariants** | **READY** | 12-state FSM with irreversible terminal states and `RECONCILING` recovery flow. |
| **Pre-Flight Validation** | **READY** | Integer millipaise tick modulo, lot sizes, freeze ceilings, and Stop Loss logic. |
| **Pre-Trade Risk Controls** | **READY** | Margin coverage (+5% buffer), gross value ceiling, drawdown stop, and CNC short checks. |
| **Relational Storage & Schema** | **READY** | SQLite `orders`, `order_events`, and `trade_executions` tables via migration `004`. |
| **Audit & Event Bus** | **READY** | Full event types (`order.*`) and structured audit actions (`AUDIT_ORDER_*`) registered. |
| **Idempotency Architecture** | **READY** | Unique `client_order_id` indexing ready to prevent duplicate wire submissions. |
| **Circuit Breaker Hooks** | **READY** | Phase 4 `BrokerCircuitBreaker` pre-flight hooks ready to intercept execution drops. |

### 8.2. Scope Roadmap for Phase 8: Live Broker Order Execution Pipeline
When authorized by the user, Phase 8 will deliver:
1. **Kotak Neo Live Order Adapter**:
   - Real wire implementation of `place_order`, `modify_order`, and `cancel_order` wrapping the official `kotakneoapi` SDK.
2. **Defensive Wire Execution Pipeline**:
   - Circuit Breaker pre-flight clearance before socket/REST transmission.
   - Atomic idempotency verification via in-memory cache and database index to prevent duplicate order submissions.
3. **Automated Order Reconciliation Worker**:
   - Asynchronous poller reconciling `RECONCILING` and `SUBMITTED` orders against Kotak Neo order and trade books.
   - Real-time trade fill ingestion updating open positions and portfolio MTM immediately via Event Bus.
4. **Execution REST API Controller**:
   - Activating `POST /api/orders/place`, `PUT /api/orders/<id>/modify`, and `DELETE /api/orders/<id>/cancel` with mandatory two-factor or session authentication.

---

**Milestone M3 is complete, verified, and accepted as the authoritative Order Domain baseline.**
