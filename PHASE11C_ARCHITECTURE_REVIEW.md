# Phase 11C Architecture Review: Portfolio & Order Book UI

**Document Version:** 1.0.0  
**Phase:** Phase 11C (Portfolio & Order Book UI)  
**Target Milestone:** Sub-Milestone of M6 (Trading Terminal UI & Workbench Integration)  
**Status:** Completed & Validated  
**Date:** 2026-11-07  

---

## 1. Executive Summary

Phase 11C delivers the post-trade, risk management, and order auditing cockpit of the **Kotak Neo Personal Trading Terminal**: the **Demat Holdings View**, **Derivatives & Intraday Positions View**, **Live MTM Dashboard**, **Order Book**, **Trade Book**, **Expanded Funds Ledger**, **Order Timeline FSM Modal**, and **Position Quick Actions**. Engineered with the speed, clarity, and ergonomics of **Zerodha Kite**, this phase anchors execution visibility and capital management into the unified terminal interface.

All implementations strictly adhere to the project's constitutional mandates:

1. **Human-Initiated Execution Only:** Every single order creation, modification, cancellation, position exit, and position reversal is initiated strictly by explicit operator click or keyboard shortcut. Zero autonomous bots, automated square-off routines, or unprompted background trade loops exist.
2. **Defensive Order & State Hierarchy:** All order interactions route strictly through established backend services:
   $$\text{Positions / Orders UI} \longrightarrow \text{OrderTicket / API} \longrightarrow \text{Flask /api/orders/place} \longrightarrow \text{OrderExecutionService} \longrightarrow \text{ExecutionMode Gating}$$
   Direct broker wire bypass is architecturally prohibited.
3. **ExecutionMode Safety Enforcement:** All actions strictly inherit the terminal's global `ExecutionMode` (`DISABLED`, `PAPER`, `LIVE`). In `DISABLED` mode, exit and reversal workflows refuse wire submission. In `LIVE` mode, emergency mass square-off requires explicit challenge string verification (`CONFIRM_EXIT_ALL`).
4. **The Golden Rule Compliance:** Absence of live tick or touchline data renders strictly as `—` or `NONE`. No synthetic prices or optimistic UI assumptions are permitted.
5. **Dual Timestamp Integrity:** All portfolio and order snapshot views display dual timestamps (`source_timestamp` from the exchange/broker and `retrieved_timestamp` from the terminal cache/gateway).
6. **Strict Scope Exclusions:**
   - ❌ **No Greeks Engine:** No Black-Scholes Delta, Gamma, Theta, Vega, or Rho derivations.
   - ❌ **No Volatility Analytics:** No IV surfaces, IV rank, or skew calculations.
   - ❌ **No Automated Scanner Engine:** No background scanners executing trades on price/volume thresholds.
   - ❌ **No Copy Trading or AI Signals:** All decisions remain strictly manual.

---

## 2. Component Hierarchy & System Architecture

