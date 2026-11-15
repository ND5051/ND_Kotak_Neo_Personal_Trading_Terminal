# Phase 11B Architectural Design Specification
## Market Watch & Order Ticket UI

**Document Version:** 1.0.0  
**Phase:** Phase 11B — Market Watch & Order Ticket UI  
**Target Milestone:** Sub-Milestone of M6 (Trading Terminal UI & Workbench Integration)  
**Baseline Dependencies:**
- Milestone M1–M5 Baselines Locked (`M1_BASELINE` through `M5_BASELINE`)
- Phase 10 Baseline Locked: Option Chain Workbench & Symmetrical Presets (commit `e163800`)
- Phase 11A Baseline Locked: Terminal Shell, Workspace Persistence & Dark Theme (commit `3e76b57`)
**Status:** Architectural Design (Pre-Implementation)  
**Implementation Constraint:** **Design specification only — Zero production implementation code generated in this phase**.

---

## Scope Exclusions (Strict Project Governance)

In strict adherence to the **PROJECT_CONSTITUTION** and terminal safety invariants:

- ❌ **No Autonomous Trading / Algorithmic Bots**: All order creations, modifications, and cancellations are exclusively human-initiated via UI clicks or explicit keyboard shortcuts.
- ❌ **No Background Market Scanners**: Zero autonomous polling loops placing trades based on price or volume thresholds.
- ❌ **No Greeks / Volatility Analytics**: Calculation of Black-Scholes Greeks (Delta, Gamma, Theta, Vega, Rho) and IV surfaces remains strictly excluded.
- ❌ **No Direct Wire Bypassing**: The UI never communicates with raw broker wire endpoints. All order actions flow through:
  $$\text{Order Ticket UI} \longrightarrow \text{Flask REST API} \longrightarrow \text{OrderExecutionService} \longrightarrow \text{ExecutionMode Gating} \longrightarrow \text{KotakOrderAdapter}$$
- ❌ **No Optimistic UI State Updates**: The UI never displays an order as `PLACED` or `FILLED` until verified by backend reconciliation and EventBus broadcast ("The Golden Rule").

---

## 1. Executive Summary & Integration Architecture

Phase 11B builds upon the **Phase 11A Terminal Shell** to deliver the two primary daily interaction surfaces of the terminal:
1. **The Market Watch Grid & Scrip Discovery Engine:** High-density, 5-tab watchlist manager with real-time WebSocket tick updates, instant fuzzy scrip search (`Ctrl+K`), 5-level Market Depth DOM popovers, and 1-click option chain navigation.
2. **The Professional Order Ticket:** Zerodha Kite-inspired docked/floating order entry window with dedicated Buy (Blue) and Sell (Orange/Red) workflows, lot size steppers, tick modulo enforcement ($0.05$), real-time pre-flight dry-run validation, live margin preview, and strict `ExecutionMode` safety controls.

```
+-------------------------------------------------------------------------------------------------------+
|                                    PHASE 11B INTEGRATION TOPOLOGY                                     |
|                                                                                                       |
|    [ SFeed WebSocket Stream ] (Phase 4)                [ Broker Scrip Master / Instruments ]           |
|                |                                                        |                             |
|                v Real-time Touchlines                                   v Search & Contracts          |
|   +----------------------------+                       +----------------------------+                 |
|   |   Market Watch Grid (11B)  |<--------------------->| Global Search Modal Ctrl+K |                 |
|   +----------------------------+                       +----------------------------+                 |
|      |               |                                                |                               |
|      | [Depth]       | [Chain] Shortcut                               | [B] / [S] Quick Actions       |
|      v               v                                                v                               |
|   +-----------+   +---------------------------+       +------------------------------------+          |
|   | 5-Level   |   | Phase 10 Option Chain     |       |       Order Ticket Window (11B)    |          |
|   | DOM Depth |   | Workbench (/api/option-   |       |   - BUY (Blue) / SELL (Orange)     |          |
|   +-----------+   |            chain/)        |       |   - MIS / NRML / CNC Product       |          |
|                   +---------------------------+       |   - LMT / MKT / SL / SL-M Type     |          |
|                                 |                     +------------------------------------+          |
|                                 | [1-Click Add]                         |                             |
|                                 v                                       v                             |
|                   +---------------------------+       +------------------------------------+          |
|                   | Phase 5 Watchlist Service |       | Phase 8 Order Execution Engine     |          |
|                   |  - 50 Scrips Quota        |       |  - ExecutionMode: DISABLED/PAPER/  |          |
|                   |  - Unique Constraints     |       |                   LIVE             |          |
|                   |  - Drag-and-drop Reorder  |       |  - Pre-flight Validation (/validate|          |
|                   +---------------------------+       |  - Margin Preview (Phase 6 Margin) |          |
|                                                       +------------------------------------+          |
+-------------------------------------------------------------------------------------------------------+
```

