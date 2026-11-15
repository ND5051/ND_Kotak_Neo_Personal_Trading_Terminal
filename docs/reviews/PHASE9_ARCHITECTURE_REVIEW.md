# Phase 9 Architecture Review: Advanced Orders & Option Strategy Foundation

**Document Version:** 1.0.0  
**Phase:** Phase 9 (Advanced Orders & Option Strategy Foundation)  
**Target Milestone:** M5 Baseline  
**Status:** Completed & Validated  
**Date:** 2026-11-06  

---

## 1. Executive Summary

Phase 9 establishes the architectural foundation for multi-leg basket orders and option strategy definitions within the **Kotak Neo Personal Trading Terminal**. It introduces structural comprehension, mathematical validation, risk gating, and coordinated multi-leg execution across Indian derivatives exchanges (NSE / BSE), while strictly adhering to the project's constitutional mandates:

1. **Human-Initiated Only:** Execution is triggered solely by explicit human operator action. Autonomous trading bots, algorithmic signal generation, automated Greek hedging, and autonomous rollover are strictly prohibited and architecturally excluded.
2. **Defensive Order Hierarchy:** Multi-leg strategies route through Phase 8 `OrderExecutionService` $\to$ `KotakOrderAdapter`. Direct broker wire bypass is prohibited.
3. **ExecutionMode Inheritance:** Every basket strictly inherits the active global `ExecutionMode` (`DISABLED`, `PAPER`, `LIVE`). Wire submission is refused by default (`DISABLED`).
4. **The Golden Rule of Reconciliation:** If any leg transitions to `RECONCILING` (unconfirmed broker status), the parent Basket status transitions immediately to `RECONCILING` and its exposure state to `PARTIALLY_EXPOSED` or `UNKNOWN`.
5. **Default Safe Modes:** Default `BasketExecutionMode = SEQUENTIAL` and default `BasketFailurePolicy = ABORT_REMAINING`.

---

## 2. Core Domain Models & Architecture

```
+-------------------------------------------------------------------------------------------------------+
|                                    BASKET EXECUTION PIPELINE                                          |
|                                                                                                       |
|  [ Operator UI / REST API ]                                                                           |
|            |                                                                                          |
|            v                                                                                          |
|  [ BasketExecutionService ] <=================> [ BasketIdempotencyManager ] (Level 1 Deduplication)  |
|            |                                                                                          |
|            +---> [ StrategyValidationService ] (Structure, Expiry, Strikes, Lot Size, Tick Modulo)    |
|            |                                                                                          |
|            +---> [ BasketRiskService ] (Margins +10%, ₹20L Notional, -₹20k Drawdown, Max Baskets)     |
|            |                                                                                          |
|            +---> [ BasketExposureService ] (NEUTRAL, PARTIALLY_EXPOSED, FULLY_HEDGED, UNKNOWN)        |
|            |                                                                                          |
|            +---> [ BasketStateMachine ] (9-State Formal FSM with RECONCILING support)                 |
|            |                                                                                          |
|            v (Leg Dispatch Sequencing: SEQUENTIAL default / PARALLEL / DEPENDENCY)                    |
|  [ OrderExecutionService ] (Phase 8 Single-Order Gating, Level 2 Idempotency, MP Buffering)          |
|            |                                                                                          |
|            v (ExecutionMode Check: DISABLED -> Refused | PAPER -> Simulated | LIVE -> Wire)           |
|  [ KotakOrderAdapter ]                                                                                |
|            |                                                                                          |
|            v                                                                                          |
|  [ Kotak Neo API Gateway (Exchange Wire) ]                                                            |
+-------------------------------------------------------------------------------------------------------+
```

### 2.1. Domain Entities & Persisted Models
- **`Basket` (`app/baskets/models/basket.py`):** Aggregates strategy metadata (`StrategyType`), execution modes, failure policies, aggregate margin requirements, regulatory dual timestamps (`source_timestamp`, `retrieved_timestamp`), and child order legs.
- **`BasketLeg` (`app/baskets/models/basket.py`):** Individual leg model capturing contract specification, side, quantity, price, execution linkage (`order_id`, `broker_order_id`, `status`), and dependency markers (`depends_on_leg_index`).
- **`BasketModel`, `BasketLegModel`, `BasketEventModel` (`app/baskets/models/basket_entity.py`):** SQLAlchemy 2.0 entities backed by Alembic migration `005_create_basket_tables.py` (Revision `a1b2c3d4e5f6`), utilizing `selectin` relationship loading for high-performance non-blocking query execution.

