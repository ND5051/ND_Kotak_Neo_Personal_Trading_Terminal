# Live Execution Wiring Fix Review (P1 Defect Resolution)

**Document Type:** Production Defect Fix & Verification Review  
**Severity:** P1 Production-Blocking  
**Date:** 2026-11-12  
**Reference Diagnostic:** [`SECTION5_FILL_DIAGNOSTIC.md`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code - Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/SECTION5_FILL_DIAGNOSTIC.md)  

---

## 1. Root Cause

Broker authentication, order execution, portfolio services, and WebSocket streaming operated on **disconnected adapter instances**:
1. `app/broker/routes.py` instantiated a standalone `kotak_adapter = KotakBrokerAdapter()`, which populated `kotak_adapter.client` with the authenticated `NeoAPI` SDK instance during `/api/broker/login`.
2. `OrderExecutionService` used the separate global singleton `kotak_order_adapter = KotakOrderAdapter()` (`client = None`), `PortfolioService` instantiated its own `KotakBrokerAdapter()`, and `ws_supervisor.adapter` (`KotakStreamAdapter`) kept `client = None`.
3. Because `kotak_order_adapter.client` remained `None`, `kotak_order_adapter._is_mock()` returned `True` even in `ExecutionMode.LIVE`, causing `KotakOrderAdapter.place_order()` to silently fall back to `WIRE_ORDER_MOCK_SUCCESS`, generate a fake `26...` order ID, and immediately mark the order `FILLED` via `OrderPollerService`.

---

## 2. Files Changed

| File | Change |
| :--- | :--- |
| [`app/broker/adapters/kotak_adapter.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/adapters/kotak_adapter.py) | Exported global singleton `kotak_adapter`; cleared `self.client = None` on `logout()`; added `NeoAPI` client re-instantiation on `restore_session()` when env credentials exist. |
| [`app/broker/services/broker_client_sync.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/services/broker_client_sync.py) | Created `sync_shared_broker_client(client)` to propagate the single `NeoAPI` client across `kotak_adapter`, `kotak_order_adapter`, `portfolio_service.adapter`, and `ws_supervisor.adapter`. |
| [`app/portfolio/services/portfolio_service.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/portfolio/services/portfolio_service.py) | Updated default adapter from `KotakBrokerAdapter()` to the shared `kotak_adapter` singleton. |
| [`app/broker/routes.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/routes.py) | Bound routes to shared `kotak_adapter`; wired `sync_shared_broker_client()` on `/login`, `/restore`, and `/logout`; added `GET /api/broker/client-state`. |
| [`app/orders/services/order_execution_service.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/orders/services/order_execution_service.py) | Added LIVE Mode Safety Guard in `place_order()` and `_execute_live_order()` raising `BrokerException(..., status_code=503)` when `client is None` or `_is_mock()` is `True`. |
| [`app/orders/routes.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/orders/routes.py) | Propagated `getattr(e, "error_code", "BROKER_ERROR")` and `getattr(e, "status_code", 502)` for `BrokerException` responses (returning HTTP `503`). |
| [`tests/integration/test_live_execution_wiring.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/tests/integration/test_live_execution_wiring.py) | Added integration test covering `/api/broker/client-state`, LIVE mode `503` safety guard, shared client identity propagation, and logout cleanup. |

---

## 3. Shared Client Architecture

```
POST /api/broker/login   ─┐
POST /api/broker/restore ─┴─► kotak_adapter.client (Single NeoAPI Instance)
                                    │
                                    ▼ sync_shared_broker_client(client)
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
  kotak_order_adapter     portfolio_service.adapter   ws_supervisor.adapter
  (Order Execution)       (Holdings/Positions/Margin) (SFeed Streaming)
```

- On `POST /api/broker/logout`, `sync_shared_broker_client(None)` clears `.client` across all adapters simultaneously.
- Verification endpoint `GET /api/broker/client-state` exposes:
  ```json
  {
    "broker_authenticated": true,
    "execution_adapter_connected": true,
    "streaming_adapter_connected": true,
    "is_mock": false
  }
  ```

---

## 4. Safety Checks Added

1. **Pre-Dispatch LIVE Mode Guard (`OrderExecutionService.place_order` Step 8B):**
   - If `ExecutionMode == LIVE` and (`adapter.client is None` or `adapter._is_mock() == True`):
     - Releases the idempotency lock (`self.idempotency.release(client_order_id)`).
     - Raises `BrokerException(..., error_code="BROKER_CLIENT_NOT_CONNECTED", status_code=503)`.
     - **Does NOT** simulate fills, generate a `broker_order_id`, persist an `ACKNOWLEDGED`/`FILLED` order, or create `TradeExecution` records.
2. **Defense-in-Depth Guard (`OrderExecutionService._execute_live_order`):**
   - Re-verifies `adapter.client is not None` and `not adapter._is_mock()` before calling `self.adapter.place_order(order)`.
3. **HTTP 503 Propagation (`app/orders/routes.py`):**
   - `place_order()` honors `BrokerException.status_code` (`503`) and `BrokerException.error_code` (`BROKER_CLIENT_NOT_CONNECTED`).

---

## 5. Database Cleanup Result (`data/kotak_terminal.db`)

- **Query:** `SELECT id, client_order_id, broker_order_id, trading_symbol, quantity, filled_quantity, status FROM orders WHERE filled_quantity > quantity`
- **Invalid Legacy Rows Found:** `2`
  - `id=2`: `0740c175-d022-4d88-936b-afe1bbaccefc` (`PAPER_1106160656104`, `RELIANCE-EQ`, `quantity=1`, `filled_quantity=10`, `status=FILLED`)
  - `id=3`: `0feb918a-34ab-4455-b741-bfc3ba380772` (`PAPER_1106161018356`, `RELIANCE-EQ`, `quantity=1`, `filled_quantity=10`, `status=FILLED`)
- **Action Taken:** `UPDATE orders SET filled_quantity = quantity WHERE filled_quantity > quantity`
- **Result:** `2` rows repaired; `0` invalid rows remaining (`GET /api/orders?limit=100` invariant violation resolved).

---

## 6. Test Results

- **Targeted P1 Wiring & Safety Guard Test:**
  - `pytest tests/integration/test_live_execution_wiring.py -v`
  - **Result:** `1 passed in 1.39s`
- **Full Integration & Unit Regression Suite:**
  - `pytest tests/integration/ tests/unit/ -q`
  - **Result:** `208 passed in 23.35s` (0 failures, 0 skipped)

