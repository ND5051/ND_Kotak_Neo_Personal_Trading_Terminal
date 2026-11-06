# Phase 11 Architectural Design Specification
## Professional Trading Terminal UI

**Document Version:** 1.0.0  
**Phase:** Phase 11 — Professional Trading Terminal UI  
**Target Milestone:** Milestone M6 (Trading Terminal UI & Workbench Integration)  
**Baseline Dependencies:**
- Milestone M1 Baseline Locked (`M1_BASELINE`, commit `4d9341a`)
- Milestone M2 Baseline Locked (`M2_BASELINE`, commit `c4d30e6`): SFeed WebSocket Supervisor, Market Watch & Portfolio MTM
- Milestone M3 Baseline Locked (`M3_BASELINE`, commit `22dd3c8`): Order Domain Foundation, FSM & Risk Engine
- Milestone M4 Baseline Locked (`M4_BASELINE`, commit `2362ba8`): Order Execution Foundation, ExecutionMode & Audited Paper Engine
- Milestone M5 Baseline Locked (`M5_BASELINE`, commit `fcfb088`): Advanced Multi-Leg Baskets, Strategy Validation & Exposure Service
- Phase 10 Baseline Locked (commit `e163800`): Option Chain Workbench, Symmetrical Presets & OI/PCR Engine
**Status:** Architectural Design (Pre-Implementation)  
**Implementation Constraint:** **Design specification only — Zero production implementation code generated in this phase**.

---

## Scope Exclusions (Strict Project Governance)

In strict compliance with the **PROJECT_CONSTITUTION** and project architectural mandates, the following items are **explicitly excluded** from Phase 11:

- ❌ **No Autonomous Trading / Algorithmic Bots**: Zero automated trade dispatchers, algorithmic triggers, auto-entries, or unprompted square-offs. All UI workflows remain strictly human-initiated.
- ❌ **No Automated Scanner Engine**: No continuous background scanners executing automated orders based on UI conditions.
- ❌ **No Greeks / Volatility Analytics**: Calculation of Black-Scholes Greeks (Delta, Gamma, Theta, Vega, Rho) and IV surfaces remains strictly excluded.
- ❌ **No Direct Wire Bypassing**: The UI never constructs or sends raw wire requests directly to Kotak Neo APIs. All client actions flow through the established Flask REST backend $\to$ Domain Validation $\to$ Risk Service $\to$ Execution Service $\to$ `KotakOrderAdapter`.
- ❌ **No Optimistic Execution UI State**: The UI must never display an order as `FILLED` until confirmed by backend state reconciliation and WebSocket event broadcast. "Absence of data is `NONE` / `UNKNOWN`" (The Golden Rule).
- ❌ **No AI/ML Predictive Widgets**: No predictive buy/sell arrows, forecast lines, or algorithmic recommendations.

> [!IMPORTANT]
> **Core Architectural Objective of Phase 11:**  
> Phase 11 designs an institutional-grade, high-density, low-latency, dark-themed Web UI inspired by the ergonomics and speed of **Zerodha Kite**. It unifies Market Watch, Order Entry, Portfolio (Holdings & Positions), Multi-Leg Basket Builder, Option Chain Workbench, Funds Management, and System Telemetry into a coherent, responsive single-page trading cockpit.

---

## 1. Executive Summary & Ergonomic Philosophy

Professional proprietary and retail derivative traders demand an interface that is:
1. **Frictionless & Keyboard-Driven:** Traders can execute orders, switch views, navigate watchlists, and search contracts entirely through single-key shortcuts without taking their hands off the keyboard.
2. **High Information Density with Visual Hierarchy:** Clean, dark-mode styling where every pixel serves situational awareness. High-contrast monospace figures for financial amounts prevent misreading strikes or prices.
3. **Sub-Millisecond Perceived Responsiveness:** Instant UI responses, zero layout shifts, smooth micro-animations for price ticks (green/red flash), and docked modals that never obstruct the trader's view of live depth or option chains.
4. **Defensive Safety Guards:** Prominent, permanent display of the global `ExecutionMode` (`DISABLED`, `PAPER`, `LIVE`). Wire submission is locked out by default. Transitioning to `LIVE` mode requires explicit operator confirmation.

