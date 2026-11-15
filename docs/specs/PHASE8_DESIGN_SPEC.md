# Phase 8 Architectural Design Specification
## Order Execution Foundation

**Document Version:** 1.0.0  
**Phase:** Phase 8 — Order Execution Foundation  
**Target Milestone:** Milestone M4 (Live Execution Baseline)  
**Baseline Dependencies:** 
- Milestone M1 Baseline Locked (`M1_BASELINE`, commit `4d9341a`)
- Milestone M2 Baseline Locked (`M2_BASELINE`, commit `c4d30e6`)
  - Phase 4: WebSocket Supervisor & Streaming Infrastructure
  - Phase 5: Market Watch Foundation & Real-Time Price Engine
  - Phase 6: Portfolio Foundation, Margins & MTM Engine
- Milestone M3 Baseline Locked (`M3_BASELINE`, commit `22dd3c8`)
  - Phase 7: Order Domain Foundation, FSM, Pre-Flight Validation & Risk Framework
**Status:** Architectural Design (Pre-Implementation)  
**Implementation Constraint:** **Design specification only — Zero production implementation code generated in this phase**.  

---

## Scope Exclusions (Strict Project Governance)

In compliance with the **PROJECT_CONSTITUTION** and explicit user directives, the following features remain **strictly prohibited** from Phase 8:

- ❌ **No Basket / Multi-Leg Orders**: Zero multi-leg strategy executors, straddle/strangle spread builders, or margin-benefit sequential order routers (deferred to Phase 9).
- ❌ **No Option Chain Matrix & Greeks Engine**: Zero automated options execution from option chain matrices, Open Interest (OI) scrapers, or Black-Scholes Greeks calculators (deferred to Phase 9).
- ❌ **No Autonomous Algorithmic Strategy Bots**: Zero unattended automated bots or automated signal triggers (e.g. Supertrend, EMA crossover bots). Phase 8 provides the live broker execution pipeline for manual and semi-automated orders.

> [!IMPORTANT]
> **Core Architectural Objective of Phase 8:**  
> Phase 8 transitions the terminal from an **order-aware** system (Phase 7) into an **order-executing** system. It safely connects Phase 7's deterministic Order FSM, validation engine, risk controls, and repository to the live Kotak Neo Broker API (`kotakneoapi>=3.0.13`), enabling defensive order placement, modification, cancellation, execution fill polling, and state reconciliation while enforcing strict idempotency, circuit breaker protection, and execution mode gating.

### Mandatory Execution Mode Architecture (`ExecutionMode`)
To prevent accidental capital exposure or unintended order placement during system initialization, staging, or automated testing, all execution services are governed by an authoritative `ExecutionMode` gate:

- **`ExecutionMode.DISABLED` (Default)**:
  - Strict system-wide prohibition of order execution.
  - All calls to `place_order()`, `modify_order()`, `cancel_order()`, and `cancel_all()` are **immediately rejected** with `ExecutionModeException` (HTTP 403 Forbidden).
  - No wire transmission is permitted. The terminal starts in `DISABLED` mode by default.
- **`ExecutionMode.PAPER`**:
  - Simulated paper trading execution.
  - Generates realistic mock broker order IDs, simulates network latency (20ms–50ms), logs transitions to the database, records simulated trade fills, and drives downstream positions and MTM updates without transmitting packets to the live broker gateway.
- **`ExecutionMode.LIVE`**:
  - Authoritative live execution connecting directly to the Kotak Neo Broker API gateway.
  - Requires explicit runtime activation or environment configuration (`EXECUTION_MODE=LIVE`).
  - Dispatches signed order requests to the live exchange matching engine.

> **Execution Invariant**: Every execution service, route handler, and wire adapter **must refuse** wire submission unless the active execution mode explicitly permits it (`ExecutionMode.LIVE` or `ExecutionMode.PAPER`). Under `ExecutionMode.DISABLED`, zero wire calls can ever be made.

---

## 1. Executive Summary & Architectural Objectives

Milestone M3 established an authoritative Order Domain Foundation: the terminal has complete semantic, mathematical, and relational comprehension of orders, Stop Loss invariants, tick modulo, and margin limits. However, in Milestone M3, order execution was strictly disabled (`POST /api/orders/place` returned `405 Method Not Allowed`).