```
+-------------------------------------------------------------------------------------------------------------------+
|                                            PHASE 11C SYSTEM ARCHITECTURE                                          |
|                                                                                                                   |
|  [ Operator Browser / Desktop Cockpit: /terminal ]                                                                |
|            |                                                                                                      |
|            +---> [ Holdings View: components/holdings_view.html ]                                                 |
|            |       ├── CNC Demat Holdings Table (Symbol, Segment, Settled Qty, T1 Unsettled, Avg, LTP, Val)       |
|            |       ├── Real-Time Touchline Updating & P&L Calculations                                            |
|            |       ├── Quick Actions: [Add] (Buy 1 CNC) & [Exit] (Sell Avail Settled Qty CNC)                     |
|            |       └── Header Refresh: "Last Refreshed: HH:mm:ss" + Force Refresh Button                          |
|            |                                                                                                      |
|            +---> [ Positions View: components/positions_view.html ]                                               |
|            |       ├── Derivatives & Intraday Table (MIS / NRML, Net Qty, Buy/Sell Avg, LTP, Realized, MTM)       |
|            |       ├── Sub-tabs: ALL (n), OPEN (n), CLOSED (n) + Product Filter: ALL, MIS, NRML                   |
|            |       ├── Live MTM Metric Strip: Realized P&L, Unrealized MTM P&L, Net Day P&L, Exposure Margin      |
|            |       ├── Quick Actions: [Add] (scale into position), [Exit] (square off net qty)                    |
|            |       ├── [Reverse] Action: 180° flip (2x net qty opposite side) with confirmation modal              |
|            |       └── Emergency Batch Action: [⚠️ SQUARE OFF ALL POSITIONS] (requires CONFIRM_EXIT_ALL in LIVE)   |
|            |                                                                                                      |
|            +---> [ Order Book View: components/order_book_view.html ]                                             |
|            |       ├── Real-Time FSM Order Grid (Time, Client Order ID, Symbol, Side, Qty/Filled, Price, Status) |
|            |       ├── Status Filter Tabs: ALL, OPEN, EXECUTED, CANCELLED, REJECTED, RECONCILING                  |
|            |       ├── Live In-Flight Actions: [Mod] (Modify price/qty), [Can] (Cancel single order)              |
|            |       ├── State-Machine Visual Link: [Timeline] button launching interactive FSM modal               |
|            |       └── Emergency Kill-Switch: [⚠️ Cancel All Open Orders] -> POST /api/orders/cancel-all           |
|            |                                                                                                      |
|            +---> [ Trade Book View: components/trade_book_view.html ]                                             |
|            |       ├── Completed Trade Fills (Trade Time IST with ms precision, Trade ID, Order ID, Price, Qty)   |
|            |       └── Turnover Aggregator: Total Trades Counter & Cumulative Value (₹)                           |
|            |                                                                                                      |
|            +---> [ Expanded Funds Ledger: components/funds_expanded_view.html ]                                   |
|            |       ├── Tier 1: Trading Capital Breakdown (Available Cash, Collateral, MTM Credit, Total Margin)   |
|            |       ├── Tier 2: Margin Utilization Breakdown (SPAN Margin, Exposure Margin, Premium Blocked)       |
|            |       ├── Tier 3: Utilization Progress Bar (0-100%, Safe <70%, Caution 70-85%, Critical >=85%)       |
|            |       └── Tier 4: Risk & Regulatory Snapshot (Peak Margin, Ad-hoc, Timestamps, Upstream Status)      |
|            |                                                                                                      |
|            +---> [ Order Timeline Modal: components/order_timeline_modal.html ]                                   |
|            |       ├── Stepper Pipeline: [1 DRAFT] -> [2 VALIDATED] -> [3 SUBMITTED] -> [4 PENDING] -> [5 TRADED] |
|            |       ├── Dynamic Node Styling: .completed (green), .active (blue), .failed (red)                   |
|            |       └── Chronological Audit Event Log with Microsecond Precision and FSM Transition Explanations    |
|            |                                                                                                      |
|            +---> [ Front-End Controllers: static/js/ ]                                                            |
|                    ├── portfolio.js (Holdings, Positions, MTM Dashboard, Funds Ledger, Quick Actions)             |
|                    └── order_book.js (Orders, Trades, FSM Timeline, Modify, Cancel, Mass Cancel)                 |
+-------------------------------------------------------------------------------------------------------------------+
```

---

## 3. Dedicated Architectural Scope Audits

### 3.1. Audit Item 1: Holdings Screen (CNC Demat Portfolio)
- **Data Source Integration:** Integrates with Phase 6 `GET /api/portfolio/holdings` returning custody entities.
- **Settlement Distinction:** Explicitly distinguishes settled Demat custody (`quantity`) from unsettled T1 transactions (`t1_quantity`).
- **Valuation Invariants:**
  $$\text{Current Value} = (\text{Quantity} + \text{T1 Quantity}) \times \text{LTP}$$
  $$\text{Total P&L} = \text{Current Value} - \left( (\text{Quantity} + \text{T1 Quantity}) \times \text{Buy Average} \right)$$
- **Quick Action Triggers:**
  - `[Add]`: Pre-fills Order Ticket with `BUY`, `CNC`, 1 share.
  - `[Exit]`: Pre-fills Order Ticket with `SELL`, `CNC`, quantity clamped to settled available ($\le \text{Quantity}$). T1 unsettled shares are protected from invalid delivery sell attempts.

### 3.2. Audit Item 2: Positions Screen (Derivatives & Intraday)
- **Data Source Integration:** Integrates with Phase 6 `GET /api/portfolio/positions?type=net&status=all`.
- **Filtering Capabilities:** Sub-tabs for `ALL`, `OPEN`, and `CLOSED` positions, accompanied by a product filter dropdown (`ALL`, `MIS`, `NRML`).
- **Polymorphic Calculations:**
  - Long Position ($\text{Net Qty} > 0$): $\text{MTM} = \text{Net Qty} \times (\text{LTP} - \text{Buy Avg})$.
  - Short Position ($\text{Net Qty} < 0$): $\text{MTM} = |\text{Net Qty}| \times (\text{Sell Avg} - \text{LTP})$.
  - Closed Position ($\text{Net Qty} = 0$): $\text{MTM} = 0.00$; displays $\text{Realized P&L} = (\text{Sell Avg} - \text{Buy Avg}) \times \text{Traded Qty}$.