---

## 2. Global Terminal Architecture & Wireframe

### 2.1. Master Terminal Wireframe (Desktop Layout $\ge 1440$px)

```
+----------------------------------------------------------------------------------------------------------------------------------+
| [LOGO] KOTAK NEO TERMINAL | NIFTY 24,520.50 (+0.42%) | BANKNIFTY 52,180.20 (-0.15%) | SENSEX 80,410.10 (+0.38%) | [MODE: PAPER]  |
| Tabs: [MarketWatch] [Orders (3)] [Holdings (12)] [Positions (4)] [Option Chain] [Baskets (2)] [Funds]       | Health: OK (12ms)  |
+----------------------------------------------------------------------------------------------------------------------------------+
| LEFT PANE: MARKET WATCH (320px)           | CENTER PANE: PRIMARY WORKSPACE (Flex 1)                                              |
| [Search Scrip / Ctrl+K           ]        | +----------------------------------------------------------------------------------+ |
| [WL 1: Indices] [WL 2: Bank] [WL 3: F&O]  | | ACTIVE VIEW TAB: OPTION CHAIN / PORTFOLIO / BASKET / ORDERS                      | |
|-------------------------------------------| | (Dynamically rendered based on active navigation tab)                            | |
| NIFTY 28NOV 24500 CE   142.50  +12.40     | |                                                                                  | |
|   [B] [S] [Depth] [Chain] [Chart] [x]     | |                                                                                  | |
| NIFTY 28NOV 24500 PE    98.20   -8.10     | |                                                                                  | |
| BANKNIFTY 28NOV 52000 CE 320.10 +45.00    | |                                                                                  | |
| RELIANCE EQ           2945.00  +15.50     | |                                                                                  | |
| HDFCBANK EQ           1680.20   -4.30     | |                                                                                  | |
| INFOSYS EQ            1825.00  +22.10     | |                                                                                  | |
|                                           | |                                                                                  | |
|                                           | +----------------------------------------------------------------------------------+ |
|                                           | BOTTOM DRAWER: DOCKED TICKET / SYSTEM CONSOLE (Collapsible: 240px)                   |
|                                           | +----------------------------------------------------------------------------------+ |
|                                           | | [ORDER TICKET: NIFTY28NOV24500CE] [BUY] [MIS] Qty: 25 Price: 142.50 [SUBMIT (B)]  | |
| Quota: 18/50 Scrips | Stream: Active      | | Margin Req: ₹3,562.50 | Avail: ₹2,45,000.00 | Mode: PAPER | Shortfall: NONE      | |
+-------------------------------------------+--------------------------------------------------------------------------------------+
| STATUS FOOTER: SFeed: CONNECTED (28 ticks/s) | Auth: VALID (Exp: 5h 22m) | Breaker: NORMAL | Daily P&L: +₹4,820.50 (Live MTM)     |
+----------------------------------------------------------------------------------------------------------------------------------+
```

---

## 3. Detailed Component Specifications

### 3.1. Main Terminal Layout & Global Header
- **Global Ticker Strip:**
  - Displays persistent benchmark indices: `NIFTY 50`, `BANKNIFTY`, `SENSEX`.
  - Real-time touchline feeds updating via WebSocket.
  - Directional tick animations: brief green glow on uptick, red glow on downtick.
- **ExecutionMode Master Badge:**
  - States:
    - `DISABLED` (Crimson Red `#eb5757`): All order and basket submission buttons disabled across the entire terminal.
    - `PAPER` (Warning Amber `#f2994a`): Simulation mode. Orders routed to Phase 8 Paper Simulator.
    - `LIVE` (Emerald Green `#00d09c` with Security Shield icon): Real exchange wire submission enabled.
  - Clicking the badge opens the **ExecutionMode Modal**:
    - Switching to `LIVE` triggers a mandatory safety challenge requiring the user to type `"CONFIRM_LIVE"` to prevent accidental live execution.