---

## 2. Core Functional Specifications

### 2.1. Watchlist UI & Tabbed Management
The Market Watch left sidebar hosts up to 5 discrete watchlists, persisting active tabs and item order.

```
+--------------------------------------------------------------------+
| MARKET WATCH                                           Quota: 18/50|
| [Search Scrip / Symbol... (Ctrl+K or /)                ] [ + Add ] |
|--------------------------------------------------------------------|
| [WL 1: Indices ★] [WL 2: High Beta] [WL 3: F&O] [WL 4] [WL 5]      |
+--------------------------------------------------------------------+
```

#### Key Architectural Requirements:
1. **5-Tab Navigation Bar:**
   - Tabs labelled 1 through 5, supporting custom naming (e.g. "Indices", "Options Active", "BankNifty").
   - Double-clicking tab header activates inline text edit mode, saving title via `PATCH /api/market-watch/watchlists/{id}`.
   - Pinned default watchlist marked with a star badge (`★`).
2. **Quota & Capacity Enforcement:**
   - Real-time indicator displaying scrip count vs maximum capacity (e.g. `18/50`).
   - If count equals 50, the `+ Add` button and search results disable pinning with an informative tooltip (`Watchlist Quota Exceeded`).
3. **Workspace Persistence Integration:**
   - Active tab ID persists across page refreshes via `WorkspaceManager.set('selected_watchlist_id', id)`.
4. **Drag-and-Drop Reordering:**
   - HTML5 draggable rows with smooth transition animations.
   - Dropping a scrip sends an array of reordered tokens to `POST /api/market-watch/watchlists/{id}/reorder`.

---

### 2.2. Market Watch Grid & Scrip Row Architecture

```
+--------------------------------------------------------------------+
| NIFTY 28NOV 24500 CE              NFO     142.50  +12.40 (+9.53%)  |
|   Vol: 2.4M | OI: 115.4K                  L: 110.00 | H: 165.20    |
|   [ B ] [ S ] [ Depth (D) ] [ Chain (O) ] [ Chart ] [ x Delete ]   |
|--------------------------------------------------------------------|
| NIFTY 28NOV 24500 PE              NFO      98.20   -8.10 (-7.62%)  |
|   Vol: 1.8M | OI: 95.1K                   L: 85.00  | H: 122.50    |
|   [ B ] [ S ] [ Depth (D) ] [ Chain (O) ] [ Chart ] [ x Delete ]   |
|--------------------------------------------------------------------|
| RELIANCE EQ                       NSE    2945.00  +15.50 (+0.53%)  |
|   Vol: 8.2M | ATP: 2938.40                L: 2920.0 | H: 2955.0    |
|   [ B ] [ S ] [ Depth (D) ] [ Chain (O) ] [ Chart ] [ x Delete ]   |
+--------------------------------------------------------------------+
```

#### Scrip Row Elements:
- **Left Column:** Trading Symbol (bold), Exchange Segment badge (`NSE`, `BSE`, `NFO`, `BFO`). For F&O contracts: Expiry Date (`28NOV`), Strike (`24500`), and Option Type (`CE`/`PE`).
- **Right Column:** Last Traded Price (large monospace), Absolute Change, and Percentage Change.
- **Directional Tick Pulses:**
  - Uptick: Cell flashes with green glow (`.tick-up`).
  - Downtick: Cell flashes with red glow (`.tick-down`).