### 2.2. Standard Supported Strategy Types
- `CUSTOM`: Arbitrary multi-leg combinations without symmetry constraints.
- `BULL_CALL_SPREAD`: Buy lower strike Call + Sell higher strike Call (same expiry).
- `BEAR_PUT_SPREAD`: Buy higher strike Put + Sell lower strike Put (same expiry).
- `LONG_STRADDLE` / `SHORT_STRADDLE`: Buy/Sell ATM Call + ATM Put (identical strike, same expiry).
- `LONG_STRANGLE` / `SHORT_STRANGLE`: Buy/Sell OTM Call + OTM Put (Call strike > Put strike, same expiry).
- `IRON_CONDOR`: Buy OTM Put + Sell higher OTM Put + Sell lower OTM Call + Buy higher OTM Call.
- `IRON_BUTTERFLY`: Buy OTM Put + Sell ATM Put + Sell ATM Call + Buy OTM Call.
- `COVERED_CALL`: Long Underlying Equity (CNC) + Sell OTM Call.
- `PROTECTIVE_PUT`: Long Underlying Equity (CNC) + Buy OTM Put.

---

## 3. Dedicated Architectural Audits

### 3.1. Audit Section 1: Basket Idempotency Architecture
The terminal enforces a strict two-tier idempotency hierarchy separating container deduplication from wire-level single order deduplication:

```
[ POST /api/baskets/execute ]
             |
             +---> [ Level 1: Basket Idempotency Check ]
             |     - Evaluated in `BasketIdempotencyManager`
             |     - Evaluates `client_basket_id` and SHA-256 `basket_idempotency_key`
             |     - Prevents duplicate multi-leg container submissions from UI double-clicks,
             |       browser retries, or network retry storms
             |     - Intercepts in-flight execution via atomic in-memory cache locks
             |     - Enforces database unique constraint on `baskets.client_basket_id`
             |     - Rejection: Returns `DUPLICATE_BASKET_REQUEST` with HTTP 409/400
             |
             +---> [ For Each Validated Leg ]
                   - Dispatches via `OrderExecutionService`
                   - Inherits Level 2: `client_order_id` in-memory lock & DB constraint
                   - Guarantees single-execution wire semantics per individual leg
```

**Verification:** Validated by `tests/unit/test_basket_idempotency.py` and `tests/unit/test_basket_execution_service.py::test_basket_level_idempotency_deduplication`. Immediate back-to-back execution calls on the same container return `DUPLICATE_BASKET_REQUEST` without submitting duplicate orders to the wire.

### 3.2. Audit Section 2: Basket Failure Policy (`ABORT_REMAINING`)
In multi-leg derivative trading, executing a broken strategy (e.g. wing hedge rejected while short body leg executes) introduces naked short exposure. 

Phase 9 establishes `BasketFailurePolicy.ABORT_REMAINING` as the strict non-configurable default:
- **Immediate Abort:** If `Leg[i]` fails validation or is rejected by the exchange or RMS, the executor terminates the execution pipeline immediately.
- **Subsequent Legs Never Dispatched:** `Leg[i+1]` through `Leg[N]` are never dispatched to the broker wire or order execution service.
- **State Transition:** The Basket transitions to `PARTIALLY_EXECUTED` (if earlier legs filled) or `FAILED` (if Leg 0 failed).
- **Zero Compensating Orders:** Phase 9 strictly prohibits automated compensating orders, auto-reversals, or autonomous repair trades. 
- **Human Mandatory Intervention:** The system flags the broken container and requires human operator action.

**Verification:** Validated by `tests/unit/test_basket_execution_service.py::test_basket_failure_policy_abort_remaining`. When Leg 1 fails RMS rejection in a 3-leg basket, Leg 0 remains filled, Leg 1 is marked rejected, and Leg 2 is confirmed never dispatched.