- **Master Navigation Tabs:**
  - `Market Watch` (Focus left pane / full-screen option)
  - `Orders` (Order Book, Executed Trades, Order Audit Trail)
  - `Holdings` (Long-term equity holdings & P&L)
  - `Positions` (Day intraday & positional F&O positions with live MTM)
  - `Option Chain` (Full interactive two-sided strike ladder)
  - `Baskets` (Multi-leg strategy builder & execution monitor)
  - `Funds` (Margin utilization, cash breakdown, collateral)
- **Global Status Indicators:**
  - WebSocket Latency badge (`< 20ms` Green, `20-100ms` Amber, `> 100ms` Red).
  - Quick Kill-Switch Button (`EMERGENCY CANCEL ALL` in top right header).

---

### 3.2. Market Watch Layout & Workflow
- **Multi-Tab Watchlist Bar:**
  - Supports 5 independent user watchlists (Tab 1 to Tab 5) mapped to Phase 5 `WatchlistService`.
  - Scrip count badge per tab (e.g., `18/50`).
  - Double-click tab name to inline-edit watchlist label.
- **Scrip Search & Add (Kite-Style Command Bar):**
  - Shortcut: `/` or `Ctrl+K`.
  - Autocomplete search with exchange segment filter pills: `ALL`, `NSE`, `BSE`, `NFO`, `BFO`.
  - Search results display: Trading Symbol, Company/Index Name, Segment tag, and `+` action button.
- **Scrip Row Architecture:**
  - Left: Trading Symbol (bold), Exchange Segment pill (`NSE`, `NFO`).
  - Sub-row: Expiry date, Strike price, Option type (`CE`/`PE`) for F&O contracts.
  - Right: Last Traded Price (large monospace), Absolute Change, Percentage Change.
  - **Quick Action Hover Bar (Reveals on row hover or keyboard focus):**
    - `[B]` **Buy Button (Blue):** Immediately loads contract into docked Order Entry ticket in BUY mode.
    - `[S]` **Sell Button (Orange/Red):** Immediately loads contract into docked Order Entry ticket in SELL mode.
    - `[Depth]` **5-Level Market Depth Popover:** Shows 5 best Bids (Orders, Qty, Price) vs 5 best Asks (Price, Qty, Orders), Total Buy Qty, Total Sell Qty, Open, High, Low, Close, Volume, and Upper/Lower Circuit limits.
    - `[Chain]` **Option Chain Shortcut:** Switches center workspace to Option Chain filtered to this underlying.
    - `[Delete]` **Remove Scrip:** Prompts deletion, auto-unsubscribing from SFeed stream.
- **Drag-and-Drop Reordering:**
  - Smooth HTML5 reordering with persistent position saving via `POST /api/market-watch/watchlists/{id}/reorder`.

---

### 3.3. Portfolio Layout (Holdings & Positions)

```
+----------------------------------------------------------------------------------------------------------------------------------+
| PORTFOLIO OVERVIEW                                                                                                               |
| Invested: ₹4,25,000.00 | Current: ₹4,58,420.50 | Overall P&L: +₹33,420.50 (+7.86%) | Day P&L: +₹4,820.50 (+1.06%)                |
+----------------------------------------------------------------------------------------------------------------------------------+
| Sub-tabs: [ POSITIONS (4) ]  [ HOLDINGS (12) ]                                       [Filter: ALL / F&O / CNC] [Search Scrip...]  |
+----------------------------------------------------------------------------------------------------------------------------------+
| Product | Instrument         | Qty  | Buy Avg | Sell Avg | LTP      | MTM P&L     | Chg %  | Actions                           |
|---------+--------------------+------+---------+----------+----------+-------------+--------+-----------------------------------|
| NRML    | NIFTY 28NOV 24500 CE | +50  |  120.00 |     0.00 |   142.50 | +₹1,125.00  | +18.7% | [Add] [Exit]                      |
| NRML    | NIFTY 28NOV 24700 CE | -50  |    0.00 |    45.00 |    38.00 |   +₹350.00  | -15.5% | [Add] [Exit]                      |
| MIS     | BANKNIFTY 52000 PE |   0  |  180.00 |   210.00 |   195.00 | +₹1,500.00  | CLOSED | [Details]                         |
| MIS     | RELIANCE           | +100 | 2930.00 |     0.00 |  2945.00 | +₹1,500.00  | +0.51% | [Add] [Exit]                      |
+----------------------------------------------------------------------------------------------------------------------------------+
| Action Bar: [ SQUARE OFF ALL POSITIONS (Emergency) ]                                                                               |
+----------------------------------------------------------------------------------------------------------------------------------+
```

