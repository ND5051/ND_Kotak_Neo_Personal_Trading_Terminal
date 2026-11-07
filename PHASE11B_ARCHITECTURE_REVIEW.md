# Phase 11B Architecture Review: Market Watch & Order Ticket UI

**Document Version:** 1.0.0  
**Phase:** Phase 11B (Market Watch & Order Ticket UI)  
**Target Milestone:** Sub-Milestone of M6 (Trading Terminal UI & Workbench Integration)  
**Status:** Completed & Validated  
**Date:** 2026-11-07  

---

## 1. Executive Summary

Phase 11B delivers the primary trading and market-monitoring interfaces of the **Kotak Neo Personal Trading Terminal**: the **Market Watch Grid** and the **Professional Order Ticket**. Engineered with the speed, clarity, and ergonomics of **Zerodha Kite**, this phase integrates real-time touchline market data with defensive order execution pipelines.

All implementations strictly adhere to the project's constitutional mandates:

1. **Human-Initiated Execution Only:** Every single order creation, modification, and cancellation is initiated strictly by explicit operator click or keyboard shortcut. Zero autonomous bots or unprompted background trade loops exist.
2. **Defensive Order Hierarchy:** The Order Ticket routes exclusively through:
   $$\text{OrderTicket UI} \longrightarrow \text{Flask /api/orders/place} \longrightarrow \text{OrderExecutionService} \longrightarrow \text{ExecutionMode Gating} \longrightarrow \text{KotakOrderAdapter}$$
   Direct broker wire bypass is architecturally prohibited.
3. **ExecutionMode Safety Enforcement:** All order placements strictly inherit the terminal's global `ExecutionMode` (`DISABLED`, `PAPER`, `LIVE`). In `DISABLED` mode, the submit button is locked out with an explicit red warning banner.
4. **The Golden Rule Compliance:** Absence of broker or quote data renders strictly as `—` or `NONE`. No synthetic prices or optimistic UI assumptions are permitted.
5. **Strict Scope Exclusions:**
   - ❌ **No Greeks Engine:** No Black-Scholes Delta, Gamma, Theta, Vega, or Rho derivations.
   - ❌ **No Volatility Analytics:** No IV surfaces, IV rank, or skew calculations.
   - ❌ **No Automated Scanner Engine:** No background scanners executing trades on price/volume thresholds.
   - ❌ **No Copy Trading or AI Signals:** All decisions remain strictly manual.

---

## 2. Component Hierarchy & System Architecture