- **Quick Action Hover Bar (Appears on row hover or keyboard navigation):**
  - `[ B ]` (Blue): Opens Order Ticket pre-filled in **BUY** mode.
  - `[ S ]` (Orange/Red): Opens Order Ticket pre-filled in **SELL** mode.
  - `[ Depth ]` (Gray): Opens 5-level Market Depth DOM popover (Hotkey: `D`).
  - `[ Chain ]` (Purple): Switches primary workspace to Phase 10 Option Chain filtered to this scrip's underlying (Hotkey: `O`).
  - `[ Delete ]` (Red ghost): Unpins scrip, triggering `DELETE /api/market-watch/watchlists/{id}/items/{item_id}` and WebSocket unsubscription.
- **Empty State:**
  - If a watchlist is empty, renders an intuitive onboarding card with a 1-click button to open Scrip Search (`Ctrl+K`).

---

### 2.3. Unified Scrip Search Command Palette (`Ctrl+K` or `/`)

```
+--------------------------------------------------------------------+
|  SEARCH INSTRUMENTS                                       [ Esc ]  |
|  [🔍 Type symbol or strike, e.g. "NIFTY 24500 CE" or "RELIANCE"   ] |
|--------------------------------------------------------------------|
|  Filter: [ (●) ALL ]  [ NSE ]  [ BSE ]  [ NFO ]  [ BFO ]           |
|--------------------------------------------------------------------|
|  NIFTY 28NOV 24500 CE   Index Option (NFO)    142.50  [+ Add] [B]  |
|  NIFTY 28NOV 24500 PE   Index Option (NFO)     98.20  [+ Add] [B]  |
|  NIFTY 28NOV 24600 CE   Index Option (NFO)     88.75  [+ Add] [B]  |
|  RELIANCE EQ            Equity Share (NSE)   2945.00  [+ Add] [B]  |
|  HDFCBANK EQ            Equity Share (NSE)   1680.20  [+ Add] [B]  |
|--------------------------------------------------------------------|
|  Use ↑ ↓ to navigate | Enter to add to active watchlist | Esc close|
+--------------------------------------------------------------------+
```

#### Functional Requirements:
1. **Instant Keyboard Trigger:** Opened from anywhere in the terminal by pressing `/` or `Ctrl + K`.
2. **Debounced Query Execution ($150\text{ ms}$):**
   - Queries `GET /api/market-watch/search?q={query}&segment={segment}` against the cached broker scrip master.
3. **Segment Filter Pills:**
   - Allows instant narrowing to Cash (`NSE`/`BSE`) or Derivatives (`NFO`/`BFO`).
4. **Keyboard-Driven Selection:**
   - `↑` and `↓` arrow keys move active selection highlight.
   - `Enter` adds selected scrip to the active watchlist and triggers `SubscriptionManager.subscribe(...)`.
   - `B` / `S` opens the Order Ticket immediately for the highlighted search result without requiring prior watchlist addition.

---

### 2.4. 5-Level Market Depth DOM Popover

```
+--------------------------------------------------------------------+
| MARKET DEPTH: NIFTY 28NOV 24500 CE                       [ x Close]|
| NSE | NFO | Token: 45210 | Divisor: 100                            |
+--------------------------------------------------------------------+
|          BIDS (BUY ORDERS)         |         ASKS (SELL ORDERS)    |
| Orders | Quantity | Price (₹)      | Price (₹)      | Qty   | Ords |
|--------+----------+----------------+----------------+-------+------|
|     12 |      600 | 142.45  [====] | [=====] 142.55 |   750 |   15 |
|     24 |    1,250 | 142.40  [=== ] | [======]142.60 | 1,100 |   21 |
|      8 |      450 | 142.35  [==  ] | [===   ]142.65 |   500 |    9 |
|     15 |      800 | 142.30  [====] | [====  ]142.70 |   650 |   11 |
|     31 |    1,800 | 142.25  [====] | [=======142.75 | 1,450 |   28 |
|--------+----------+----------------+----------------+-------+------|
| Total: |    4,900 | (47.3%)        | (52.7%)        | 5,450 | Total|
+--------------------------------------------------------------------+
| Ratio Bar: [====================|========================]         |
| Open: 125.00  | High: 165.20  | Low: 110.00  | Close: 130.10       |
| Volume: 2,410,500 | ATP: 141.20 | OI: 115,400 (Chg: +25,100)       |
| Lower Circuit: 25.50           | Upper Circuit: 285.00             |
+--------------------------------------------------------------------+
| [ BUY (B) ]                                            [ SELL (S) ]|
+--------------------------------------------------------------------+
```