#### Detailed Portfolio Elements:
- **Positions Tab (Live F&O and Intraday):**
  - Columns: Product (`MIS`, `NRML`), Instrument Symbol, Net Quantity (+ for Long, - for Short, 0 for Closed), Buy Average, Sell Average, LTP, Realized P&L, Live MTM P&L, Day Change %.
  - Live tick flashing on LTP and MTM P&L columns.
  - Zero Data Handling: Displays `NONE` if quotes are unconfirmed (The Golden Rule).
  - Quick Actions per Row:
    - `[Exit]`: Opens pre-filled Order Entry ticket with reverse side (Sell for Long, Buy for Short) and exact open quantity.
    - `[Add]`: Opens Order Entry ticket to add to position.
- **Holdings Tab (CNC Long-term Equities):**
  - Columns: Instrument, Available Qty, T1 (Unsettled) Qty, Average Price, LTP, Current Value, Overall P&L, % Return, Day P&L.
- **Defensive Square-Off Modal:**
  - Clicking `[SQUARE OFF ALL POSITIONS]` triggers a two-step confirmation dialog showing all open positions, total expected market orders, and warns about market impact.

---

### 3.4. Order Entry Window (Order Ticket)

```
+-------------------------------------------------------------------+
| [ BUY ]   NIFTY 28NOV 24500 CE                          [ x Close ]|
| NSE | NFO | Lot Size: 25 | Tick: 0.05                             |
+-------------------------------------------------------------------+
| Side Toggle:    (●) BUY (Blue)       ( ) SELL (Orange/Red)        |
+-------------------------------------------------------------------+
| Product:        (●) MIS (Intraday)   ( ) NRML (F&O)   ( ) CNC     |
+-------------------------------------------------------------------+
| Order Type:     (●) LIMIT    ( ) MARKET    ( ) SL     ( ) SL-M    |
+-------------------------------------------------------------------+
| Quantity:       [   25 ] lots [ 1 ] (Multiplier: x25)             |
| Price:          [ 142.50 ] (LTP: 142.50 | Best Bid: 142.45)        |
| Trigger Price:  [ ------ ] (Disabled unless SL / SL-M)            |
| Disclosed Qty:  [    0 ] (Optional)                               |
+-------------------------------------------------------------------+
| Market Protection: [====|=========] 2% (Auto-clamps limit price)  |
+-------------------------------------------------------------------+
| Margin Summary:                                                   |
|   Required Margin:  ₹3,562.50                                     |
|   Available Cash:   ₹2,45,000.00                                  |
|   Status:           SUFFICIENT MARGIN                             |
|   Execution Mode:   [ PAPER MODE ] (Simulation)                   |
+-------------------------------------------------------------------+
| [ CANCEL (Esc) ]                         [ SUBMIT BUY ORDER (Enter) ]|
+-------------------------------------------------------------------+
```

#### Ergonomic & Behavioral Features:
- **Kite-Style Color Theming:** Blue header and accent for BUY (`#1b73e8`), Orange/Red for SELL (`#ff5722`).
- **Docked vs Floating Mode:** Operator can dock the ticket at the bottom drawer or undock it as a floating modal.
- **Lot Multiplier Stepper:** Stepper buttons ($\pm 1$ lot) automatically increment quantity by instrument lot size ($25, 15, 50, \dots$).
- **Tick Size Auto-Correction:** Modulo 0.05 rounding on price inputs prevents exchange tick errors.
- **Live Margin Preview:** Debounced ($200\text{ ms}$) query to `/api/orders/validate` calculates margin requirement against available balance.
- **ExecutionMode Safety Banner:** Explicitly displays whether submission will execute in `PAPER`, route to exchange in `LIVE`, or be refused in `DISABLED`.

