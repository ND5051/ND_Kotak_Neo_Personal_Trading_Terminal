# PAPER Mode Auto-Fill Behavior & Section 4 Kill-Switch Execution Guidance

**Document Purpose:** Clarify `PAPER` mode limit order fill behavior and define the exact execution protocol for **Section 4 (Global Emergency Kill-Switch Drill)** in [`LIVE_UAT_CHECKLIST.md`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code - Nitin Joshi/ND Projects/ND_Kotak_Neo_Personal_Trading_Terminal/LIVE_UAT_CHECKLIST.md).  
**Date:** 2026-11-12  

---

## 1. Does `PAPER` Mode Intentionally Auto-Fill All Limit Orders?

**Yes — this is intentional by design in the current Paper Execution Engine.**

### Exact Codebase Behavior
1. **Paper Order Registration ([`order_execution_service.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code - Nitin Joshi/ND Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/orders/services/order_execution_service.py#L459-L496)):**
   When `ExecutionMode` is `PAPER`, `OrderExecutionService._execute_paper_order()` simulates a 20ms latency and unconditionally registers the simulated order with `status="complete"`, regardless of `order_type` (`LIMIT`, `MARKET`, `SL`) or limit price relative to LTP:
   ```python
   if hasattr(self.adapter, "register_simulated_order"):
       self.adapter.register_simulated_order(
           paper_order_id,
           quantity=int(order.quantity),
           price=float(order.price or 100.0),
           status="complete",
       )
   ```
2. **Immediate Background Fill ([`order_poller_service.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code - Nitin Joshi/ND Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/orders/services/order_poller_service.py#L64-L97)):**
   `_execute_paper_order()` transitions the order to `ACKNOWLEDGED` and immediately spawns `self.poller.spawn_async_poll(order)`. After `initial_delay_sec=0.1` (100ms), `OrderPollerService.poll_order_status()` reads `status="complete"` from the adapter and transitions the order to `FILLED` (a terminal state).

### Why This Happens
The `PAPER` simulator does **not** run a live limit-order matching engine against real-time market depth/LTP. Every valid paper order is treated as an instant simulated fill (~100–120ms end-to-end) so paper workflows can verify validation, risk checks, trade book recording, and MTM updates deterministically.

---

## 2. Why Section 4 (Kill Switch) Cannot Rest Open Orders in `PAPER` Mode

In [`OrderExecutionService.cancel_all_orders()`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code - Nitin Joshi/ND Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/orders/services/order_execution_service.py#L343-L378), the Kill Switch only cancels orders currently in open states:
```python
open_statuses = [
    OrderStatus.ACKNOWLEDGED,
    OrderStatus.TRIGGER_PENDING,
    OrderStatus.PARTIALLY_FILLED,
]
```
Because `PAPER` mode transitions orders from `ACKNOWLEDGED` $\to$ `FILLED` within ~100ms, a human operator staging 2 Limit orders in `PAPER` mode will see both orders already in `FILLED` (terminal) state before they can press `Shift + Esc`.

---

## 3. How Section 4 (Kill Switch Verification) Should Be Executed

Execute Section 4 using the two-stage protocol below:

### Stage A: Pre-Live Control & Pipeline Verification (in `PAPER` Mode)
Use `PAPER` mode **only** to verify the Kill-Switch trigger, confirmation prompt, API endpoint, and audit logging:
1. **UI & Shortcut Check (`Shift + Esc`):**
   - Ensure focus is not inside an `<input>`, `<textarea>`, or `<select>` (see [`terminal_shell.js`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code - Nitin Joshi/ND Projects/ND_Kotak_Neo_Personal_Trading_Terminal/static/js/terminal_shell.js#L582-L585)).
   - Press `Shift + Esc` (or click the **Emergency Cancel All** button).
   - Confirm the prompt: `"EMERGENCY KILL-SWITCH: Are you sure you want to cancel all open orders across all exchanges?"`.
   - Verify `POST /api/orders/cancel-all` returns HTTP `200 OK` (`{"success": true, "total_found": 0, "cancelled": 0, "failed": 0}`).
   - Verify the audit log records `AUDIT_EMERGENCY_CANCEL_ALL`.
2. **Automated Cancellation Logic Verification:**
   - The mass-cancellation of open `ACKNOWLEDGED` / `TRIGGER_PENDING` orders is verified by the automated integration suite (`tests/integration/test_order_routes.py::test_orders_cancel_all_emergency_kill_switch`).

### Stage B: Full Live Resting-Order Kill-Switch Drill (in `LIVE` Mode — Required for UAT Sign-Off)
Section 4 of [`LIVE_UAT_CHECKLIST.md`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code - Nitin Joshi/ND Projects/ND_Kotak_Neo_Personal_Trading_Terminal/LIVE_UAT_CHECKLIST.md#L55-L63) explicitly specifies **"Stage 2 open Limit orders resting on the exchange (e.g. 5% below market)"** — this is designed for **`LIVE` mode** where the exchange order book holds the orders open:

1. **Ensure Zero Capital Fill Risk:**
   - Switch Execution Mode to `LIVE` (using the `CONFIRM_LIVE` challenge).
   - Pick a liquid large-cap equity on `nse_cm` (e.g., `ITC` or `INFY`), **Quantity = `1` share**, **Product = `MIS` or `CNC`**.
   - Place **2 `BUY LIMIT` orders** priced **5% to 8% below current LTP** (ensure the price stays within NSE's daily lower circuit limit so the broker accepts it).
2. **Verify Open State:**
   - Open Order Book (`Alt + 2`) and confirm both orders remain resting with status `ACKNOWLEDGED` / `OPEN` (and `nOrdNo` populated).
3. **Execute Kill Switch:**
   - Press `Shift + Esc` from anywhere in the terminal (outside text inputs).
   - Confirm the emergency modal prompt.
4. **Verify Cancellation & Audit:**
   - Assert both orders transition to `CANCELLED` within 500ms in the terminal Order Book and in the Kotak Neo mobile/web app.
   - Verify the audit log emits `AUDIT_EMERGENCY_CANCEL_ALL` with `cancelled: 2, failed: 0`.
5. **WebSocket Severed Fallback (Step 4.7):**
   - Repeat with a single 1-share far-OTM/below-market `BUY LIMIT` order, disconnect WebSocket/network briefly or test REST fallback, trigger `Shift + Esc`, and confirm REST `POST /api/orders/cancel-all` still cancels the resting order.
   - *(Safety Net: Keep the Kotak Neo mobile/web app open alongside the terminal during the drill so any order can be manually cancelled if network connectivity is severed during Step 4.7.)*

---

## 4. Summary Checklist for Operator

| Mode | What Can Be Verified for Section 4 |
| :--- | :--- |
| **`PAPER`** | `Shift + Esc` shortcut, confirmation dialog, `POST /api/orders/cancel-all` reachability, `AUDIT_EMERGENCY_CANCEL_ALL` logging (open order count will be `0` because paper orders auto-fill in ~100ms). |
| **`LIVE`** | Full Section 4 UAT drill (Steps 4.1–4.7): 2 resting `BUY LIMIT` orders (1 share, 5–8% below LTP) held open on the exchange, mass-cancelled via `Shift + Esc` within 500ms. |