Phase 8 designs the **Live Order Execution Pipeline**. In financial trading systems, transmitting execution payloads across the wire is the ultimate high-risk surface. An unhandled exception, network glitch, or double-click can cause catastrophic financial loss through duplicate fills, runaway loops, or unintended market exposure.

The primary architectural objectives of Phase 8 are:

1. **Kotak Neo Live Order Execution Adapter (`KotakOrderAdapter`)**:
   - Encapsulate the official Kotak Neo SDK (`kotakneoapi` / `neo-api-client >= 3.0.13`) order methods: `place_order()`, `modify_order()`, `cancel_order()`, and `order_report()`.
   - Translate internal `Order` domain models to Kotak Neo wire parameters and vice versa.
   - Defensively normalize polymorphic responses (`stat: "Ok"`, `nOrdNo`, `rejRsn`, `data`, `result`).

2. **Defensive Execution & Idempotency Framework**:
   - Guarantee single-execution semantics via atomic idempotency keys (`client_order_id`).
   - Pre-flight `BrokerCircuitBreaker` inspection to immediately block order dispatch if the broker gateway is unstable.
   - Enforce rate-limiting and request pacing to prevent `429 Too Many Requests` API locks.

3. **Defensive Order Types & Market Protection (MP)**:
   - Prohibit raw naked market orders (`MKT`) on illiquid contracts to prevent flash crash slippage.
   - Implement aggressive buffered Limit orders with dynamic Market Protection (MP) percentage buffers snapped to ₹0.05 ticks.
   - Place native broker-side Stop Loss Limit orders (`order_type="SL"`) with identical limit and trigger prices (`price == trigger_price`) to prevent artificial slippage.

4. **Execution Status Polling & Asynchronous Reconciliation**:
   - Establish a resilient execution status poller: `place_order` returning `200 OK` only confirms gateway ingestion; the poller queries `order_report` to track exchange acceptance, rejections, and true weighted average fill prices (`avg_price`).
   - Automatically reconcile orders stuck in `RECONCILING` or `SUBMITTED` state, upholding **The Golden Rule of Order Reconciliation**.

5. **State Reconciliation & Downstream Sync**:
   - Upon execution fills, instantly update the local order book and dispatch `ORDER_FILLED` / `ORDER_PARTIALLY_FILLED` events.
   - Wire event listeners to Phase 6 `PositionsService` and `MTMEngine` to update open commitments and floating PnL in real time without waiting for slow REST polls.

6. **Order Execution REST API Suite**:
   - `POST /api/orders/place`: Full end-to-end validated and risk-checked order placement.
   - `PUT /api/orders/<id>/modify`: Live price, quantity, and trigger price amendment.
   - `DELETE /api/orders/<id>/cancel`: Individual order cancellation.
   - `POST /api/orders/cancel-all`: Emergency mass cancellation of all working orders.

---

## 2. High-Level Architecture & End-to-End Execution Flow