---

### 3.5. Basket Builder UI

```
+----------------------------------------------------------------------------------------------------------------------------------+
| BASKET BUILDER & STRATEGY WORKBENCH                                                        [ + Add Custom Leg ] [ Load Template ]|
| Active Basket: "NIFTY_BULL_CALL_SPREAD_01" | Status: DRAFT | Exposure: NEUTRAL | Mode: SEQUENTIAL | Failure Policy: ABORT_REMAINING |
+----------------------------------------------------------------------------------------------------------------------------------+
| # | Leg Instrument         | Side | Type | Strike | Expiry | Lots | Qty | Order Type | Price  | Status | Dependency | Action  |
|---+------------------------+------+------+--------+--------+------+-----+------------+--------+--------+------------+---------|
| 1 | NIFTY 28NOV 24500 CE   | BUY  | CE   |  24500 | 28NOV  |    1 |  25 | LIMIT      | 142.50 | READY  | NONE       | [Edit][x|
| 2 | NIFTY 28NOV 24700 CE   | SELL | CE   |  24700 | 28NOV  |    1 |  25 | LIMIT      |  48.00 | READY  | Leg 1 Fill | [Edit][x|
+----------------------------------------------------------------------------------------------------------------------------------+
| STRATEGY TEMPLATES: [ Bull Call ] [ Bear Put ] [ Straddle ] [ Strangle ] [ Iron Condor ] [ Iron Butterfly ]                       |
| Strategy Validation: VALID BULL CALL SPREAD | Expiry: Symmetric | Strikes: 24500 < 24700 | Lot Multiples: Consistent             |
| Net Premium: Debit ₹94.50 (₹2,362.50 per lot) | Margin Required: ₹38,500.00 | Available Margin: ₹2,45,000.00                     |
+----------------------------------------------------------------------------------------------------------------------------------+
| [ Reset Basket ] [ Save Draft ] [ Validate Dry Run ]                           [ EXECUTE BASKET (Sequential / Paper Mode) ]      |
+----------------------------------------------------------------------------------------------------------------------------------+
```

#### Key Capabilities:
- **Template Autofill:** 1-click loading of predefined strategies with auto-calculated strikes relative to ATM.
- **Dependency DAG Visualization:** Clearly highlights dependency relationships (e.g., Short leg waits for Hedge wing fill).
- **Dry-Run Validation:** Connects to Phase 9 `POST /api/baskets/validate` to verify strike relationships, tick rules, and account margin before execution.
- **Idempotency Protection:** Double-click disabled submit button with local request token lock.

---

### 3.6. Option Chain UI

```
+----------------------------------------------------------------------------------------------------------------------------------+
| OPTION CHAIN: NIFTY 50 | Spot: 24,520.50 (+102.30 / +0.42%) [★ Favourite] | Expiry: [ 28-NOV-2026 (DTE: 5) ▼ ]                  |
| Presets: [ ATM ±5 ]  (●) [ ATM ±10 ]  [ ATM ±15 ]  [ ATM ±20 ]   | PCR (OI): 0.94 | PCR (Vol): 1.05 | Max Pain: 24,500         |
+----------------------------------------------------------------------------------------------------------------------------------+
|                     CALLS (Bullish)                     | STRIKE |                      PUTS (Bearish)                      |
| OI       | Chg OI  | Volume | Bid   | Ask   | LTP       | PRICE  | LTP      | Bid   | Ask   | Volume | Chg OI  | OI       | Quick |
+----------+---------+--------+-------+-------+-----------+--------+----------+-------+-------+--------+---------+----------+-------+
|  45,200  | +8,400  | 1.2M   | 285.0 | 286.0 | 285.50 ITM| 24,300 |    42.10 |  42.0 |  42.2 | 450K   |  -2,100 |  18,500  | [+][B]|
|  62,100  | +12,300 | 1.8M   | 205.0 | 205.5 | 205.20 ITM| 24,400 |    65.40 |  65.2 |  65.5 | 680K   |  -1,500 |  24,200  | [+][B]|
| ============================================= ATM STRIKE: 24,500 ======================================================== |
| 115,400  | +25,100 | 3.5M   | 142.0 | 142.5 | 142.50 ATM| 24,500 |    98.20 |  98.0 |  98.3 | 2.1M   | +14,200 |  95,100  | [+][B]|
| ========================================================================================================================= |
|  82,300  | +18,200 | 2.1M   |  88.5 |  89.0 |  88.75    | 24,600 |   145.00 | 144.5 | 145.2 | 890K   |  +8,100 |  52,400  | [+][S]|
|  95,800  | +21,400 | 2.4M   |  48.0 |  48.2 |  48.10    | 24,700 |   210.50 | 210.0 | 211.0 | 520K   |  +4,200 |  38,900  | [+][S]|
+----------------------------------------------------------------------------------------------------------------------------------+
| Upstream OI Timestamp: 2026-11-06T15:30:00Z | Quote Tick: 15:32:04.120 | Ret: 15:32:04.125 | Streaming Active (42 scrips)         |
+----------------------------------------------------------------------------------------------------------------------------------+
```