- **The Golden Rule Handling:** If live quote is missing from the touchline cache, MTM renders as `—` rather than calculating erroneous values.

### 3.3. Audit Item 3: Portfolio Dashboard & Navigation Synchronization
- **Cross-Component Sync:** Header ticker and navigation bar (`#badge-open-positions`, `#badge-open-orders`, `#nav-day-pnl`) dynamically reflect portfolio state changes.
- **Day P&L Aggregator:**
  $$\text{Day Total P&L} = \sum \text{Realized P&L} + \sum \text{Unrealized MTM}$$
- **Visual Color Semantics:** Positive numbers render in `--accent-green` (`#00d09c`), negative numbers in `--accent-red` (`#eb5757`), zero in neutral gray.

### 3.4. Audit Item 4: Order Book (Active & Filtered FSM Orders)
- **FSM State Visualization:** Each order displays an authoritative badge representing the Phase 7/8 Finite State Machine:
  - `OPEN` / `PENDING` / `SUBMITTED` / `VALIDATED`: Blue badge (`#1b73e8`).
  - `TRADED` / `FILLED`: Green badge (`#00d09c`).
  - `CANCELLED`: Gray badge (`#8b949e`).
  - `REJECTED` / `FAILED`: Red badge (`#eb5757`).
  - `RECONCILING`: Pulsing amber badge (`#f2994a`) with CSS pulse animation.
- **In-Flight Controls:** `[Mod]` triggers price/quantity adjustment via `PUT /api/orders/{id}/modify`; `[Can]` issues single-order cancellation via `DELETE /api/orders/{id}/cancel`.
- **Search Filtering:** Real-time text search filters rows by trading symbol or client order ID.
- **Mass Kill-Switch:** `[⚠️ Cancel All Open Orders]` triggers `POST /api/orders/cancel-all`.

### 3.5. Audit Item 5: Trade Book (Audit-Grade Executed Fills)
- **Data Source Integration:** Consumes Phase 8 `GET /api/orders/trades`.
- **Sub-Second Precision:** Execution timestamps display millisecond resolution (`YYYY-MM-DD HH:mm:ss.SSS`).
- **Turnover Metrics:** Aggregates cumulative executed turnover:
  $$\text{Turnover} = \sum_{i} (\text{Quantity}_i \times \text{Fill Price}_i)$$

### 3.6. Audit Item 6: Live MTM Widgets & Real-Time Strips
- **Multi-Metric Cards:** Summary strip atop the Positions view displays:
  1. Realized P&L
  2. Unrealized MTM P&L
  3. Net Day P&L
  4. Exposure Margin Required
- **Immediate Refresh:** Triggered automatically upon order placement, modification, cancellation, and manual refresh clicks.

### 3.7. Audit Item 7: PnL Widgets & Risk Indicators
- **Dynamic Risk Banners:**
  - Utilization buffer status in funds ledger shifts colors: Safe ($< 70\%$, green), Caution ($70-85\%$, amber), Critical ($\ge 85\%$, red).
  - Net Day P&L updates terminal header ticker in real time.

### 3.8. Audit Item 8: Expanded Funds View (Collateral & Margin Ledger)
- **4-Tier Architecture:**
  1. *Trading Capital Breakdown:* Realized cash, pledged collateral, MTM credit, and net available margin.
  2. *Margin Utilization Breakdown:* SPAN margin, exposure margin, and option premium blocked.
  3. *Utilization Progress Track:* Visual progress bar with threshold status.
  4. *Risk & Regulatory Snapshot:* Peak margin today, ad-hoc margin, balance timestamp, and upstream reconciliation status (`RECONCILED`).
- **Integration:** Powered by `GET /api/portfolio/margins`.

### 3.9. Audit Item 9: Order Timeline View (Visual FSM Progression)
- **Stepped Transition Graph:**
  $$\text{DRAFT} \longrightarrow \text{VALIDATED} \longrightarrow \text{SUBMITTED} \longrightarrow \text{PENDING} \longrightarrow \text{TRADED / REJECTED / CANCELLED}$$