```
========================================================================================================
                                  PHASE 8 ORDER EXECUTION ARCHITECTURE
========================================================================================================

  [ OPERATOR / ALGO REQUEST ]
              |
              | POST /api/orders/place
              v
+------------------------------------------------------------------------------------------------------+
| 1. AUTHENTICATION & IDEMPOTENCY GATEWAY                                                              |
|    - Verify Operator Session (@login_required) & Broker Session Active                               |
|    - Idempotency Manager: Atomic check on client_order_id (In-Memory Set + DB Unique Index)          |
|      -> If duplicate: Return existing order record immediately (Zero Wire Placement)                 |
+------------------------------------------------------------------------------------------------------+
              |
              v
+------------------------------------------------------------------------------------------------------+
| 2. PRE-FLIGHT VALIDATION & PRE-TRADE RISK GATEKEEPER                                                 |
|    - OrderValidationService: Scaled ₹0.05 Tick Size, Lot Size Multiples, Stop Loss Price Invariants    |
|    - Market Protection (MP): Convert aggressive market requests to buffered limit orders             |
|    - OrderRiskService: Margin Check (+5% Buffer vs MarginService), Max Value Ceiling, Drawdown Stop   |
|      -> If validation or risk fails: Reject order locally (Zero Wire Placement, Status = REJECTED)    |
+------------------------------------------------------------------------------------------------------+
              |
              v
+------------------------------------------------------------------------------------------------------+
| 3. CIRCUIT BREAKER PRE-FLIGHT INSPECTION                                                             |
|    - BrokerCircuitBreaker.allow_request(): Check if broker gateway is healthy                        |
|      -> If Breaker is OPEN: Reject order immediately (Status = FAILED, CircuitBreakerOpenException)   |
+------------------------------------------------------------------------------------------------------+
              |
              v
+------------------------------------------------------------------------------------------------------+
| 4. PERSISTENCE & FSM TRANSITION (PRE-SUBMISSION)                                                     |
|    - OrderStateMachine.transition_to(order, OrderStatus.SUBMITTED)                                   |
|    - OrderRepository.save_order(order) & record_transition()                                         |
|    - EventBus.publish(ORDER_SUBMITTED) & AuditLogger.record(AUDIT_ORDER_PLACE)                       |
+------------------------------------------------------------------------------------------------------+
              |
              v
+------------------------------------------------------------------------------------------------------+
| 5. WIRE DISPATCH TO KOTAK NEO GATEWAY (`KotakOrderAdapter`)                                          |
|    - Format wire payload: exchange_segment, product, price, order_type, qty, validity, trdSym, side  |
|    - Attach tracking tag (GuiOrdId = client_order_id)                                                |
|    - client.place_order(...)                                                                         |
|                                                                                                      |
|    +-----------------------+-----------------------+------------------------+                        |
|    | Success: nOrdNo       | Immediate Rejection   | Timeout / Network Drop |                        |
|    v                       v                       v                        v                        |
|  Save broker_order_id    Transition to REJECTED  Transition to RECONCILING                           |
|  Transition to           Save rejection reason   (The Golden Rule: Never                             |
|  ACKNOWLEDGED            Publish REJECTED        assume dead; Poller resolves)                       |
+------------------------------------------------------------------------------------------------------+
              |
              v
+------------------------------------------------------------------------------------------------------+
| 6. ASYNCHRONOUS EXECUTION STATUS POLLER & RECONCILIATION WORKER                                      |
|    - Poll client.order_report(broker_order_id) with exponential backoff                              |
|    - Extract true weighted avg_price, fldQty, and terminal status                                    |
|    - When FILLED or PARTIALLY_FILLED:                                                                |
|      -> Save TradeExecution in DB (with dual timestamps)                                             |
|      -> Transition Order FSM (PARTIALLY_FILLED / FILLED)                                             |
|      -> Publish ORDER_FILLED / ORDER_PARTIALLY_FILLED to EventBus                                    |
+------------------------------------------------------------------------------------------------------+
              |
              +------------------------------------------------+
              |                                                |
              v                                                v
+--------------------------------+             +--------------------------------+
|  PHASE 6 PORTFOLIO SYNC        |             |  DOWNSTREAM AUDIT & METRICS    |
|  - PositionsService updates    |             |  - Append-only audit entry     |
|    net & day commitments       |             |  - Update daily order metrics  |
|  - MTMEngine updates floating  |             |  - Dispatch Web UI live alert  |
|    unrealized PnL on new tick  |             |                                |
+--------------------------------+             +--------------------------------+
========================================================================================================
```

---

## 3. Kotak Neo Order Execution Adapter (`KotakOrderAdapter`)

Located at `app/broker/adapters/kotak_order_adapter.py`, this adapter encapsulates the official Kotak Neo SDK client methods, abstracting raw wire calls and normalizing polymorphic responses.

### 3.1. Interface Definition
```python
class KotakOrderAdapterInterface(ABC):
    @abstractmethod
    def place_order(self, order: Order, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Submit new order to Kotak Neo broker gateway."""
        pass

    @abstractmethod
    def modify_order(self, order: Order, modifications: Dict[str, Any], credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Modify price, quantity, or trigger price of an existing open order."""
        pass

    @abstractmethod
    def cancel_order(self, order: Order, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Cancel an open or trigger-pending order on the exchange."""
        pass

    @abstractmethod
    def get_order_report(self, broker_order_id: str, credentials: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch real-time order execution report and trade fills."""
        pass

    @abstractmethod
    def get_order_book(self, credentials: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve full daily order book from broker."""
        pass

    @abstractmethod
    def get_trade_book(self, credentials: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve full daily trade book from broker."""
        pass
```

### 3.2. Wire Mapping Table
The adapter maps internal domain models to Kotak Neo wire parameters as specified by `neo_api_client`:

| Internal Domain Attribute | Kotak Neo Wire Parameter | Mapping Logic / Allowed Values |
|---|---|---|
| `order.exchange_segment` | `exchange_segment` | `"nse_cm"`, `"bse_cm"`, `"nse_fo"`, `"bse_fo"`, `"cde_fo"`, `"mcx_fo"` |
| `order.trading_symbol` | `trading_symbol` | Scrip trading symbol (e.g. `"RELIANCE-EQ"`, `"NIFTY26NOV24500CE"`) |
| `order.side` | `transaction_type` | `OrderSide.BUY` -> `"B"`; `OrderSide.SELL` -> `"S"` |
| `order.quantity` | `quantity` | `str(order.quantity)` |
| `order.price` | `price` | Format to 2 decimal places: `f"{order.price:.2f}"` (For Market, `"0"`) |
| `order.trigger_price` | `trigger_price` | Format to 2 decimal places: `f"{order.trigger_price:.2f}"` (For Limit/Mkt, `"0"`) |
| `order.order_type` | `order_type` | `OrderType.MARKET` -> `"MKT"`; `OrderType.LIMIT` -> `"L"`; `OrderType.SL` -> `"SL"`; `OrderType.SL_M` -> `"SL-M"` |
| `order.product_type` | `product` | `ProductType.CNC` -> `"CNC"`; `ProductType.MIS` -> `"MIS"`; `ProductType.NRML` -> `"NRML"` |
| `order.validity` | `validity` | `Validity.DAY` -> `"DAY"`; `Validity.IOC` -> `"IOC"` |
| `order.disclosed_quantity` | `disclosed_quantity` | `str(order.disclosed_quantity or 0)` |
| `order.client_order_id` | `tag` | Echoed back in Kotak reports as `GuiOrdId` or `tag` |

### 3.3. Response Normalization & Polymorphism Handling
Kotak Neo responses vary across SDK versions and endpoints. The adapter must normalize all responses into a standardized dictionary:

```python
# Standardized Execution Result Model
{
    "success": bool,
    "broker_order_id": Optional[str],     # extracted from nOrdNo, ordNo, order_id
    "status": str,                         # "ACKNOWLEDGED", "REJECTED", "FAILED", "RECONCILING"
    "rejection_reason": Optional[str],     # extracted from rejRsn, cancelRejectReason, errMsg
    "raw_response": Dict[str, Any]
}
```

* **Success Extraction**:
  - `response.get("stat") == "Ok"` or `response.get("nOrdNo") is not None` -> Success.
  - Extract `nOrdNo` as `broker_order_id`.
* **Broker Rejection Extraction**:
  - `response.get("stat") == "Not_Ok"` or presence of `errMsg` / `rejRsn` -> Failure.
  - Extract `rejRsn` or `errMsg` as `rejection_reason`.

### 3.4. Simulated / Test Mock Fallback
In compliance with project standards, if `neo_api_client` is not installed or if running in test fixtures (`__is_mock__`), `KotakOrderAdapter` provides a high-fidelity simulated execution mode:
- Generates realistic mock exchange order numbers: `f"26{datetime.now().strftime('%m%d%H%M%S')}{random.randint(100, 999)}"`.
- Simulates network latency (20ms–50ms).
- Simulates realistic order fills and trade execution records for integration testing.

---

## 4. Defensive Order Execution & Protection Patterns

Carrying forward the principles from the `kotak-neo-algo-trading` skill, Phase 8 incorporates production-hardened defensive execution patterns:

### 4.1. Market Protection (MP) for Aggressive Limits
**The Hazard**: Placing pure naked market orders (`MKT`) on exchange options frequently results in immediate RMS rejection (SEBI/NSE restriction on illiquid contracts) or massive slippage against wide bid-ask spreads.

**The Solution**:
- If an order specifies `order_type == OrderType.MARKET`, the execution pipeline intercepts it and queries Phase 5 `PriceEngine` for the current Touchline quote.
- Converts the order to an aggressive buffered `OrderType.LIMIT` with a configurable Market Protection buffer (default $2.0\%$ for equity, $5.0\%$ for options).
- Calculates the buffered limit price:
  - **Buy Order**: $\text{Limit Price} = \text{LTP} \times (1.0 + \text{Buffer})$.
  - **Sell Order**: $\text{Limit Price} = \text{LTP} \times (1.0 - \text{Buffer})$.