#### Depth Architecture:
- **Depth Proportions:** Visual horizontal bar graphs behind Bid and Ask quantities indicating liquidity concentration.
- **Buyer/Seller Pressure Bar:** Dynamic dual-color ratio bar displaying $\frac{\sum \text{Bid Qty}}{\sum \text{Bid Qty} + \sum \text{Ask Qty}}$ vs $\frac{\sum \text{Ask Qty}}{\sum \text{Bid Qty} + \sum \text{Ask Qty}}$.
- **Statistical Cards:** OHLC, Average Traded Price (ATP), Traded Volume, Open Interest, and Exchange Circuit Limits.
- **Quick Action Triggers:** Bottom buttons `[BUY (B)]` and `[SELL (S)]` launch Order Ticket directly.

---

### 2.5. Order Ticket UI Architecture

```
+--------------------------------------------------------------------+
| [ BUY ]   NIFTY 28NOV 24500 CE                          [ x Close ]|
| NSE | NFO | Lot: 25 | Tick: 0.05 | Freeze: 1,800                   |
+--------------------------------------------------------------------+
| SIDE:           (●) BUY (Blue Theme)   ( ) SELL (Orange Theme)     |
+--------------------------------------------------------------------+
| PRODUCT:        (●) MIS (Intraday)     ( ) NRML (F&O)   ( ) CNC    |
+--------------------------------------------------------------------+
| ORDER TYPE:     (●) LIMIT    ( ) MARKET    ( ) SL     ( ) SL-M     |
+--------------------------------------------------------------------+
| QUANTITY (Lots):                                                   |
|   [ - ]   [   25  ] Lots: 1   [ + ]      Max per order: 1,800      |
|                                                                    |
| PRICE (₹):                                                         |
|   [ -0.05 ]  [  142.50  ]  [ +0.05 ]     LTP: 142.50 | Ask: 142.55 |
|                                                                    |
| TRIGGER PRICE (₹) (Conditional for SL / SL-M):                     |
|   [ -0.05 ]  [  ------  ]  [ +0.05 ]     Disabled for LIMIT/MKT    |
|                                                                    |
| DISCLOSED QUANTITY (Optional):                                     |
|   [   0   ]  (0 = full quantity disclosed)                         |
+--------------------------------------------------------------------+
| MARKET PROTECTION: [======|=========] 2% (Clamps market slippage)  |
+--------------------------------------------------------------------+
| PRE-FLIGHT VALIDATION:                                             |
|   ✓ NSE Tick Size Modulo (0.05) Valid                              |
|   ✓ Derivatives Lot Size Multiple (x25) Valid                      |
|   ✓ Freeze Limit Quantity (< 1,800) Valid                          |
+--------------------------------------------------------------------+
| MARGIN & EXECUTION PREVIEW:                                        |
|   Required Margin:  ₹3,562.50        Available Cash: ₹2,45,000.00  |
|   Margin Buffer:    +₹2,41,437.50    Status: SUFFICIENT FUNDS      |
|   Execution Mode:   [ PAPER MODE ] (Simulator active; wire locked) |
+--------------------------------------------------------------------+
| [ CANCEL (Esc) ]                         [ SUBMIT BUY ORDER (Enter)]|
+--------------------------------------------------------------------+
```

