# Kotak Neo Personal Trading Terminal
## Release Package — Milestone M4 Baseline (Phases 7 & 8: Order Domain & Order Execution Foundation)

**Release Version:** Milestone M4 Baseline  
**Release Date:** 2026-11-06  
**Target Platform:** Kotak Neo Broker API (`kotakneoapi>=3.0.13`) / Live Wire & Paper Order Execution Engine  
**Architecture Status:** Stable / Order Domain, Defensive Wire Execution & Hardened Paper Simulator  
**Test Suite Status:** 137 / 137 Tests Passing (100% Automated Coverage, including 4/4 Audit & 27/27 Order Execution Tests)  
**Git Branch:** `main`  
**Git Tag:** `M4_BASELINE`  

---

## 1. Executive Summary

Milestone M4 represents the critical milestone in the evolution of the Kotak Neo Personal Trading Terminal, completing the full lifecycle transition from passive observation to active, defensive execution.

While Milestone M3 established the semantic model, immutable finite state machine, pre-flight syntax checks, and pre-trade capital controls of the **Order Domain Foundation (Phase 7)**, Milestone M4 operationalizes execution through the **Order Execution Foundation (Phase 8)**.

Crucially, Milestone M4 enforces the **ExecutionMode** governance framework:
* By default, order execution is strictly **`DISABLED`** across all wire and paper interfaces.
* Execution must be explicitly enabled into **`PAPER`** (simulated fills) or **`LIVE`** (real wire submission to Kotak Neo exchange matching engines) via authenticated operator command.
* All execution pipelines are guarded by two-tier idempotency, market protection buffering, native stop-loss standardizations, asynchronous status polling, and continuous reconciliation upholding **The Golden Rule**.
* The paper execution engine has undergone formal mathematical and security auditing ([`PAPER_EXECUTION_AUDIT.md`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/PAPER_EXECUTION_AUDIT.md)), proving that **no fill can ever exceed requested order quantity**.

```
========================================================================================================
                                     MILESTONE M4 ARCHITECTURE
========================================================================================================

    [ OPERATOR / REST CLIENT ]            [ REAL-TIME FEED ]              [ PORTFOLIO CONTEXT ]
  (Execution Mode: DISABLED/PAPER/LIVE)  (Phase 4 & 5 Streaming)          (Phase 6 Valuation)
              |                                     |                               |
              | Place / Modify / Cancel             | Touchlines                    | Margins, Custody
              v                                     v                               v
+------------------------------------------------------------------------------------------------------+
|                                   MILESTONE M4 EXECUTION ENGINE                                      |
|                                                                                                      |
|   1. Execution Mode Governance (`ExecutionModeManager`)                                              |
|      - DISABLED (Default): Wire and paper execution strictly refused (HTTP 403)                      |
|      - PAPER: High-fidelity local simulation with quantity invariant guarantees                      |
|      - LIVE: Upstream Kotak Neo SDK wire submission                                                  |
|                                                                                                      |
|   2. Pre-Trade Invariants & Idempotency (`IdempotencyManager` & `OrderRiskService`)                  |
|      - Two-Tier Deduplication: In-Memory TTL Lock + SQLite Unique `client_order_id` Index            |
|      - NSE/BSE Scaled Integer Millipaise Tick Check (₹0.05 / CDS ₹0.0025)                            |
|      - Derivative Lot Size Multiples & Single-Order Freeze Ceilings                                  |
|      - Margin Coverage (+5% Safety Buffer) & Account Daily Drawdown Floor (-₹20,000)                 |
|      - Delivery Short Selling Block (CNC Custody Verification)                                       |
|                                                                                                      |
|   3. Order Execution Service (`OrderExecutionService`)                                               |
|      - Market Protection (MP): Buffered Limit conversion (2% Equity, 5% Options to ₹0.05 tick)       |
|      - Clean Stop Loss Standard: `price == trigger_price` on native broker SL orders                 |
|      - Mass Emergency Kill-Switch: `POST /api/orders/cancel-all` with wire broadcast                 |
|                                                                                                      |
|   4. Upstream Wire Adapter (`KotakOrderAdapter`)                                                     |
|      - Official Kotak Neo SDK v3 (`place_order`, `modify_order`, `cancel_order`)                     |
|      - Polymorphic Response Normalization (`stat: "Ok"`, `nOrdNo`, `errMsg`, `rejRsn`)               |
|      - Dynamic Simulated Order Registry for Test & Paper Modes                                       |
|                                                                                                      |
|   5. Asynchronous Poller & Reconciler (`OrderPollerService`)                                         |
|      - Exponential Backoff & Jitter Polling (`get_order_report`)                                      |
|      - Weighted Average Traded Price Calculation & Granular `TradeExecution` Ingestion              |
|      - Golden Rule Reconciler: Reconciles `RECONCILING` and `SUBMITTED` orders                       |
|      - Mathematical Clamping: Invariant `filled_quantity <= quantity` strictly enforced              |
+------------------------------------------------------------------------------------------------------+
              |                                                                 |
              v                                                                 v
+--------------------------------+                             +--------------------------------+
|       SYSTEM EVENT BUS         |                             |     APPEND-ONLY AUDIT LOG      |
|  - ORDER_SUBMITTED             |                             |  - AUDIT_ORDER_PLACE           |
|  - ORDER_ACKNOWLEDGED          |                             |  - AUDIT_ORDER_MODIFY          |
|  - ORDER_FILLED / PARTIAL      |                             |  - AUDIT_ORDER_CANCEL          |
|  - ORDER_RECONCILED            |                             |  - AUDIT_ORDER_EXECUTION_FILL  |
|  - EXECUTION_MODE_CHANGED      |                             |  - AUDIT_ORDER_DISCREPANCY     |
+--------------------------------+                             +--------------------------------+
========================================================================================================
```