```
+-------------------------------------------------------------------------------------------------------+
|                                    PHASE 11B SYSTEM ARCHITECTURE                                      |
|                                                                                                       |
|  [ Operator Browser / Desktop Cockpit: /terminal ]                                                    |
|            |                                                                                          |
|            +---> [ Left Pane: components/market_watch_grid.html ]                                     |
|            |       ├── 5-Tab Watchlist Bar (Watchlist 1 to 5, Default ★, Custom Rename)               |
|            |       ├── Scrip Quota Badge (18/50 Scrips counter)                                       |
|            |       ├── Scrip Rows: Symbol, Segment (NSE/NFO), Expiry, Strike, LTP, Chg, % Chg         |
|            |       ├── Directional Tick Pulses (.tick-up green, .tick-down red)                       |
|            |       ├── HTML5 Drag-and-Drop Reordering (PUT /api/market-watch/watchlists/{id}/reorder)  |
|            |       └── Hover Action Bar: [B] Buy, [S] Sell, [D] Depth, [O] Chain, [x] Delete          |
|            |                                                                                          |
|            +---> [ Scrip Search Command Palette: components/scrip_search_modal.html ]                 |
|            |       ├── Keyboard Triggers: Ctrl+K or / from anywhere in the terminal                   |
|            |       ├── Debounced Input (150ms) -> GET /api/market-watch/search                       |
|            |       ├── Segment Filter Pills: ALL, NSE, BSE, NFO, BFO                                  |
|            |       ├── Quick Suggest Tags (NIFTY, BANKNIFTY, RELIANCE, HDFCBANK)                      |
|            |       └── Arrow Key Navigation (↑, ↓, Enter to add, B/S to trade)                        |
|            |                                                                                          |
|            +---> [ 5-Level Market Depth DOM: components/market_depth_modal.html ]                     |
|            |       ├── Best 5 Bids (Orders, Qty, Price) vs Best 5 Asks (Price, Qty, Orders)           |
|            |       ├── Dynamic Buyer/Seller Liquidity Pressure Bar                                    |
|            |       ├── OHLC, ATP, Volume, Open Interest, Lower/Upper Circuit Bands                   |
|            |       └── Bottom Action Buttons: [BUY (B)] and [SELL (S)]                                |
|            |                                                                                          |
|            +---> [ Professional Order Ticket: components/order_ticket.html ]                          |
|            |       ├── Docked Bottom Drawer (Default) & Floating Centered Modal Toggle (⤢ / ⤡)        |
|            |       ├── BUY Workflow: Blue Theme (#1b73e8), Best Ask pre-fill                          |
|            |       ├── SELL Workflow: Orange/Red Theme (#ff5722), Best Bid pre-fill                   |
|            |       ├── Product Selection: MIS (Intraday), NRML (F&O), CNC (Delivery)                  |
|            |       ├── Order Types: LIMIT, MARKET, SL (Stop-Loss Limit), SL-M (Stop-Loss Market)     |
|            |       ├── Lot Multiplier Steppers ([+] / [-] by instrument lot size: 25, 15, etc.)      |
|            |       ├── Price Steppers & Modulo Auto-Rounding (0.05 tick size)                         |
|            |       ├── Pre-Flight Dry-Run Validation (POST /api/orders/validate)                      |
|            |       ├── Margin Preview Strip (Required Margin vs Available Cash from Phase 6)          |
|            |       ├── ExecutionMode Gating Banner (DISABLED, PAPER, LIVE)                            |
|            |       └── Submit Dispatch: POST /api/orders/place with client_order_id idempotency       |
|            |                                                                                          |
|            +---> [ Client Controllers: static/js/ ]                                                   |
|                    ├── market_watch.js (Watchlists, Search, Depth DOM, Drag & Drop, Hotkeys)          |
|                    └── order_ticket.js (Ticket state, Lot math, Validation debouncing, Submission)    |
+-------------------------------------------------------------------------------------------------------+
```

---

## 3. Dedicated Architectural Scope Audits

### 3.1. Audit Item 1: Watchlist UI & Tabbed Management
- **5-Tab Navigation Bar:** Tabbed container supporting up to 5 user watchlists.
- **Default Indicator:** Pinned default watchlist distinguished with a star badge (`★`).
- **Inline Renaming:** Double-clicking or clicking the edit button (`✏️`) prompts the user and commits title updates via `PATCH /api/market-watch/watchlists/{id}`.
- **Quota Tracking:** Prominent `18/50` counter enforces Phase 5 constraints; locks further scrip addition once capacity is reached.
- **Persistence:** Selected watchlist tab persists across reloads via `WorkspaceManager.set('selected_watchlist_id', id)`.

### 3.2. Audit Item 2: Market Watch Grid & Scrip Row Architecture
- **Tabular Data Hierarchy:** Displays Trading Symbol, Exchange Segment pill (`NSE`, `BSE`, `NFO`, `BFO`), F&O metadata, LTP, Absolute Change, and Percentage Change.
- **Directional Tick Pulses:** Real-time visual feedback via CSS animations (`.tick-up` green pulse, `.tick-down` red pulse).
- **Hover Action Bar:** On row hover or keyboard focus, reveals `[B]`, `[S]`, `[Depth]`, `[Chain]`, and `[Delete]`.
- **Empty State:** If a watchlist contains zero scrips, renders an onboarding banner with a single-click search trigger.

### 3.3. Audit Item 3: Ctrl+K / `/` Scrip Search Command Palette
- **Unified Command Palette:** Launched from anywhere in the terminal via `/` or `Ctrl + K`.
- **Debounced Execution ($150\text{ ms}$):** Queries `GET /api/market-watch/search` against the instrument master cache.
- **Segment Filter Pills:** Instant filtering by segment (`ALL`, `NSE`, `BSE`, `NFO`, `BFO`).
- **Keyboard Navigation:** `↑` and `↓` navigate search results; `Enter` pins to the active watchlist; `B`/`S` opens the Order Ticket directly.

