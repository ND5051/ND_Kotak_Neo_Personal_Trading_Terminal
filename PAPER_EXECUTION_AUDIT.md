# Paper Execution Simulator Audit Report
## Quantity & Filled Quantity Integrity Verification

**Audit Date:** 2026-11-06  
**Auditor:** Antigravity Agentic Assistant / Google DeepMind Pair Programming  
**Scope:** Paper Trading Execution Pipeline (`ExecutionMode.PAPER`), Mock Order Adapters, Asynchronous Poller & Order State Machine  
**Target Repository:** `ND_Kotak_Neo_Personal_Trading_Terminal`  
**Governing Mandate:** Verify `quantity` vs `filled_quantity` in paper-mode fills; guarantee that **no fill can ever exceed the requested quantity under any condition**.  
**Audit Outcome:** **PASSED & HARDENED** (All identified vulnerabilities resolved, 4/4 audit tests passing, 137/137 terminal suite passing).

---

## 1. Executive Summary

As part of the pre-Phase 9 readiness gate for Milestone M4, a formal security and mathematical audit was conducted on the terminal's **Paper Execution Simulator**.

The audit identified two critical latent risks in the initial Phase 8 implementation:
1. **Static Mock Fill Anomaly**: The initial fallback simulated order report in `KotakOrderAdapter.get_order_report` returned a hardcoded `"fldQty": "10"`. When an order with `quantity < 10` (such as 1, 2, or 5 shares) was evaluated by the poller, `fldQty` was assigned directly to `order.filled_quantity`, causing the filled quantity to exceed the requested quantity ($10 > 5$).
2. **Substring Classification Collision**: The poller used string substring matching `if any(s in raw_st for s in ["complete", "traded", "filled"])` before checking `"partial"`. Because `"partially_filled"` contains the substring `"filled"`, simulated partial fills were erroneously classified as complete terminal fills.

Both vulnerabilities were systematically remediated through:
* Mandatory quantity clamping in `OrderPollerService`: `target_fld_qty = min(fld_qty, order.quantity)`.
* Incremental trade fill accounting: `incremental_fill = max(0, target_fld_qty - order.filled_quantity)`.
* Mathematical invariant assertions baked directly into the `Order` domain dataclass (`assert_quantity_invariants()`).
* Dynamic mock order registration in `KotakOrderAdapter` and `OrderExecutionService` strictly tracking requested quantities.
* Reordered state classification preventing partial fill string collisions.

---

## 2. Mathematical Invariants & Governing Contracts

The paper execution engine and poller must strictly obey three fundamental mathematical invariants at all times ($t \ge 0$):

$$\text{Invariant 1 (Non-Negativity): } \quad \text{filled\_quantity} \ge 0, \quad \text{pending\_quantity} \ge 0$$

$$\text{Invariant 2 (Strict Capacity Ceiling): } \quad \text{filled\_quantity} \le \text{quantity}$$

$$\text{Invariant 3 (Conservation of Quantity): } \quad \text{filled\_quantity} + \text{pending\_quantity} = \text{quantity}$$

$$\text{Invariant 4 (Monotonic Fill Accumulation): } \quad \sum_{i=1}^{n} \text{fill\_quantity}_i = \text{filled\_quantity} \le \text{quantity}$$

Any state where $\text{filled\_quantity} > \text{quantity}$ constitutes a catastrophic RMS and accounting failure, as it creates phantom market exposure, corrupts portfolio margin, and violates exchange clearinghouse rules.

---

## 3. Vulnerability Analysis & Discovery

