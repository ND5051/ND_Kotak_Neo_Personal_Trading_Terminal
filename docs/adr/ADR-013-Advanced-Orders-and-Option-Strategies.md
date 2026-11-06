# ADR-013: Advanced Multi-Leg Orders and Option Strategy Foundation

## Status
Accepted

## Context
Following Phase 8 (Order Execution Foundation) and Milestone M4, the terminal possesses single-order wire execution capabilities gated by `ExecutionMode` (`DISABLED`, `PAPER`, `LIVE`), atomic idempotency, circuit breakers, and asynchronous fill polling. However, active options trading requires managing multi-leg structures (Spreads, Straddles, Strangles, Condors, Butterflies, Covered Calls, Protective Puts) where orders cannot be treated as isolated transactions. Placing or managing multi-leg strategies presents severe systemic risks: partial execution asymmetry (naked short risk), double-click multi-leg duplication multiplying exposure, leg failure cascades, and complex margin dependencies. 

Phase 9 establishes the architectural foundation for multi-leg basket orders and option strategy definitions, enforcing structural validation, mathematical parity, two-tier idempotency, strict failure policies, exposure state tracking, and sequential/dependency execution models while prohibiting autonomous trading or signal generation.

## Decision
1. **Core Domain Models and Strategy Types:**
   Implement `Basket`, `BasketLeg`, `BasketExecution`, `BasketEventRecord` in `app/baskets/models/basket.py`. Define supported strategies (`CUSTOM`, `BULL_CALL_SPREAD`, `BEAR_PUT_SPREAD`, `LONG_STRADDLE`, `SHORT_STRADDLE`, `LONG_STRANGLE`, `SHORT_STRANGLE`, `IRON_CONDOR`, `IRON_BUTTERFLY`, `COVERED_CALL`, `PROTECTIVE_PUT`). System understands and validates structures; it does NOT generate trading signals.
2. **Mandatory Basket Idempotency (Two-Tier Protection):**
   - **Level 1 (Basket Level):** `client_basket_id` and SHA-256 `basket_idempotency_key` evaluated by `BasketIdempotencyManager` with in-memory TTL caching and a database unique constraint on `baskets.client_basket_id`. Prevents duplicate multi-leg container submissions from UI double-clicks or retry storms.
   - **Level 2 (Order Level):** Each dispatched leg receives an isolated `client_order_id` passed to Phase 8 `OrderExecutionService` for single-order broker wire idempotency.
3. **Basket Failure Policy (`BasketFailurePolicy`):**
   Supported policies: `ABORT_REMAINING`, `CONTINUE`, `COMPENSATING_ACTION`.
   **Phase 9 Default:** Strictly `ABORT_REMAINING`. If any leg fails or is rejected, immediate dispatch of subsequent legs is aborted, remaining unfilled legs are abandoned, filled legs remain intact, and human operator intervention is mandated. No automated compensating orders or autonomous hedge repairs are permitted.
4. **ExecutionMode Inheritance:**
   All multi-leg executions route strictly through `BasketExecutor -> OrderExecutionService -> KotakOrderAdapter`. Basket execution NEVER bypasses Phase 8 boundaries. Baskets inherit active `ExecutionMode`; execution is refused with HTTP 403 Forbidden if `ExecutionMode == DISABLED`.
5. **Reconciling Exposure Model (`BasketExposureState`):**
   Define `BasketExposureState` (`NEUTRAL`, `PARTIALLY_EXPOSED`, `FULLY_HEDGED`, `UNKNOWN`). Basket lifecycle status alone is insufficient to convey risk. If any single leg is in `RECONCILING` status, the parent Basket status must be `RECONCILING` (The Golden Rule) and its exposure state marked `PARTIALLY_EXPOSED` or `UNKNOWN`.
6. **Basket State Machine (`BasketState`):**
   Formal 9-state FSM (`DRAFT`, `VALIDATED`, `READY`, `EXECUTING`, `PARTIALLY_EXECUTED`, `EXECUTED`, `FAILED`, `CANCELLED`, `RECONCILING`) enforcing strict state transitions and immutable audit event logging.
7. **Basket Execution Modes (`BasketExecutionMode`):**
   Support `SEQUENTIAL` (Phase 9 Default), `PARALLEL`, and `DEPENDENCY` (DAG-based wing hedge execution before body short legs).
8. **Option Strategy Validation Engine:**
   Implement `StrategyValidationService` validating Indian exchange derivatives symbol syntax (`OPTION_SYMBOL_PATTERN`), lot size multiples (NIFTY 25, BANKNIFTY 15, FINNIFTY 25, MIDCPNIFTY 50), strike ladder relationships (debit spread strike ordering, Iron Condor wing symmetry), expiry parity across legs, and ₹0.05 tick modulo.
9. **Pre-Trade Multi-Leg Risk Controls:**
   Implement `BasketRiskService` verifying aggregate upfront margin (+10% buffer), gross notional exposure ceiling (₹20 Lakhs), daily drawdown floor (-₹20,000), and maximum concurrent open baskets (5).
10. **Relational Persistence & Alembic Migration:**
    Create migration `005_create_basket_tables.py` creating `baskets`, `basket_legs`, and `basket_events` tables with `strategy_version` and regulatory dual timestamps (`source_timestamp`, `retrieved_timestamp`).
11. **Event Bus & Audit Integration:**
    Register domain events (`BASKET_CREATED`, `BASKET_VALIDATED`, `BASKET_EXECUTION_STARTED`, `BASKET_LEG_FILLED`, `BASKET_RECONCILING`, `BASKET_COMPLETED`, `BASKET_FAILED`, `BASKET_CANCELLED`) and audit actions (`AUDIT_BASKET_CREATED`, `AUDIT_BASKET_VALIDATED`, `AUDIT_BASKET_EXECUTION_STARTED`, `AUDIT_BASKET_LEG_FILLED`, `AUDIT_BASKET_RECONCILIATION`, `AUDIT_BASKET_FAILED`, `AUDIT_BASKET_CANCELLED`).

## Consequences
- The terminal gains production-grade multi-leg and option strategy creation and execution capabilities.
- Multi-leg execution is strictly human-initiated; zero autonomous trading bots or signal generation.
- Default `SEQUENTIAL` execution and `ABORT_REMAINING` policy prevent catastrophic runaway execution.
- Two-tier idempotency protects operators from duplicate multi-leg strategy submissions.
- Strict `ExecutionMode` inheritance prevents accidental broker order placement.