### 3.3. Audit Section 3: Exposure State Computation (`BasketExposureState`)
Basket lifecycle status alone (e.g. `EXECUTING` or `RECONCILING`) fails to communicate whether capital is exposed to asymmetric market risk. Phase 9 implements `BasketExposureState` managed by `BasketExposureService`:

| Lifecycle Status | Leg Realization | Basket Exposure State | Financial Meaning |
|---|---|---|---|
| `DRAFT` / `READY` | 0 legs filled | `NEUTRAL` | Zero capital or directional risk. |
| `EXECUTED` | All legs filled to ratio | `FULLY_HEDGED` | Defined risk boundaries mathematically established. |
| `PARTIALLY_EXECUTED` | Wing filled, body rejected | `PARTIALLY_EXPOSED` | Asymmetric or broken hedge; immediate human attention required. |
| `RECONCILING` | 1+ legs in unconfirmed wire state | `PARTIALLY_EXPOSED` / `UNKNOWN` | Cannot prove risk boundary until broker state resolves (The Golden Rule). |

**Scenario Demonstrations:**
1. **Iron Condor Partial Fill:** Leg 0 (Buy Put) FILLED, Leg 1 (Sell Put) FILLED, Leg 2 (Sell Call) RECONCILING, Leg 3 (Buy Call) UNFILLED. Basket status is `RECONCILING`; Exposure state is computed as `PARTIALLY_EXPOSED` because short upside call exposure is unhedged.
2. **Broken Spread:** Bull Call Spread Leg 0 (Buy Call) FILLED, Leg 1 (Sell Call) REJECTED. Basket is `PARTIALLY_EXECUTED`; Exposure state is `PARTIALLY_EXPOSED` (long naked call).

**Verification:** Validated by `tests/unit/test_basket_exposure_service.py` across 4 comprehensive multi-leg scenario tests.

### 3.4. Audit Section 4: Dependency Execution Model (`DEPENDENCY`)
For complex option structures where margin relief or risk protection depends on specific leg execution ordering, Phase 9 supports `BasketExecutionMode.DEPENDENCY`:
- **DAG Execution Hierarchy:** Legs specify `depends_on_leg_index`.
- **Root Wings First:** Long protective wings (e.g. Buy OTM Wings with `depends_on_leg_index=None`) are dispatched and confirmed `FILLED` first.
- **Dependent Legs Second:** Short body legs (e.g. Sell ATM Body with `depends_on_leg_index=0`) are dispatched only after their prerequisite wing leg confirms `FILLED`.
- **Dependency Interception:** If a prerequisite wing fails, dependent legs are never dispatched, completely eliminating naked short execution.

**Verification:** Validated by `tests/unit/test_basket_execution_service.py::test_dependency_execution_dag`. Order dispatch timestamps and client order IDs confirm roots executed prior to dependent legs.

### 3.5. Audit Section 5: ExecutionMode Inheritance Validation
Phase 9 enforces strict compliance with the Phase 8 Execution Mode architecture:
- **Default Mode:** `ExecutionMode.DISABLED`.
- **Strict Prohibition of Direct Broker Wire:** Baskets cannot call `KotakOrderAdapter` or broker APIs directly. All dispatches must pass through `OrderExecutionService`.
- **Wire Refusal:** When `ExecutionMode == DISABLED`, calling `execute_basket()` raises `ExecutionModeException` and returns HTTP 403 Forbidden (`EXECUTION_MODE_DISABLED`).
- **Paper vs Live Isolation:** Under `PAPER` mode, basket legs route to paper execution simulator with full idempotency and FSM progression. Under `LIVE` mode, orders route to the live Kotak Neo gateway.

**Verification:** Validated by `tests/unit/test_basket_execution_service.py::test_basket_execution_refused_when_disabled` and integration test `tests/integration/test_basket_routes.py::test_baskets_execute_refused_when_disabled`.

---

## 4. Verification & Test Suite Results