---

### 2.6. Dedicated Buy Workflow
1. **Trigger:** User clicks `[B]` on Market Watch row, presses `B` on focused row, clicks `[B]` in Search modal, or clicks `[B]` on Option Chain strike.
2. **Context Hydration:**
   - Ticket opens with primary blue theme (`#1b73e8`).
   - Radio initialized to `BUY`.
   - Pre-fills instrument token, trading symbol, exchange segment, and minimum lot size.
   - Price defaults to current **Best Ask** (touchline depth).
3. **Lot Multiplier Logic:**
   - Clicking `[+]` increments quantity by exactly $1 \times \text{lot\_size}$ ($25$ for NIFTY, $15$ for BANKNIFTY).
4. **Validation Debounce ($200\text{ ms}$):**
   - Dispatches payload to `POST /api/orders/validate` (Phase 8 dry-run engine).
   - Verifies tick size modulo, stop-loss trigger sanity, and margin availability.
5. **Execution Dispatch:**
   - Operator presses `Enter` or clicks `[SUBMIT BUY ORDER]`.
   - Dispatches payload to `POST /api/orders`.
   - Button enters `SUBMITTING...` state (double-click disabled).
   - On response: emits success toast, sounds optional execution chime, and updates Order Book badge.

---

### 2.7. Dedicated Sell Workflow
1. **Trigger:** User clicks `[S]` on Market Watch row, presses `S` on focused row, clicks `[S]` in Search modal, or clicks `Exit` on Portfolio position.
2. **Context Hydration:**
   - Ticket opens with primary orange/red theme (`#ff5722`).
   - Radio initialized to `SELL`.
   - Pre-fills instrument metadata.
   - Price defaults to current **Best Bid** (touchline depth).
3. **Delivery & Intraday Gating:**
   - If Product = `CNC` (Cash & Carry Equity): System performs pre-check against Phase 6 Holdings to ensure available shares exist; if unheld, displays short-selling delivery warning.
   - If Product = `MIS` or `NRML`: Short selling is permitted, and option writing margin requirements are computed.
4. **Validation & Margin Check:**
   - For option selling (writing), verifies high margin requirements ($\approx ₹1.5\text{L}$ per lot for index options) against Available Margin.
5. **Execution Dispatch:**
   - Dispatches to `POST /api/orders`.
   - If `ExecutionMode = DISABLED`, wire submission is refused with HTTP 403 `EXECUTION_MODE_DISABLED`.

---

### 2.8. Pre-Flight Order Validation UI
The Order Ticket prevents invalid orders from reaching the exchange wire by evaluating Phase 7 & 8 validation rules locally in real time:

| Validation Rule | Condition | Visual UI Behavior |
|:---|:---|:---|
| **Tick Size Modulo** | $\text{Price} \pmod{0.05} \neq 0$ | Input border turns red; displays error *"Price must be a multiple of 0.05"*; auto-correct button appears. |
| **Lot Size Multiple** | $\text{Qty} \pmod{\text{Lot Size}} \neq 0$ | Input border turns red; displays error *"Quantity must be a multiple of lot size (25)"*. |
| **Freeze Limit** | $\text{Qty} > \text{Freeze Qty}$ | Error banner: *"Quantity exceeds exchange freeze limit (1,800). Split order required."* |
| **SL Trigger Sanity (Buy)** | $\text{Trigger Price} < \text{LTP}$ | Warning: *"Buy Stop-Loss trigger must be $\ge$ current market price."* |
| **SL Trigger Sanity (Sell)** | $\text{Trigger Price} > \text{LTP}$ | Warning: *"Sell Stop-Loss trigger must be $\le$ current market price."* |
| **Disclosed Quantity** | $0 < \text{Disclosed} < 0.1 \times \text{Qty}$ | Error: *"Disclosed quantity must be at least 10% of total quantity."* |

---

### 2.9. Real-Time Margin Preview
The ticket provides immediate visibility into margin sufficiency prior to order submission:
1. **Debounced Query Execution:**
   - Upon quantity, price, or product type modification, the ticket queries `POST /api/orders/validate`.