- **Visual Nodes:** Each node reflects completion status (`.completed`, `.active`, `.failed`) with its recorded microsecond timestamp.
- **Audit Event Log:** Chronological list detailing transition reasons, actor identities, and gateway timestamps from `GET /api/orders/{client_order_id}`.

### 3.10. Audit Item 10: Position Quick Actions (Add, Exit, Reverse) & Safety Threshold
- **`[Add]` Workflow:** Launches Order Ticket with same side and default lot size to scale or average into position.
- **`[Exit]` Workflow & Position Exit Safety Threshold:**
  - Evaluates position gross exposure: $\text{Exposure} = |\text{Net Qty}| \times \max(\text{LTP}, \text{Buy Avg}, \text{Sell Avg})$.
  - **Threshold Policy ($> ₹1,00,000$):** If position exposure exceeds ₹1,00,000.00, single-click exit is guarded by `#high-exposure-exit-modal`. The operator must explicitly verify instrument symbol, gross exposure amount, and liquidation quantity before the Order Ticket is presented.
  - For exposures $\le ₹1,00,000.00$, directly launches Order Ticket pre-filled with opposite side and exact open net quantity ($|\text{Net Qty}|$).
- **`[Reverse]` Workflow (180° Flip):**
  - Calculates reversal size: $\text{Reverse Qty} = 2 \times |\text{Net Qty}|$.
  - Direction: Opposite to current net exposure (Long $+50 \implies \text{SELL } 100 \implies \text{New Net } -50$).
  - Displays modal confirmation detailing current position vs new position target.
  - Launches Order Ticket pre-filled with reversal parameters and toast notification.
- **Emergency Square Off All Workflow:** Opens modal listing all open legs. In `LIVE` mode, enforces typing challenge `CONFIRM_EXIT_ALL` before dispatching MARKET exit orders. Sequential order routing preserves the terminal's single-order risk checks.

### 3.11. Audit Item 11: Portfolio Refresh Controls & Timestamps
- **Timestamp Display:** Header prominently displays `"Last Refreshed: HH:mm:ss"` parsed from backend `retrieved_timestamp`.
- **Force-Refresh Action:** Single-click `[🔄 Refresh]` button invokes `POST /api/portfolio/refresh`, force-syncing holdings, positions, and margins from broker cache and updating all views simultaneously.

---

## 4. Verification & Testing Metrics

### 4.1. Automated Test Coverage
A dedicated test suite `tests/integration/test_portfolio_order_book_ui_routes.py` was created to validate Phase 11C deliverables.

| Test Case | Scope Covered | Status |
| :--- | :--- | :--- |
| `test_terminal_loads_phase11c_components` | Verifies inclusion of Holdings, Positions, Order Book, Trade Book, Funds ledger, Timeline modal, and CSS/JS assets in `/terminal` HTML | **PASSED** |
| `test_phase11c_static_assets_served` | Verifies HTTP 200 for `portfolio.css`, `portfolio.js`, and `order_book.js` | **PASSED** |
| `test_portfolio_endpoints_integration` | Verifies `GET /api/portfolio/holdings`, `positions`, `margins`, `pnl`, and `POST /api/portfolio/refresh` with dual timestamps | **PASSED** |
| `test_orders_and_timeline_integration` | Verifies `GET /api/orders`, `trades`, paper order placement, timeline detail fetch, and mass cancellation | **PASSED** |

### 4.2. Full Regression Suite Results
The complete terminal regression suite was executed across all test files:

$$\mathbf{204\text{ passed, } 0\text{ failed, } 0\text{ regressions in } 19.26\text{ seconds}}$$

---

## 5. Architectural Sign-Off

Phase 11C meets all design specifications, safety mandates, and performance criteria outlined in `PHASE11C_DESIGN_SPEC.md`. Post-trade operations, position tracking, MTM calculations, and order management are now fully integrated into the desktop trading terminal.

| Sub-Phase | Component | Status | Target Phase |
| :--- | :--- | :--- | :--- |
| **Phase 11A** | Terminal Shell, Global Header, Navigation Tabs, Workspace Persistence, Compact Mode | **COMPLETED** | — |
| **Phase 11B** | Market Watch Grid, Scrip Search Palette (Ctrl+K), 5-Level Depth DOM, Professional Order Ticket | **COMPLETED** | — |
| **Phase 11C** | Demat Holdings, Positions, Live MTM Dashboard, Order Book, Trade Book, Funds Ledger, Timeline Modal | **COMPLETED** | — |
| **Phase 11D** | Multi-Leg Basket Builder UI & Option Chain Workbench UI | **PENDING** | Next Milestone |