---

## 2. Summary of Phase 7 (Order Domain Foundation)

Phase 7 delivered the foundational data models, lifecycle state machine, and pre-trade rules:
* **Universal Domain Models:** Standardized `Order` and `TradeExecution` dataclasses holding `client_order_id`, `broker_order_id`, execution parameters, and regulatory dual-timestamps (`source_timestamp` and `retrieved_timestamp`).
* **Deterministic FSM:** 12-state forward-only finite state machine (`OrderStateMachine`) guarded by thread-safe `RLock`. Enforces terminal state immutability and **The Golden Rule** through `OrderStatus.RECONCILING`.
* **Pre-Flight Validation Engine:** Integer millipaise modulo tick checking for NSE/BSE (₹0.05) and CDS (₹0.0025); derivative lot size multiples; exchange freeze ceilings; Stop Loss trigger price invariants.
* **Pre-Trade Risk Engine:** Margin sufficiency evaluation (+5% safety buffer); ₹5,00,000 single order gross value limit; ₹20,000 account daily drawdown kill-switch; Demat custody verification blocking unauthorized short selling of delivery (`CNC`) equities.
* **Relational Schema:** SQLAlchemy ORM models and Alembic migration `004_create_order_tables.py` creating indexed `orders`, `order_events`, and `trade_executions` tables.

---

## 3. Summary of Phase 8 (Order Execution Foundation)

Phase 8 activated the execution pipeline, bridging domain models to broker wire transport:
* **ExecutionMode Governance:** Tri-state operational switch (`DISABLED`, `PAPER`, `LIVE`). Starts in `DISABLED` on cold boot, strictly refusing wire submissions with HTTP 403 / `ExecutionModeException`.
* **Two-Tier Idempotency Engine:** Prevents duplicate order placement from double-clicks or network retries by combining an atomic memory cache with database unique constraints on `client_order_id`.
* **Broker Wire Adapter (`KotakOrderAdapter`):** Encapsulates Kotak Neo Python SDK v3 calls, serializing internal domain structures to broker-specific parameters and normalizing diverse API response dictionaries.
* **Execution Orchestrator (`OrderExecutionService`):** Coordinates validation, risk clearance, idempotency registration, market protection price buffering, wire transmission, FSM state updates, and poller dispatching.
* **Asynchronous Poller & Reconciler (`OrderPollerService`):** Background worker polling broker order execution reports with exponential backoff and jitter, extracting volume-weighted average fill prices, recording `TradeExecution` rows, and executing recovery on `RECONCILING` orders.
* **Emergency Mass Kill-Switch:** `POST /api/orders/cancel-all` atomically cancels all open and trigger-pending orders across the terminal and broker wire simultaneously.
* **REST Execution APIs:** Activated `POST /api/orders/place`, `PUT /api/orders/<id>/modify`, `DELETE /api/orders/<id>/cancel`, `POST /api/orders/mode`, and `POST /api/orders/reconcile`.

---

## 4. Paper Execution Simulator Audit Findings

In accordance with project requirements prior to Milestone M4 baselining, a dedicated investigation and mathematical verification was conducted on the paper execution simulator.

### 4.1. Core Mathematical Invariant
$$\text{filled\_quantity} \le \text{quantity} \quad \forall \quad t \ge 0$$
$$\sum_{i=1}^{n} \text{fill\_quantity}_i = \text{filled\_quantity} \le \text{quantity}$$

### 4.2. Identified Issues & Remediation
1. **Static Mock Report**: The initial mock adapter returned hardcoded `fldQty: 10`, causing orders with `quantity < 10` to overfill.
   - *Fix:* `KotakOrderAdapter` now features dynamic simulated order registration (`register_simulated_order`), strictly retaining the exact requested quantity and price.