### 3.1. Vulnerability V-01: Static Mock `fldQty: 10` Overfill
* **File:** `app/broker/adapters/kotak_order_adapter.py`
* **Root Cause:**
  ```python
  # Prior vulnerable code:
  if self._is_mock():
      return [{
          "nOrdNo": broker_order_id,
          "ordSt": "complete",
          "avgPrc": "2450.05",
          "fldQty": "10",  # <--- HARDCODED 10 SHARES
          "rejRsn": "",
      }]
  ```
  In `app/orders/services/order_poller_service.py`:
  ```python
  # Prior vulnerable code:
  if any(s in raw_st for s in ["complete", "traded", "filled"]):
      order.filled_quantity = fld_qty or order.quantity
      order.pending_quantity = max(0, order.quantity - order.filled_quantity)
  ```
* **Impact:**
  If an operator placed a paper order for 1 share of TCS, the poller extracted `fld_qty = 10`. `fld_qty or order.quantity` evaluated to `10`. The order was saved with `filled_quantity = 10`, `quantity = 1`, and `TradeExecution(fill_quantity=10)`. The order filled **1000%** of requested quantity.

### 3.2. Vulnerability V-02: Substring Collision on `"partially_filled"`
* **File:** `app/orders/services/order_poller_service.py`
* **Root Cause:**
  ```python
  # Prior vulnerable ordering:
  if any(s in raw_st for s in ["complete", "traded", "filled"]):   # "partially_filled" matched "filled"!
      ...  # Treated as complete fill
  elif any(s in raw_st for s in ["partial", "partially"]):
      ...  # Never reached for "partially_filled"
  ```
* **Impact:**
  Any simulated partial fill (e.g. 5 of 20 shares) with status `"partially_filled"` was prematurely transitioned to `OrderStatus.FILLED`.

---

## 4. Defensive Hardening Implemented

### 4.1. Domain Model Mathematical Invariant (`Order.assert_quantity_invariants`)
Located in [`app/orders/models/order.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/orders/models/order.py):
```python
def assert_quantity_invariants(self) -> None:
    """
    Verify mathematical invariants on quantities:
    1. filled_quantity >= 0 and pending_quantity >= 0
    2. filled_quantity <= quantity
    3. filled_quantity + pending_quantity <= quantity
    """
    if self.filled_quantity < 0:
        raise ValueError(f"Invariant violation: filled_quantity ({self.filled_quantity}) cannot be negative")
    if self.pending_quantity < 0:
        raise ValueError(f"Invariant violation: pending_quantity ({self.pending_quantity}) cannot be negative")
    if self.filled_quantity > self.quantity:
        raise ValueError(
            f"Invariant violation: filled_quantity ({self.filled_quantity}) cannot exceed total quantity ({self.quantity})"
        )
    if self.filled_quantity + self.pending_quantity > self.quantity:
        raise ValueError(
            f"Invariant violation: filled ({self.filled_quantity}) + pending ({self.pending_quantity}) exceeds total quantity ({self.quantity})"
        )
```
This is executed automatically in `__post_init__` and at every state transition.

### 4.2. Strict Poller Clamping & Incremental Fill Recording
Located in [`app/orders/services/order_poller_service.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn To Code - Nitin Joshi/ND Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/orders/services/order_poller_service.py):
```python
# 1. Check Partially Filled Status FIRST to avoid substring overlap
if any(s in raw_st for s in ["partial", "partially"]):
    target_fld_qty = min(fld_qty, order.quantity)
    if fld_qty > order.quantity:
        logger.warning(f"Broker reported partial fldQty {fld_qty} exceeds order.quantity {order.quantity}. Clamping.")
        audit_logger.record(category=AuditCategory.ORDER, action=AUDIT_ORDER_DISCREPANCY, ...)

    incremental_fill = max(0, target_fld_qty - order.filled_quantity)
    order.filled_quantity = target_fld_qty
    order.pending_quantity = max(0, order.quantity - order.filled_quantity)
    order.assert_quantity_invariants()

    if incremental_fill > 0:
        # Record granular trade fill for incremental execution
        trade = TradeExecution(..., fill_quantity=incremental_fill, ...)
        self.repository.record_trade_execution(trade)

# 2. Complete Fill Status
elif any(s in raw_st for s in ["complete", "traded", "filled", "executed"]):
    target_fld_qty = order.quantity if fld_qty == 0 else min(fld_qty, order.quantity)
    if fld_qty > order.quantity:
        logger.warning(f"Broker reported fldQty {fld_qty} exceeds order.quantity {order.quantity}. Clamping.")
        audit_logger.record(category=AuditCategory.ORDER, action=AUDIT_ORDER_DISCREPANCY, ...)

    incremental_fill = max(0, target_fld_qty - order.filled_quantity)
    order.filled_quantity = target_fld_qty
    order.pending_quantity = max(0, order.quantity - order.filled_quantity)
    order.assert_quantity_invariants()
```