- Enforces minimum price of ₹0.05 and snaps to the nearest valid ₹0.05 tick using integer millipaise rounding.

### 4.2. Clean Broker-Side Stop Loss Orders (`order_type="SL"`)
**The Hazard**:
1. Software-only stop losses leave infinite overnight or dropout risk if the server crashes or disconnects.
2. Setting wide gap between `price` and `trigger_price` on Kotak Neo SL orders causes unnecessary artificial slippage.

**The Solution**:
- Always place native exchange-side Stop Loss Limit orders (`order_type="SL"`).
- Set `price = trigger_price`. When the trigger price is touched on the exchange, the order converts to a limit order at that exact price, executing immediately with zero artificial slippage.

### 4.3. Atomic Idempotency Architecture
**The Hazard**: Network timeouts, double-clicks in UI, or automated retry loops submitting duplicate wire orders to the broker, resulting in double positions and catastrophic capital loss.

**The Solution**:
- Every order creation request requires or generates a unique `client_order_id` (UUIDv4).
- **Two-Tier Idempotency Guard**:
  1. **In-Memory Cache Guard**: `IdempotencyManager` maintains an atomic TTL set of in-flight and recently executed `client_order_id`s (TTL = 300 seconds).
  2. **Relational Database Unique Index**: The `orders.client_order_id` column has a strict unique constraint.
- If an order request arrives with an existing `client_order_id`:
  - The execution pipeline aborts wire submission immediately.
  - Retrieves and returns the existing order record with `is_duplicate: True`.

### 4.4. Rate Limiting & Burst Protection
- Kotak Neo REST APIs enforce strict sub-second rate limits. Firing requests faster than 5 requests/sec triggers `429 Too Many Requests / Rate limit exceeded`.
- Phase 8 integrates a Token Bucket Rate Limiter (`RateLimiter`) capping outbound execution requests at **5 requests per second** with a burst allowance of **8 requests**.

---

## 5. Execution Status Polling & Asynchronous Reconciliation

### 5.1. The Principle: Order Placement $\neq$ Order Execution
A successful HTTP 200 response from `client.place_order()` with `{"stat": "Ok", "nOrdNo": "..."}` proves **only** that Kotak Neo's ingress gateway received the packet. It does **not** mean the order was accepted by the exchange or traded.

The order may still be:
1. `REJECTED` by the exchange RMS (e.g. invalid tick, circuit breaker breach, margin shortfall).
2. `OPEN` resting on the order book.
3. `TRIGGER_PENDING` resting as a Stop Loss.
4. `PARTIALLY_FILLED` or `FILLED` immediately.

### 5.2. Asynchronous Execution Poller Service (`OrderPollerService`)
Upon successful wire submission, an asynchronous background task (`OrderPollerService`) is spawned to track order progression without blocking the operator's REST response:

* **Polling Strategy**:
  - Query `KotakOrderAdapter.get_order_report(broker_order_id)`.
  - Max retries: 6 attempts.
  - Polling interval: Exponential backoff with jitter (initial delay: 0.3s, backoff factor: 1.5x, max delay: 2.0s).
* **Terminal Status Extraction**:
  - `complete`, `traded`, `filled` -> Extract `avg_price` and `filled_quantity`, record `TradeExecution`, transition order to `OrderStatus.FILLED`.
  - `partially_filled` -> Update `filled_quantity` and `pending_quantity`, transition to `OrderStatus.PARTIALLY_FILLED`.
  - `rejected`, `cancelled` -> Extract `rejection_reason`, transition order to `OrderStatus.REJECTED` or `OrderStatus.CANCELLED`.
  - `open`, `trigger_pending` -> Transition order to `OrderStatus.ACKNOWLEDGED` or `OrderStatus.TRIGGER_PENDING`.

### 5.3. Reconciliation of `RECONCILING` Orders
Carrying forward Milestone M3's **Golden Rule**:
- If `client.place_order()` times out, drops connection, or returns an unparsed HTTP 504 error, the order is transitioned immediately to `OrderStatus.RECONCILING`.
- The background reconciliation loop queries the broker's daily order book (`client.order_report()` or `client.order_history()`) matching by `tag` (`GuiOrdId == client_order_id`).
- If found: Reconciles the order with the actual broker status (`ACKNOWLEDGED`, `FILLED`, etc.).
- If not found after 5 consecutive cycles across 30 seconds: Flags order for manual operator inspection with structured audit alert (`AUDIT_ORDER_DISCREPANCY`).