2. **Calculated Metrics Displayed:**
   - **Required Margin:** Total funds locked by this order (Span + Exposure for F&O, $100\%$ for CNC buy).
   - **Available Cash:** Current usable margin from Phase 6 `MarginSummary`.
   - **Buffer / Shortfall:** $\text{Available Cash} - \text{Required Margin}$.
3. **Insufficient Funds State:**
   - If $\text{Shortfall} < 0$:
     - Buffer value renders in bold red: `-₹12,450.00`.
     - Submit button is disabled.
     - Displays call-to-action warning: *"Insufficient margin to execute order."*

---

### 2.10. ExecutionMode Visual Controls & Safety Locks
The Order Ticket strictly inherits the terminal's global `ExecutionMode`:

```
+--------------------------------------------------------------------+
| EXECUTION MODE STATUS IN ORDER TICKET:                             |
|                                                                    |
| [ MODE: DISABLED ] -> Crimson Banner: "EXECUTION LOCKED"          |
|                       Submit button is disabled (Grayed out)       |
|                       Tooltip: "Enable PAPER or LIVE mode in header|
|                                                                    |
| [ MODE: PAPER ]    -> Amber Banner: "PAPER SIMULATION MODE"        |
|                       Submit button: [ SUBMIT PAPER ORDER ]        |
|                       Simulates fill without exchange wire risk   |
|                                                                    |
| [ MODE: LIVE ]     -> Emerald Banner: "EXCHANGE WIRE ACTIVE 🛡️"    |
|                       Submit button: [ SUBMIT REAL ORDER (LIVE) ]  |
|                       Real money risk on NSE/BSE exchange wire     |
+--------------------------------------------------------------------+
```

---

### 2.11. Complete Keyboard Shortcut Matrix

| Key / Shortcut | Scope | Action |
|:---|:---|:---|
| `Ctrl + K` or `/` | Global Terminal | Open Scrip Search Command Palette |
| `B` | Focused Scrip Row | Open Order Ticket in **BUY** mode |
| `S` | Focused Scrip Row | Open Order Ticket in **SELL** mode |
| `D` | Focused Scrip Row | Toggle **5-Level Market Depth** popover |
| `O` | Focused Scrip Row | Switch to **Option Chain** for focused underlying |
| `Delete` | Focused Scrip Row | Remove scrip from active watchlist |
| `↑` / `↓` | Watchlist / Search | Navigate up / down scrip rows |
| `Enter` | Search Result | Pin selected scrip to active watchlist |
| `Enter` | Order Ticket | Submit Order |
| `Tab` / `Shift + Tab` | Order Ticket | Cycle between Qty, Price, Trigger Price, Submit |
| `Esc` | Modal / Ticket | Close Search Palette, Depth Popover, or Order Ticket |
| `Alt + C` | Global Terminal | Toggle **Compact Mode** (High density) |
| `Shift + Esc` | Global Terminal | Open **Emergency Cancel All** confirmation |

---

### 2.12. Responsive Mobile & Tablet Ergonomics

```
+--------------------------------------------------------------------+
| MOBILE RESPONSIVE BEHAVIOR (< 768px Viewport)                      |
|                                                                    |
| 1. Market Watch View:                                              |
|    - Occupies full mobile width with swipeable watchlist tabs.     |
|    - Tapping a row opens an action bottom-sheet:                   |
|      [ BUY (Blue) ]   [ SELL (Red) ]   [ Depth ]   [ Option Chain] |
|                                                                    |
| 2. Order Ticket as Bottom Sheet:                                   |
|    - Slides up smoothly from bottom covering 85% of screen height. |
|    - Touch-optimized lot steppers (+ / - buttons >= 48px height).  |
|    - Swipe down to dismiss ticket.                                 |
|                                                                    |
| 3. Mobile Scrip Search:                                            |
|    - Full-screen modal overlay with virtual keyboard autofocus.    |
+--------------------------------------------------------------------+
```