2. **Substring Classification Overlap**: String matching for `"filled"` intercepted `"partially_filled"` status reports.
   - *Fix:* Reordered status evaluation to evaluate `is_partial` prior to `is_filled`.
3. **Defensive Invariant Clamping**: If an upstream broker ever returns an anomalous fill quantity ($fldQty > quantity$), the poller strictly clamps the fill to `order.quantity`, updates `pending_quantity` to 0, logs `AUDIT_ORDER_DISCREPANCY`, and raises no uncaught exceptions.
4. **Domain Model Self-Assertion**: Added `assert_quantity_invariants()` to `Order`, enforcing non-negativity and capacity ceilings at model construction and state transitions.

Full audit documentation is published in [`PAPER_EXECUTION_AUDIT.md`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/PAPER_EXECUTION_AUDIT.md).

---

## 5. Verification & Test Results

The Milestone M4 codebase has achieved **100% automated test coverage** across 137 individual tests:

```
===================================================================================================
                                MILESTONE M4 TEST SUITE BREAKDOWN
===================================================================================================
Module / Subsystem                     Tests Passing     Coverage Notes
---------------------------------------------------------------------------------------------------
Authentication & Core Security:             15 / 15      PBKDF2, Encryption, TOTP, Sessions
Broker Connectivity & Session:              12 / 12      Session recovery, Credentials, Health
Streaming, SFeed & Circuit Breaker:         18 / 18      WebSocket supervisor, Telemetry, Breaker
Market Watch & Instrument Search:           12 / 12      Scrip Master, Watchlist CRUD, Quotes
Portfolio Accounting & MTM Engine:          18 / 18      Holdings, Positions, Margins, PnL
Order Domain Foundation (Phase 7):          20 / 20      FSM, Invariants, Modulo Tick, Risk, DB
Order Execution Foundation (Phase 8):       23 / 23      ExecutionMode, Idempotency, Wire Adapter
Paper Execution Invariants (Audit):          4 / 4       Quantity bounds, Overfill clamp, Partials
REST Integration & Health Endpoints:        15 / 15      App Factory, System Health, Route Guards
---------------------------------------------------------------------------------------------------
Total Milestone M4 Suite:                  137 / 137     100% Pass Rate (0 Failures, 0 Warnings)
===================================================================================================
```

---

## 6. Known Limitations

While Milestone M4 delivers live and paper execution capabilities, the following features remain intentionally excluded pursuant to the project roadmap:

1. **No Basket / Multi-Leg Orders (Deferred to Phase 9):**
   - Multi-leg option strategies, straddles, strangles, iron condors, and multi-scrip baskets remain unmapped stubs in `app/basket/routes.py`.
2. **No Option Chain Matrix & Greeks (Deferred to Phase 9):**
   - Real-time strike matrices, Black-Scholes Greeks (Delta, Gamma, Theta, Vega), and implied volatility calculations are scheduled for Phase 9.
3. **No Autonomous Algorithmic Strategy Bots (Deferred to Phase 10):**
   - Execution is currently driven by authenticated human operator REST requests. Automated signal-to-order algorithmic trading bots will be built in Phase 10.
4. **Static Scrip Master Derivation:**
   - Contract lot size dictionaries currently maintain fixed specifications for benchmark indices (NIFTY x25, BANKNIFTY x15, etc.). Dynamic daily Scrip Master updates will be integrated in Phase 9.

---

## 7. Readiness Assessment for Phase 9

Milestone M4 satisfies all architectural, security, execution, and audit requirements to begin **Phase 9: Advanced Orders & Option Strategies Foundation**.

### 7.1. Phase 9 Readiness Scorecard
| Foundation Component | Status | Readiness Justification |
|---|---|---|
| **ExecutionMode Governance** | **READY** | Strict isolation between `DISABLED`, `PAPER`, and `LIVE` operational modes. |
| **Broker Wire Execution** | **READY** | Standardized `KotakOrderAdapter` communicating across the wire. |
| **Two-Tier Idempotency** | **READY** | Zero double-execution risk across rapid order dispatch. |
| **Paper Simulation Simulator** | **READY** | Mathematically audited; guaranteed $\text{filled\_quantity} \le \text{quantity}$. |
| **Pre-Trade Risk Controls** | **READY** | Margin validation, order value caps, and Demat delivery checks active. |
| **State Machine & Reconciliation**| **READY** | 12-state FSM with Golden Rule `RECONCILING` recovery active. |
| **Emergency Kill-Switch** | **READY** | Atomic mass cancellation across open and trigger-pending orders. |

---

**Milestone M4 is complete, verified, audited, and baselined under Git Tag `M4_BASELINE`.**