---

## 6. Order Modification & Cancellation Pipelines

### 6.1. Order Modification (`PUT /api/orders/<id>/modify`)
Allows operators to update working orders resting on the exchange:
- **Allowed States for Modification**: Only orders in `ACKNOWLEDGED`, `TRIGGER_PENDING`, or `PARTIALLY_FILLED` can be modified. Attempting to modify terminal orders (`FILLED`, `CANCELLED`, `REJECTED`) raises `IllegalOrderStateTransitionException`.
- **Modifiable Fields**:
  - `price`: Must satisfy the integer millipaise ₹0.05 tick size rule.
  - `quantity`: Must be greater than `filled_quantity` and adhere to lot size multiples.
  - `trigger_price`: For SL orders, must satisfy Stop Loss trigger invariants.
- **Wire Dispatch**: Invokes `client.modify_order(order_id=broker_order_id, price=..., quantity=..., ...)`.
- **Audit & Events**: Dispatches `ORDER_MODIFIED` and logs `AUDIT_ORDER_MODIFY`.

### 6.2. Order Cancellation (`DELETE /api/orders/<id>/cancel`)
Allows operators to cancel resting orders:
- **Allowed States for Cancellation**: `ACKNOWLEDGED`, `TRIGGER_PENDING`, `PARTIALLY_FILLED`, or `RECONCILING`.
- **Wire Dispatch**: Invokes `client.cancel_order(order_id=broker_order_id)`.
- **FSM Transition**: Transitions order to `OrderStatus.CANCELLED` upon broker acknowledgement.
- **Audit & Events**: Dispatches `ORDER_CANCELLED` and logs `AUDIT_ORDER_CANCEL`.

### 6.3. Emergency Mass Cancellation (`POST /api/orders/cancel-all`)
An emergency kill-switch endpoint to immediately cancel all open/resting orders across the account:
- Queries `OrderRepository` for all active orders (`status in (ACKNOWLEDGED, TRIGGER_PENDING, PARTIALLY_FILLED)`).
- Iterates and dispatches cancellation requests concurrently with a bounded thread pool (max 5 workers to respect rate limits).
- Returns summary: `{total: N, cancelled: M, failed: K}`.
- Dispatches emergency audit entry: `AUDIT_EMERGENCY_CANCEL_ALL`.

---

## 7. Portfolio & Downstream System Integration

Phase 8 cleanly integrates execution events with downstream portfolio and market data services:

```
+---------------------------------------------------------------------------------------------------+
|                                     EXECUTION EVENT DISPATCH                                      |
+---------------------------------------------------------------------------------------------------+
                                                  |
                         +------------------------+------------------------+
                         |                                                 |
                         v                                                 v
         [ EVT: ORDER_FILLED / PARTIAL ]                         [ EVT: ORDER_CANCELLED / REJECTED ]
                         |                                                 |
                         v                                                 v
+-------------------------------------------------+     +-----------------------------------------+
| Phase 6 PositionsService Integration            |     | Phase 6 MarginService Integration       |
| - Ingests TradeExecution into net/day positions |     | - Releases blocked margin back to       |
| - Recalculates realized PnL on closed lots      |     |   available cash pool                   |
| - Broadcasts POSITIONS_UPDATED event            |     | - Recalculates margin utilization %     |
+-------------------------------------------------+     +-----------------------------------------+
                         |
                         v
+-------------------------------------------------+
| Phase 6 MTMEngine Integration                   |
| - Binds new open position to PriceEngine stream |
| - Recalculates floating unrealized PnL          |
| - Broadcasts MTM_UPDATED event                  |
+-------------------------------------------------+
```

---

## 8. Order Execution REST API Design

All execution endpoints require active operator session authentication (`@login_required`).

### 8.1. API Specification Table