---

## 3. Integration Specifications

### 3.1. Phase 5 Watchlist Integration
- **Scrip Persistence:**
  - `POST /api/market-watch/watchlists/{id}/items`: Adds scrip and immediately invokes `subscription_manager.subscribe(token, segment)`.
  - `DELETE /api/market-watch/watchlists/{id}/items/{item_id}`: Removes scrip and invokes `subscription_manager.unsubscribe(token, segment)` if reference count hits zero.
- **Quota Validation:**
  - Evaluates `MAX_SCRIPS_PER_WATCHLIST = 50` before sending network requests.

### 3.2. Phase 8 Order Execution Engine Integration
- **Pre-Flight Dry Run:**
  - Order Ticket debounces inputs and calls `POST /api/orders/validate` passing `dry_run=True`.
- **Order Placement:**
  - Form submission dispatches to `POST /api/orders`.
  - Payload incorporates client idempotency key (`client_order_id`) to prevent duplicate submissions from rapid clicks.

### 3.3. Phase 6 Portfolio Foundation Integration
- **Live Margin Synchronization:**
  - Consumes `GET /api/portfolio/margins` to retrieve live `available_cash` and `total_margin_used`.
- **Holdings CNC Exit Linkage:**
  - Clicking `[Exit]` in Holdings pre-populates Order Ticket in `SELL` mode with exact held quantity.

### 3.4. Phase 10 Option Chain Integration
- **Direct Navigation Link:**
  - Clicking `[Chain (O)]` on an option contract or index scrip row switches the primary workspace tab to Option Chain and selects the matching underlying and expiry date.

---

## 4. Test & Verification Strategy for Phase 11B

Phase 11B implementation will be validated through a comprehensive test suite:

1. **Watchlist & Scrip Row Tests (`test_watchlist_ui.py`):**
   - Verify tab switching and active tab persistence.
   - Verify scrip addition, deletion, and 50-item quota lockout.
   - Verify drag-and-drop reordering API payload generation.
2. **Search Palette Tests (`test_search_modal.py`):**
   - Verify debounced search queries and segment filtering (`NSE`, `NFO`).
   - Verify keyboard navigation (`↑`, `↓`, `Enter`) adds scrips to watchlist.
3. **Market Depth Tests (`test_market_depth.py`):**
   - Verify 5-level Bid/Ask table rendering and total quantity ratio calculations.
4. **Order Ticket & Validation Tests (`test_order_ticket.py`):**
   - Verify Buy (Blue) vs Sell (Orange/Red) theme switching.
   - Verify lot stepper multiplier and tick modulo auto-rounding ($0.05$).
   - Verify pre-flight validation catches invalid stop-loss triggers and freeze limits.
   - Verify margin shortfall disables submit button.
   - Verify `ExecutionMode = DISABLED` disables submit button.
5. **Full Regression Guarantee:**
   - Zero regressions across existing 194 automated tests.

---

## 5. Deliverables Summary

Upon approval of this specification, implementation of Phase 11B will deliver:
1. `templates/components/market_watch_grid.html`: Multi-tab watchlist container, scrip list, hover actions, and quota badge.
2. `templates/components/scrip_search_modal.html`: Command palette for global instrument discovery.
3. `templates/components/market_depth_modal.html`: 5-level DOM depth popover with buyer/seller ratio bar.
4. `templates/components/order_ticket.html`: Kite-inspired docked/floating order ticket with live validation.
5. `static/css/market_watch.css`: Dedicated grid styling, depth bars, hover action animations, and buy/sell color schemes.
6. `static/js/market_watch.js`: Watchlist state management, search debounce, depth popovers, and SFeed WebSocket DOM binding.
7. `static/js/order_ticket.js`: Ticket state, lot multiplier, pre-flight validation queries, and order submission.
8. `tests/integration/test_market_watch_ui_routes.py`: Comprehensive test suite verifying all Phase 11B UI endpoints and components.
9. `PHASE11B_ARCHITECTURE_REVIEW.md`: Post-implementation architectural audit.