### 4.1. Phase 9 Unit & Integration Tests (29/29 PASSED)
```
tests/unit/test_basket_models.py::test_basket_models_initialization_and_serialization PASSED
tests/unit/test_basket_models.py::test_basket_status_predicates PASSED
tests/unit/test_basket_models.py::test_basket_event_record_serialization PASSED
tests/unit/test_basket_idempotency.py::test_basket_idempotency_acquire_and_duplicate PASSED
tests/unit/test_basket_idempotency.py::test_basket_idempotency_db_backing PASSED
tests/unit/test_basket_idempotency.py::test_compute_basket_hash_deterministic PASSED
tests/unit/test_basket_state_machine.py::test_basket_fsm_legal_progression PASSED
tests/unit/test_basket_state_machine.py::test_basket_fsm_reconciling_and_recovery PASSED
tests/unit/test_basket_state_machine.py::test_basket_fsm_illegal_transition_rejected PASSED
tests/unit/test_basket_exposure_service.py::test_exposure_state_neutral PASSED
tests/unit/test_basket_exposure_service.py::test_exposure_state_fully_hedged PASSED
tests/unit/test_basket_exposure_service.py::test_exposure_state_partially_exposed_broken_hedge PASSED
tests/unit/test_basket_exposure_service.py::test_exposure_state_reconciling_scenarios PASSED
tests/unit/test_strategy_validator.py::test_parse_option_symbol PASSED
tests/unit/test_strategy_validator.py::test_validate_bull_call_spread PASSED
tests/unit/test_strategy_validator.py::test_validate_iron_condor PASSED
tests/unit/test_strategy_validator.py::test_universal_invariants_expiry_and_lot_multiples PASSED
tests/unit/test_basket_execution_service.py::test_basket_execution_refused_when_disabled PASSED
tests/unit/test_basket_execution_service.py::test_basket_execution_sequential_paper_success PASSED
tests/unit/test_basket_execution_service.py::test_basket_failure_policy_abort_remaining PASSED
tests/unit/test_basket_execution_service.py::test_dependency_execution_dag PASSED
tests/unit/test_basket_execution_service.py::test_golden_rule_reconciling_exposure PASSED
tests/unit/test_basket_execution_service.py::test_basket_level_idempotency_deduplication PASSED
tests/integration/test_basket_routes.py::test_baskets_status_public_endpoint PASSED
tests/integration/test_basket_routes.py::test_baskets_create_and_detail PASSED
tests/integration/test_basket_routes.py::test_baskets_validate_dry_run PASSED
tests/integration/test_basket_routes.py::test_baskets_execute_refused_when_disabled PASSED
tests/integration/test_basket_routes.py::test_baskets_execute_success_in_paper_mode PASSED
tests/integration/test_basket_routes.py::test_baskets_cancel_endpoint PASSED
```

### 4.2. Full Regression Test Suite (166/166 PASSED)
The complete system regression test suite spanning Phases 1 through 9 executed cleanly:
```
============================ 166 passed in 12.80s =============================
```

---

## 5. Scope Exclusions & Compliance Verification

| Prohibited Scope Item | Verification / Defensive Mechanism | Status |
|---|---|---|
| **Autonomous Trading Bots** | All execution endpoints require authenticated user session (`@login_required`). Zero background auto-submission threads. | **Compliant** |
| **Signal Generation** | Strategy definitions are structural templates only. No indicator or price signal generators exist. | **Compliant** |
| **Automated Compensating Orders** | `BasketFailurePolicy.COMPENSATING_ACTION` prohibited. System only aborts remaining legs. | **Compliant** |
| **Auto-Hedging / Greeks Engine** | Greeks computation, volatility arbitrage, and dynamic delta hedging excluded from domain services. | **Compliant** |
| **Direct Broker Wire Bypass** | All basket legs route strictly through `OrderExecutionService`. Direct adapter wire calls are prohibited. | **Compliant** |
| **Default Execution Gating** | ExecutionMode defaults to `DISABLED`. Refuses submission unless explicitly flipped by operator. | **Compliant** |

---

## 6. Conclusion & Readiness for Milestone M5 Release

Phase 9 implementation is complete, architecturally sound, thoroughly tested, and compliant with all project constitutional constraints. The terminal now securely supports multi-leg option strategy basket creation, dry-run validation, pre-trade risk controls, sequential and dependency execution, and exposure state monitoring.

**Readiness Assessment:**
- Database Migrations: Applied (`005_create_basket_tables.py`)
- Unit & Integration Tests: 29/29 Passed
- Full System Regression: 166/166 Passed (100%)
- Architecture Review & ADR-013: Completed
- Ready for Milestone M5 Release Package.