| Method | Endpoint | Description | Auth Required | Request Body Summary | Response Summary |
|---|---|---|---|---|---|
| `GET` | `/api/orders/status` | Operational status of execution engine | No | None | `{status: "operational", execution_enabled: true}` |
| `POST` | `/api/orders/place` | Place live order to broker | Yes | `OrderPlacementRequest` (symbol, qty, price, type, side, product) | `{success: true, order: OrderSchema, execution: ExecutionDetails}` |
| `PUT` | `/api/orders/<id>/modify` | Modify open/pending order | Yes | `{price, quantity, trigger_price}` | `{success: true, order: OrderSchema}` |
| `DELETE` | `/api/orders/<id>/cancel` | Cancel open/pending order | Yes | None | `{success: true, order_id: str, status: "CANCELLED"}` |
| `POST` | `/api/orders/cancel-all` | Emergency mass cancel all open orders | Yes | Optional: `{segment, symbol}` | `{total_found: N, cancelled: M, failed: K}` |
| `POST` | `/api/orders/validate` | Dry-run validation (Zero Execution) | Yes | `OrderPlacementRequest` | `{valid: true, risk_passed: true, margin: {...}}` |
| `GET` | `/api/orders` | Queryable order book | Yes | Query params: `status, symbol, limit` | `{orders: [...], total_count: N}` |
| `GET` | `/api/orders/<id>` | Order detail & transition timeline | Yes | None | `{order: OrderSchema, events: [...]}` |
| `GET` | `/api/orders/trades` | Executed trade fills (Trade Book) | Yes | Query params: `symbol, limit` | `{trades: [...], count: N}` |
| `GET` | `/api/orders/stats` | Daily execution metrics | Yes | None | `{total_orders: N, filled: M, rejected: K, ...}` |

### 8.2. Payload Schema Examples

#### `POST /api/orders/place` Request Payload:
```json
{
  "client_order_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "trading_symbol": "RELIANCE-EQ",
  "exchange_segment": "nse_cm",
  "side": "BUY",
  "order_type": "LIMIT",
  "product_type": "CNC",
  "quantity": 10,
  "price": 2450.05,
  "trigger_price": 0.0,
  "validity": "DAY",
  "disclosed_quantity": 0,
  "market_protection_percent": 2.0
}
```

#### `POST /api/orders/place` Successful Response:
```json
{
  "success": true,
  "data": {
    "order": {
      "client_order_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "broker_order_id": "260930000169351",
      "status": "ACKNOWLEDGED",
      "trading_symbol": "RELIANCE-EQ",
      "quantity": 10,
      "price": 2450.05,
      "filled_quantity": 0,
      "pending_quantity": 10,
      "source_timestamp": "2026-11-06T09:45:00.123Z",
      "retrieved_timestamp": "2026-11-06T09:45:00.125Z"
    },
    "execution": {
      "status": "ACKNOWLEDGED",
      "nOrdNo": "260930000169351",
      "stat": "Ok"
    }
  }
}
```

---

## 9. Event Bus & Audit Framework Changes

### 9.1. New Event Types (`app/events/event_types.py`)
| Event Name | Constant | Description |
|---|---|---|
| `order.submitted` | `ORDER_SUBMITTED` | Dispatched when order payload is sent across the wire |
| `order.acknowledged` | `ORDER_ACKNOWLEDGED` | Dispatched when Kotak Neo accepts order with exchange number |
| `order.modified` | `ORDER_MODIFIED` | Dispatched when an open order is modified |
| `order.cancelled` | `ORDER_CANCELLED` | Dispatched when an order is canceled |
| `order.filled` | `ORDER_FILLED` | Dispatched when an order is 100% executed |
| `order.partially_filled` | `ORDER_PARTIALLY_FILLED` | Dispatched when an order receives a partial execution fill |
| `order.emergency_cancelled` | `ORDER_EMERGENCY_CANCELLED` | Dispatched when mass cancel-all is executed |

### 9.2. New Audit Actions (`app/core/audit.py`)
| Action Name | Constant | Category | Description |
|---|---|---|---|
| `ORDER_PLACE` | `AUDIT_ORDER_PLACE` | `AuditCategory.ORDER` | Recorded when live order is placed across the wire |
| `ORDER_MODIFY` | `AUDIT_ORDER_MODIFY` | `AuditCategory.ORDER` | Recorded when order price/qty is amended |
| `ORDER_CANCEL` | `AUDIT_ORDER_CANCEL` | `AuditCategory.ORDER` | Recorded when order is canceled |
| `ORDER_EXECUTION_FILL` | `AUDIT_ORDER_EXECUTION_FILL` | `AuditCategory.ORDER` | Recorded when trade execution fill is processed |
| `EMERGENCY_CANCEL_ALL` | `AUDIT_EMERGENCY_CANCEL_ALL` | `AuditCategory.ORDER` | Recorded when mass kill-switch is triggered |
| `ORDER_EXECUTION_FAILURE` | `AUDIT_ORDER_EXECUTION_FAILURE` | `AuditCategory.ORDER` | Recorded when broker returns wire error or reject |