#### Detailed Capabilities:
- **Symmetrical Preset Windowing:** Instant toggling between `ATM ±5` (11 rows), `ATM ±10` (21 rows), `ATM ±15` (31 rows), and `ATM ±20` (41 rows).
- **Moneyness Shading:** Subtle amber/gold background for ITM strikes (`K < S` for Calls, `K > S` for Puts). ATM strike accentuated with a prominent boundary.
- **Dynamic Quick Action Hover Bar:**
  - `[+]`: 1-click addition of the specific contract to Phase 5 default watchlist.
  - `[B]` / `[S]`: Loads the option contract directly into the Order Ticket.
  - Multi-select checkbox: Allows selecting multiple strikes to export into Basket Builder with 1 click.
- **Live WebSocket Streaming:** Visible strike quotes update in real time via Phase 4 SFeed streaming pipeline.

---

### 3.7. Funds Widget
- **Visual Margin Utilization Bar:**
  - Progress bar dynamically shaded:
    - `0% - 70%`: Green (`#00d09c`) — Healthy buffer.
    - `70% - 85%`: Amber (`#f2994a`) — Caution threshold.
    - `85% - 100%`: Crimson (`#eb5757`) — Risk limit warning; order placement blocked.
- **Metrics Breakdown:**
  - **Available Trading Cash:** Realized balance available for new positions.
  - **Collateral / Non-Cash Margin:** Margin derived from pledged holdings.
  - **Used Margin:** Total margin locked in open positions and active limit orders.
  - **Total Account Value:** Net liquidation value.
- **Instant Refresh Button:** Triggers Phase 6 `/api/portfolio/margins` query.

---

### 3.8. System Health & Telemetry Widget
- **SFeed WebSocket Monitor:**
  - Connection indicator with pulsing LED (`CONNECTED` green, `RECONNECTING` amber, `DISCONNECTED` red).
  - Ping round-trip latency in milliseconds.
  - Cumulative message throughput (ticks/sec).
- **Broker Authentication Telemetry:**
  - Session validity status.
  - Countdown timer to session token expiry.
  - 1-click token re-authentication button.
- **Circuit Breaker Status:**
  - Shows breaker state: `NORMAL`, `HALF_OPEN`, `OPEN`.
- **ExecutionMode Master Display:**
  - Visual badge repeating global execution state with quick-access safety toggle.

---

## 4. Dark Theme Design System & Visual Tokens

The interface implements a custom dark theme tailored for high-frequency market readability, minimizing eye strain during long trading sessions.

### 4.1. Color Tokens