### 3.4. Audit Item 4: Watchlist Tabs Synchronization
- Tabs integrate seamlessly with the Phase 5 backend API:
  - `GET /api/market-watch/watchlists` retrieves all user watchlists and quotes.
  - Adding or deleting watchlists automatically notifies `SubscriptionManager` to maintain reference-counted WebSocket streams.

### 3.5. Audit Item 5: Drag & Drop Reordering
- Implemented using the native HTML5 Drag and Drop API (`dragstart`, `dragover`, `drop`, `dragend`).
- Dropping a scrip row dynamically reorders the in-memory array and synchronizes the sequence with the backend via `PUT /api/market-watch/watchlists/{id}/reorder`.

### 3.6. Audit Item 6: 5-Level Market Depth DOM Popover
- Triggered via `[Depth]` button or `D` hotkey on any focused scrip row.
- **Bid/Ask Ladder:** 5 best bids (Orders, Qty, Price) vs 5 best asks (Price, Qty, Orders) with visual depth bars.
- **Liquidity Pressure Bar:** Dual-colored horizontal ratio bar representing $\frac{\text{Bid Qty}}{\text{Total Qty}}$ vs $\frac{\text{Ask Qty}}{\text{Total Qty}}$.
- **Market Statistics:** OHLC, ATP, Traded Volume, Open Interest, Lower Circuit, and Upper Circuit limits.
- **Direct Trading Triggers:** `[BUY (B)]` and `[SELL (S)]` action buttons open the Order Ticket pre-filled with best prices.

### 3.7. Audit Item 7: Buy Button Workflow
- Triggered by `[B]` on Market Watch row, search result, market depth, or hotkey `B`.
- Header dynamically adopts the institutional blue theme (`#1b73e8`).
- Quantity defaults to minimum instrument lot size ($25$ for NIFTY, $15$ for BANKNIFTY).
- Price pre-fills with the current **Best Ask** price to minimize execution slippage.
- Submit button displays `BUY ORDER (Enter)`.

### 3.8. Audit Item 8: Sell Button Workflow
- Triggered by `[S]` on Market Watch row, search result, market depth, or hotkey `S`.
- Header dynamically adopts the orange/red theme (`#ff5722`).
- Price pre-fills with the current **Best Bid** price.
- **Delivery Pre-Check:** If product is `CNC` (Cash & Carry Equity), verifies share availability against Phase 6 Holdings to warn against unheld short selling.
- Submit button displays `SELL ORDER (Enter)`.

### 3.9. Audit Item 9: Docked Order Ticket
- Default display mode anchors the ticket to the bottom-right viewport drawer (`docked`).
- Operates non-obtrusively, allowing the trader to monitor market watch, option chain, and portfolio positions while staging orders.

### 3.10. Audit Item 10: Floating Order Ticket
- Clicking the expand control (`⤢`) shifts the ticket into a centered, draggable modal window (`floating`).
- Operator can toggle back to docked mode (`⤡`) with a single click.

### 3.11. Audit Item 11: Real-Time Margin Preview
- Queries Phase 6 `GET /api/portfolio/margins` and dry-run pre-flight validation.
- Calculates and displays:
  - **Required Margin:** Estimated span and exposure requirement for F&O, or notional value for CNC.
  - **Available Cash:** Current usable balance.
  - **Margin Status Badge:** Displays green `SUFFICIENT MARGIN` or red `INSUFFICIENT FUNDS`.
- Insufficient funds disable the submit button and provide actionable feedback.

### 3.12. Audit Item 12: Order Validation Preview
- Pre-flight dry-run validation (`POST /api/orders/validate` with `dry_run=True`) evaluates:
  1. **Tick Size Modulo:** Enforces exact $0.05$ tick increments; displays red error border and corrective hints.
  2. **Lot Size Multiples:** Enforces multiples of contract lot size ($25, 15, \dots$).
  3. **Exchange Freeze Limits:** Warns if quantity exceeds $1,800$ contracts.
  4. **Stop-Loss Trigger Sanity:** Validates $\text{Trigger Price} \le \text{Price}$ for Buy SL, and $\text{Trigger Price} \ge \text{Price}$ for Sell SL.
- Validation failures disable the submit button with specific error tooltips.