---

## 10. Test Strategy & Verification Plan

Phase 8 will be validated through a comprehensive test suite of unit and integration tests:

### 10.1. Unit Tests
1. `tests/unit/test_kotak_order_adapter.py`:
   - Verify wire parameter formatting for Equity (`nse_cm`), Derivatives (`nse_fo`), and Currency (`cde_fo`).
   - Verify polymorphic response normalization (`stat: "Ok"`, `nOrdNo`, `errMsg`, `rejRsn`).
   - Verify simulated mock order placement, modification, and cancellation.
2. `tests/unit/test_order_execution_service.py`:
   - Verify pre-flight validation interception (zero wire call if tick size is invalid).
   - Verify pre-trade risk interception (zero wire call if margin or drawdown limit breached).
   - Verify Circuit Breaker interception (zero wire call if circuit breaker is OPEN).
   - Verify Market Protection buffer calculation on Market orders.
3. `tests/unit/test_idempotency_manager.py`:
   - Verify duplicate `client_order_id` is intercepted and returns cached order without dispatching wire call.
4. `tests/unit/test_order_poller.py`:
   - Verify execution report polling loop, exponential backoff, and trade fill extraction.
   - Verify resolution of `RECONCILING` orders into `FILLED` or `ACKNOWLEDGED`.

### 10.2. Integration Tests
1. `tests/integration/test_order_execution_routes.py`:
   - Test `POST /api/orders/place` end-to-end (validation -> risk -> wire -> poller -> DB).
   - Test `PUT /api/orders/<id>/modify` for price and quantity amendment.
   - Test `DELETE /api/orders/<id>/cancel` for individual cancellation.
   - Test `POST /api/orders/cancel-all` emergency mass kill-switch.
   - Test duplicate order rejection via idempotency key.
   - Test downstream sync: verify that an executed fill automatically updates Phase 6 `PositionsService` and `MTMEngine`.

---

## 11. Rollback & Fail-Safe Strategy

1. **Broker Circuit Breaker Auto-Trip**:
   - If the Kotak Neo order gateway returns 5 consecutive network timeouts or 5xx server errors, `BrokerCircuitBreaker` trips to `OPEN`.
   - All subsequent `POST /api/orders/place` calls fail fast locally, protecting user capital and preventing queue piling.
2. **Reconciliation Containment (The Golden Rule)**:
   - Any order with an unconfirmed wire status transitions to `OrderStatus.RECONCILING`.
   - Automated duplicate submissions are strictly blocked until authoritative status is verified.
3. **Graceful Emergency Kill-Switch**:
   - `POST /api/orders/cancel-all` allows instantaneous evacuation of all resting limit orders.
4. **Git Branching & Database Rollback**:
   - All Phase 8 code developed on feature branch `feature/phase8-order-execution`.
   - Zero destructive schema changes to existing Phase 7 tables; database backward compatibility maintained.

---

## 12. Deliverables Checklist for Phase 8

Upon implementation approval, Phase 8 will deliver:

- [ ] `app/broker/adapters/kotak_order_adapter.py` (Kotak Neo SDK Order Execution Adapter)
- [ ] `app/orders/services/order_execution_service.py` (End-to-end execution orchestrator)
- [ ] `app/orders/services/idempotency_manager.py` (Atomic deduplication cache)
- [ ] `app/orders/services/order_poller_service.py` (Asynchronous status poller & reconciler)
- [ ] `app/orders/routes.py` (Activated `/place`, `/modify`, `/cancel`, `/cancel-all` endpoints)
- [ ] `app/events/event_types.py` & `app/core/audit.py` (Registered execution events & audit actions)
- [ ] `docs/adr/ADR-012-Order-Execution-Foundation.md` (Architecture Decision Record)
- [ ] `tests/unit/test_kotak_order_adapter.py` & `tests/unit/test_order_execution_service.py`
- [ ] `tests/integration/test_order_execution_routes.py`
- [ ] `PHASE8_ARCHITECTURE_REVIEW.md` (Comprehensive architecture review and audit package)

---

**End of Phase 8 Architectural Design Specification**