```css
:root {
  /* Surfaces & Backgrounds */
  --bg-app: #0d1117;           /* Deep dark master background */
  --bg-surface: #161b22;       /* Card and pane surface */
  --bg-surface-hover: #21262d; /* Hovered item surface */
  --bg-surface-active: #30363d;/* Selected item surface */
  --border-subtle: #30363d;    /* Subtle division border */
  --border-prominent: #484f58; /* Active / focused border */

  /* Text & Typography */
  --text-primary: #f0f6fc;     /* Primary high-contrast text */
  --text-secondary: #8b949e;   /* Secondary labels and headers */
  --text-muted: #6e7681;       /* Inactive / disabled text */

  /* Market Semantics (Indian Market Conventions) */
  --market-green: #00d09c;     /* Uptick / Bullish / Profit / Buy */
  --market-green-bg: rgba(0, 208, 156, 0.12); /* Subtle green fill */
  --market-red: #eb5757;       /* Downtick / Bearish / Loss / Sell */
  --market-red-bg: rgba(235, 87, 87, 0.12);   /* Subtle red fill */

  /* Operational Semantic Accents */
  --accent-blue: #1b73e8;      /* Buy order accent / Action CTA */
  --accent-orange: #ff5722;    /* Sell order accent */
  --accent-amber: #f2994a;     /* Paper mode warning / Alert */
  --itm-gold-bg: rgba(255, 193, 7, 0.08); /* Option ITM Moneyness tint */

  /* Numeric Font */
  --font-numeric: 'JetBrains Mono', 'Roboto Mono', monospace;
  --font-sans: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
}
```

### 4.2. Typography & Numerical Rules
- **Monospace Alignment:** All monetary values, quantities, strikes, percentages, and timestamps must use `--font-numeric` with `font-variant-numeric: tabular-nums` to prevent layout shaking as digits tick.
- **Color Discipline:** Green and Red are reserved strictly for market direction, P&L, and order sides. Non-financial UI controls use neutral grays or blue accents.

---

## 5. Responsive Layout Breakpoints

```
+---------------------------------------------------------------------------------------------------+
| BREAKPOINT      | VIEWPORT RANGE  | LAYOUT BEHAVIOR                                               |
|-----------------+-----------------+---------------------------------------------------------------|
| Ultra-Wide / 4K | >= 1920px       | 3-Pane: Market Watch (360px) + Main Workspace + Docked Ticket |
| Desktop         | 1440px - 1919px | 2-Pane: Market Watch (320px) + Main Workspace + Bottom Drawer |
| Laptop / Small  | 1024px - 1439px | Collapsible Market Watch sidebar + Tabbed Main Workspace      |
| Tablet          | 768px - 1023px  | Single-pane stacked: Market Watch off-canvas drawer           |
| Mobile          | < 768px         | Mobile view: Bottom navigation bar + Full-screen cards        |
+---------------------------------------------------------------------------------------------------+
```

- **Touch Targets:** On touch devices ($< 1024$px), all clickable buttons and action targets maintain a minimum dimension of $44 \times 44$px.
- **Mobile Bottom Navigation:** Provides quick switching between `Watchlist`, `Orders`, `Portfolio`, `Option Chain`, and `Account`.

---

## 6. Zerodha/Kite-Inspired UX & Keyboard Navigation

Speed is a safety feature. The terminal implements a keyboard map matching standard institutional workflows:

| Key Binding | Target Action | Scope / Context |
|:---|:---|:---|
| `B` | Open Order Ticket in **BUY** mode for focused scrip | Market Watch / Option Chain / Portfolio |
| `S` | Open Order Ticket in **SELL** mode for focused scrip | Market Watch / Option Chain / Portfolio |
| `↑` / `↓` | Navigate active scrip row up/down | Market Watch / Option Chain |
| `/` or `Ctrl + K` | Focus Global Scrip Search input | Global Terminal |
| `Esc` | Close active modal, popover, or Order Ticket | Global Terminal |
| `Enter` | Submit Order / Execute active form button | Order Ticket / Modal |
| `Tab` | Cycle through inputs (Qty $\to$ Price $\to$ Trigger) | Order Ticket |
| `O` | Switch active workspace to **Option Chain** for focused scrip | Market Watch / Portfolio |
| `Shift + Esc` | Open **Emergency Cancel All Orders** confirmation | Global Terminal |

---

## 7. State Management & WebSocket Reactive Data Binding