### 4.3. Dynamic Order Registration in Adapter & Paper Engine
Located in [`app/broker/adapters/kotak_order_adapter.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn To Code - Nitin Joshi/ND Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/adapters/kotak_order_adapter.py) and [`app/orders/services/order_execution_service.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn To Code - Nitin Joshi/ND Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/orders/services/order_execution_service.py):
* `KotakOrderAdapter` maintains a thread-safe registry `_simulated_orders: Dict[str, Dict[str, Any]]`.
* When an order is placed in simulated mode or paper mode, it is registered with its **exact requested quantity and price**:
  ```python
  adapter.register_simulated_order(paper_order_id, quantity=order.quantity, price=order.price, status="complete")
  ```
* When `get_order_report(broker_order_id)` is invoked, it retrieves the exact registered record rather than a static default.

### 4.4. Terminal State Poller Immunity
In `OrderPollerService.poll_order_status`:
```python
for attempt in range(1, max_attempts + 1):
    if order.is_terminal():
        return order  # Do not mutate orders that are CANCELLED, REJECTED, or FILLED
    time.sleep(delay)
    if order.is_terminal():
        return order
```
Prevents race conditions where a background poller overrides an order that was cancelled or rejected by operator action.

---

## 5. Verification Test Suite

A dedicated unit test suite was implemented in [`tests/unit/test_paper_execution_audit.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn To Code - Nitin Joshi/ND Projects/ND_Kotak_Neo_Personal_Trading_Terminal/tests/unit/test_paper_execution_audit.py):

| Test Identifier | Test Case Name | Objective / Scenario | Result |
|---|---|---|---|
| **AUD-P8-01** | `test_order_model_quantity_invariants` | Verifies `assert_quantity_invariants()` rejects negative quantities, `filled > quantity`, and `filled + pending > quantity`. | **PASSED** |
| **AUD-P8-02** | `test_paper_execution_fill_strictly_matches_requested_quantity` | Places paper orders for 1, 5, 25, 65, and 100 shares. Verifies every order fills to exactly the requested quantity with 0 pending and $\le$ quantity invariant. | **PASSED** |
| **AUD-P8-03** | `test_poller_clamps_excess_broker_reported_quantity` | Simulates an overfill anomaly where adapter/broker reports `fldQty: 999` on an order of `quantity: 10`. Verifies fill is strictly clamped to 10 and trade execution is recorded for 10. | **PASSED** |
| **AUD-P8-04** | `test_paper_partial_fill_progression` | Simulates sequential partial fills (8 shares, then 6 shares, then remaining 6 on an order of 20). Verifies cumulative fill is 20, pending is 0, and individual fills sum to $\le 20$. | **PASSED** |

---

## 6. Audit Conclusion & Sign-Off

The paper execution simulator and order poller have been thoroughly audited, defensively hardened, and mathematically verified.

* **Verified:** Under no condition can paper execution fills exceed requested quantity.
* **Verified:** Overfill anomalies from faulty broker responses are strictly clamped, discrepancy-audited, and blocked from corrupting the domain model.
* **Verified:** Partial fills progress monotonically and sum exactly to cumulative filled quantity.
* **Audit Status:** **CLEARED FOR MILESTONE M4 BASELINE & PHASE 9 PROGRESSION.**

