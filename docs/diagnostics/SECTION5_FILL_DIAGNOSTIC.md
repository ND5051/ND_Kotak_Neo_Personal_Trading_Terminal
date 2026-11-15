# Section 5 Live UAT Order Immediate Fill — Forensic Diagnostic

**Document Type:** Root Cause & Execution Timeline Investigation  
**Target Order:** `cli_ord_1794481709728_497` (`HDFCBANK EQ`, `BUY`, `1` Qty, `LIMIT` @ ₹1,600.00)  
**Broker Order ID:** `261112163830488`  
**Date:** 2026-11-12  

---

## 1. Executive Summary & Answers to Diagnostic Questions

| # | Question | Finding |
| :--- | :--- | :--- |
| **1** | **Is the order routed through `PAPER` or `LIVE` execution path?** | **`LIVE` execution path** (`OrderExecutionService._execute_live_order()`). |
| **2** | **What was the actual `ExecutionMode` at dispatch time?** | **`LIVE`**. |
| **3** | **What `broker_order_id` was generated?** | **`261112163830488`** (locally synthesized mock ID, not a Kotak/exchange `nOrdNo`). |
| **4** | **Did the order reach Kotak Neo?** | **NO.** Zero network/SDK calls were made to Kotak Neo. |
| **5** | **Was a real exchange order created?** | **NO.** |
| **6** | **Was the fill produced by `OrderPollerService`?** | **YES.** `OrderPollerService` (`actor="order_poller"`) polled `kotak_order_adapter.get_order_report("261112163830488")`, received the mock `"ordSt": "complete"` record, and transitioned the order to `FILLED`. |
| **7** | **Was the fill produced by Paper Execution Simulator?** | **NO** (not `_execute_paper_order()`). It was produced by **`KotakOrderAdapter._is_mock()` fallback inside the `LIVE` execution path**. |

---

## 2. Root Cause: Disconnected `KotakOrderAdapter` Singleton (`client = None`)

In the current codebase, broker authentication and order execution use **two separate, unwired adapter instances**:

1. **Authentication Adapter ([`app/broker/routes.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/routes.py#L19)):**
   ```python
   kotak_adapter = KotakBrokerAdapter()
   ```
   When `/api/broker/login` or `/api/broker/restore` runs, `kotak_adapter.client` is populated with the authenticated `NeoAPI` SDK instance.

2. **Order Execution Adapter ([`app/broker/adapters/kotak_order_adapter.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code - Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/adapters/kotak_order_adapter.py#L79-L100)):**
   `OrderExecutionService` uses the global singleton `kotak_order_adapter = KotakOrderAdapter()`, initialized with `self.client = None`. Nothing ever injects `kotak_adapter.client` into `kotak_order_adapter.client` after broker login.

3. **Silent Mock Fallback in `LIVE` Mode ([`kotak_order_adapter.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/adapters/kotak_order_adapter.py#L148-L164)):**
   ```python
   def _is_mock(self) -> bool:
       if self.client is None:
           return True
       return getattr(self.client, "__is_mock__", False) or (NeoAPI is None)
   ```
   Because `kotak_order_adapter.client` remains `None`:
   - `place_order()` enters `if self._is_mock():`.
   - It synthesizes `mock_order_no = "261112163830488"`.
   - It calls `self.register_simulated_order(mock_order_no, quantity=1, price=1600.0, status="complete")`.
   - It logs `WIRE_ORDER_MOCK_SUCCESS` and returns `stat: "Ok"`.
   - `_execute_live_order()` transitions the order to `ACKNOWLEDGED` (`"Broker Gateway Ingestion Successful"`) and spawns `OrderPollerService`.
   - ~100ms later, `OrderPollerService` queries `kotak_order_adapter.get_order_report("261112163830488")`, reads the `"complete"` mock record, creates a `trade_executions` row, and marks the order `FILLED` (`"Exchange Execution Complete"`).

> [!CAUTION]
> **Critical Safety Finding:** In `ExecutionMode.LIVE`, `KotakOrderAdapter` **must never** silently fall back to `_is_mock()` simulation when `self.client is None` or `NeoAPI is None`. Live mode without an authenticated SDK client must fail loudly (`BrokerException`) rather than fabricating fake fills.

---

## 3. Extracted Execution Timeline (Forensic Evidence)

Evidence extracted from `data/kotak_terminal.db` (`orders`, `order_events`, `trade_executions`) and `logs/terminal.log` for **`cli_ord_1794481709728_497`**:

| Stage | Timestamp (UTC) | Source / Event | Details |
| :--- | :--- | :--- | :--- |
| **1. Order Created** | `2026-11-12T11:08:29.883696Z` | `orders` table (`id=10`) | `HDFCBANK EQ`, `BUY`, `1` Qty, `LIMIT` @ ₹1,600.00 |
| **2. Validation** | `2026-11-12T11:08:29.833225Z` $\to$ `.931730Z` | `ORDER_VALIDATION` / `order_events.id=34` | `PENDING_VALIDATION` $\to$ `VALIDATED` (`Pre-flight and risk checks passed`) |
| **3. Risk Check** | `2026-11-12T11:08:29.871953Z` | `ORDER_RISK_CHECK` | `APPROVED` (`available_cash: 500000.0`) |
| **4. Submission** | `2026-11-12T11:08:29.992581Z` $\to$ `.046745Z` | `order_events.id=35` / `WIRE_ORDER_DISPATCH` | `VALIDATED` $\to$ `SUBMITTED` (`Dispatching to broker gateway`) |
| **5. Mock Fallback** | `2026-11-12T11:08:30.083159Z` | `WIRE_ORDER_MOCK_SUCCESS` | `Simulated order placement: 261112163830488` (`self._is_mock() == True`) |
| **6. Ack** | `2026-11-12T11:08:30.140260Z` | `order_events.id=36` / `ORDER_ACKNOWLEDGED` | `SUBMITTED` $\to$ `ACKNOWLEDGED` (`Broker Gateway Ingestion Successful`) |
| **7. Fill** | `2026-11-12T11:08:30.296800Z` $\to$ `.353548Z` | `trade_executions.id=9` / `order_events.id=37` / `ORDER_EXECUTION_FILL` | `ACKNOWLEDGED` $\to$ `FILLED` (`Exchange Execution Complete`, `fill_qty=1`, `fill_price=1600.0`, `actor=order_poller`) |

Total elapsed time from `POST /api/orders/place` to simulated `FILLED`: **~441 ms**.

---

## 4. Secondary Anomaly Observed in Logs

During the same session (`2026-11-12T11:10:07.362913Z`), `GET /api/orders?limit=100` returned **HTTP 500** due to a pre-existing row in `orders` violating the quantity invariant:
```
ValueError: Invariant violation: filled_quantity (10) cannot exceed total quantity (1)
```
This should be cleaned up in `data/kotak_terminal.db` before resuming UAT so the Order Book endpoint returns HTTP `200`.

---

## 5. Recommended Remediation (Before Resuming Live UAT)

1. **Wire `kotak_adapter.client` to `kotak_order_adapter` (and Portfolio/Market services):**
   - Share the authenticated `NeoAPI` client from `kotak_adapter` into `kotak_order_adapter.client` on `/api/broker/login`, `/api/broker/restore`, and clear it on `/api/broker/logout`.
2. **Prohibit Silent Mock Fallback in `LIVE` Mode:**
   - In `OrderExecutionService._execute_live_order()` (or `KotakOrderAdapter.place_order()` when `mode == LIVE`), raise `BrokerException("Live Kotak Neo SDK client is not connected/authenticated")` if `kotak_order_adapter._is_mock()` is `True` — **never** simulate an order in `LIVE` mode.
3. **Clean Up Corrupted DB Row:**
   - Inspect and remove/repair the legacy `orders` row where `filled_quantity=10` and `quantity=1` in `data/kotak_terminal.db`.