### 3.13. Audit Item 13: ExecutionMode Visual Warnings
- The Order Ticket incorporates a dedicated execution mode banner:
  - `DISABLED`: Red warning banner (*"EXECUTION LOCKED: ExecutionMode is DISABLED. Order submission is blocked."*). Submit button disabled.
  - `PAPER`: Amber simulation banner (*"SIMULATION MODE: Order will be simulated in Paper Engine without wire risk."*).
  - `LIVE`: Emerald green security banner (*"EXCHANGE WIRE ACTIVE 🛡️: Real money order will be submitted to Kotak Neo."*).

### 3.14. Audit Item 14: Keyboard Shortcuts Ergonomics
- Global shortcuts:
  - `Ctrl + K` or `/`: Opens Scrip Search command palette.
  - `Alt + C`: Toggles Compact Mode.
  - `Shift + Esc`: Triggers Emergency Cancel All confirmation.
- Focused scrip shortcuts:
  - `↑` / `↓`: Navigates scrip rows.
  - `B`: Launches Order Ticket in BUY mode.
  - `S`: Launches Order Ticket in SELL mode.
  - `D`: Opens 5-level Market Depth popover.
  - `O`: Switches active workspace to Option Chain for focused underlying.
  - `Delete`: Unpins scrip from active watchlist.
- Order ticket shortcuts:
  - `Enter`: Submits order.
  - `Esc`: Dismisses ticket or modal.
  - `Tab` / `Shift + Tab`: Cycles through quantity, price, and trigger inputs.

---

## 4. Backend Integrations Verified

| Backend Module | Integration Point | Status |
|:---|:---|:---:|
| **Phase 5 Watchlists** | `GET /api/market-watch/watchlists`, `POST /items`, `DELETE /items`, `PUT /reorder` | ✅ Fully Integrated |
| **Phase 6 Portfolio** | `GET /api/portfolio/margins` for live Available Cash and Collateral | ✅ Fully Integrated |
| **Phase 8 Order Engine** | `POST /api/orders/validate` (dry run) and `POST /api/orders/place` | ✅ Fully Integrated |
| **Phase 10 Option Chain** | Direct navigation shortcut (`O` hotkey) linking Market Watch to Option Chain matrix | ✅ Fully Integrated |

---

## 5. Test Verification Matrix & Regression Analysis

All Phase 11B components and routes were verified through automated testing in `tests/integration/test_market_watch_ui_routes.py`:

| Test Name | File | Scope | Status |
|:---|:---|:---|:---:|
| `test_terminal_loads_phase11b_components` | `test_market_watch_ui_routes.py` | Verify `/terminal` loads Grid, Search Modal, Depth Popover, Order Ticket | ✅ Passed |
| `test_phase11b_static_assets_served` | `test_market_watch_ui_routes.py` | Verify `market_watch.css`, `market_watch.js`, `order_ticket.js` load (HTTP 200) | ✅ Passed |
| `test_watchlist_api_lifecycle_integration` | `test_market_watch_ui_routes.py` | Verify watchlist retrieval, item addition, and quota enforcement | ✅ Passed |
| `test_scrip_search_api_integration` | `test_market_watch_ui_routes.py` | Verify Scrip Master search endpoint returns structured instrument items | ✅ Passed |
| `test_order_preflight_validation_dry_run_endpoint` | `test_market_watch_ui_routes.py` | Verify dry-run validation catches tick size and lot size modulo errors | ✅ Passed |
| `test_order_execution_mode_paper_placement` | `test_market_watch_ui_routes.py` | Verify order execution succeeds in `PAPER` and is refused in `DISABLED` | ✅ Passed |
| **Phase 11B Subtotal** | **Market Watch & Order Ticket** | **6 new integration tests** | **100% Passed** |
| **Full Regression Suite** | **Phases 1 through 11B** | **200 total project tests** | **100% Passed (18.16s)** |

---

## 6. Conclusion & Next Steps

Phase 11B is fully implemented, structurally hardened, and validated with zero regressions across the 200 automated tests. The terminal now offers a complete, reactive daily trading workflow: finding scrips, evaluating depth, sizing orders with lot steppers, reviewing real-time margins, and dispatching orders under strict `ExecutionMode` safety governance.

We are ready to proceed with **Phase 11C: Portfolio & Order Book UI** upon instruction.