```
+----------------------------------------------------------------------------------------------------+
|                                    FRONT-END STATE ARCHITECTURE                                    |
|                                                                                                    |
|   [ Kotak Neo SFeed WebSocket ]          [ REST Backend APIs ]                                      |
|                 |                                  |                                               |
|                 v                                  v                                               |
|      [ SFeed Streaming Client ]            [ API Service Client ]                                   |
|                 |                                  |                                               |
|                 +----------------+                 |                                               |
|                                  v                 v                                               |
|                     [ Master Reactive State Store (`Store`) ]                                      |
|                       ├── MarketWatch State (Watchlists, Scrip Lists, Touchlines)                  |
|                       ├── OptionChain State (Strikes, Spot, Presets, PCR, OI)                      |
|                       ├── Portfolio State (Holdings, Positions, Live MTM)                          |
|                       ├── OrderBook State (Open, Executed, Cancelled, FSM)                         |
|                       ├── Basket State (Draft Strategies, Legs, Exposure)                          |
|                       └── System State (Health, Latency, ExecutionMode)                            |
|                                  |                                                                 |
|         +------------------------+------------------------+                                        |
|         v                                                 v                                        |
|  [ Targeted DOM Updates ]                          [ Sound & Toast FX ]                            |
|  - Selective cell re-rendering                     - Order filled chime                            |
|  - Micro green/red tick pulses                     - Rejection alert toast                         |
|  - Zero full-page layout thrashing                                                                 |
+----------------------------------------------------------------------------------------------------+
```

### Key Principles:
1. **Targeted Micro-Updates:** WebSocket ticks update individual DOM nodes (`element.textContent`) directly using data attributes (`data-token="45210"`); the entire table or list is never re-rendered.
2. **The Golden Rule Compliance:** If quote data drops or is absent, the UI shows `—` or `NONE`. It never invents placeholder prices.
3. **Optimistic UI Banned:** Orders placed via the ticket stay in a `SUBMITTING...` state until an event confirmation (`ORDER_PLACED` / `ORDER_FILLED`) is received over the EventBus/Socket.IO.

---

## 8. Test & Verification Strategy for Phase 11 UI

Phase 11 implementation will be validated through a multi-tier testing framework:

1. **State Store Unit Tests (`tests/ui/test_store.js` / Python mock verification):**
   - Verify tick ingestion, price scaling, and change calculations.
   - Verify lot stepper increments and tick size modulo corrections.
2. **Component Integration Tests:**
   - Verify Order Entry ticket validation (e.g. Price $> 0$, Qty $> 0$, Stop Loss logic).
   - Verify Basket Builder template instantiation and leg dependency wiring.
   - Verify Option Chain preset switching (`ATM ±5` through `ATM ±20`) produces exact row counts.
3. **End-to-End Headless Tests:**
   - Execute order placement workflow in `PAPER` mode: Click Buy $\to$ Fill Qty $\to$ Submit $\to$ Verify Order Book update.
   - Verify `DISABLED` mode locks all action buttons with error tooltips.
   - Verify `Shift+Esc` emergency kill-switch trigger.
4. **Responsive Layout Audits:**
   - Automated viewport regression checks at 1920px, 1440px, 1024px, 768px, and 375px.

---

## 9. Deliverables Summary

Upon approval of this specification, the implementation of Phase 11 will deliver:
1. `app/templates/terminal.html`: Master terminal layout container.
2. `app/templates/components/`: Modular Jinja2 components (`market_watch.html`, `order_ticket.html`, `portfolio.html`, `option_chain.html`, `basket_builder.html`, `funds_widget.html`, `health_widget.html`).
3. `app/static/css/terminal.css`: Complete dark-mode design system, CSS variables, high-contrast typography, and responsive grid.
4. `app/static/js/`: Modular ES6 client code (`store.js`, `stream_client.js`, `order_ticket.js`, `option_chain_ui.js`, `basket_builder_ui.js`, `keyboard_nav.js`).
5. `tests/integration/test_ui_routes.py`: Flask route integration tests serving UI endpoints and assets.
6. `PHASE11_ARCHITECTURE_REVIEW.md`: Comprehensive post-implementation architectural audit.
