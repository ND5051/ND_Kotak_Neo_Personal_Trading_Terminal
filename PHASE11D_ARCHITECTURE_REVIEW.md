# Phase 11D Architecture Review: Basket Builder & Option Chain UI

**Document Version:** 1.0.0  
**Phase:** Phase 11D (Basket Builder & Option Chain UI)  
**Target Milestone:** Sub-Milestone of M6 (Trading Terminal UI & Workbench Integration)  
**Status:** Completed & Validated  
**Date:** 2026-11-09  

---

## 1. Executive Summary

Phase 11D completes the front-end user experience of the **Kotak Neo Personal Trading Terminal** by introducing the **Option Chain Workbench UI** and the **Multi-Leg Strategy & Basket Builder UI**. Inspired by the high-density analytical speed of professional derivative terminals and Zerodha Kite / Sensibull workflows, Phase 11D bridges analytical strike selection directly with deterministic, multi-leg execution safety.

Every capability built within Phase 11D adheres strictly to the project's constitutional engineering rules:

1. **Human-Initiated Execution Only:** Every basket order validation, leg staging, multiplier adjustment, and execution dispatch is initiated strictly by explicit operator click or keyboard shortcut (`Ctrl+Enter`). Zero autonomous trading bots, automated gamma scalpers, or unprompted background execution loops exist.
2. **Defensive Order & State Hierarchy:** All order actions route strictly through established backend domain pipelines:
   $$\text{Option Chain} \longrightarrow \text{Basket Builder} \longrightarrow \text{POST /api/baskets/validate} \longrightarrow \text{POST /api/baskets/<id>/execute} \longrightarrow \text{ExecutionMode Gating}$$
   Direct broker wire bypass is architecturally impossible.
3. **Strict ExecutionMode Safety Enforcement:** All actions strictly inherit the terminal's global `ExecutionMode` (`DISABLED`, `PAPER`, `LIVE`).
   - In `DISABLED` mode, basket execution is completely blocked with a visible warning banner and disabled execute buttons.
   - In `PAPER` mode, multi-leg execution is simulated safely against local state machines without broker wire risk.
   - In `LIVE` mode, the terminal enforces an explicit typing challenge (`CONFIRM_EXECUTE_BASKET`) before routing live orders to the exchange.
4. **The Golden Rule Compliance:** Absence of live tick or touchline data renders strictly as `—` or `NONE`. No synthetic prices or optimistic UI assumptions are permitted.
5. **Strict Scope Exclusions:**
   - ❌ **No Greeks Engine:** No Black-Scholes Delta, Gamma, Theta, Vega, or Rho derivations.
   - ❌ **No Volatility Analytics:** No IV surfaces, implied volatility skews, or historical volatility models.
   - ❌ **No Autonomous Bots / Background Scanners:** No background trading loops or unprompted square-offs.
   - ❌ **No Direct Wire Bypassing:** All operations adhere to sequential execution stages.

---

## 2. Component Hierarchy & System Architecture

```
+-------------------------------------------------------------------------------------------------------------------+
|                                            PHASE 11D SYSTEM ARCHITECTURE                                          |
|                                                                                                                   |
|  [ Operator Browser / Desktop Cockpit: /terminal ]                                                                |
|            |                                                                                                      |
|            +---> [ Option Chain Workbench: components/option_chain_view.html ]                                    |
|            |       ├── Master Control Bar: Underlying Selector, Expiry Dropdown, Symmetrical Strike Presets       |
|            |       ├── Spot Price Badge with Live Change & Percentage                                             |
|            |       ├── PCR & Max Pain Sentiment Strip: Total Call/Put OI, PCR OI, PCR Vol, Max Pain, S/R Levels    |
|            |       ├── Quick Strategy Shortcuts Bar: Bull Call, Bear Put, Straddle, Strangle, Condor, Butterfly   |
|            |       ├── Symmetrical Matrix Table: Calls on Left, Strike in Center, Puts on Right                   |
|            |       ├── Relative In-Cell OI Gradient Fill Bars                                                     |
|            |       ├── Visual Moneyness: Amber ITM background tinting, Amber border for ATM strike                |
|            |       └── Row Action Triggers: [B] (Buy Single), [S] (Sell Single), [➕ Leg] (Add to Basket), [📌]    |
|            |                                                                                                      |
|            +---> [ Docked Bottom Basket Drawer: components/basket_drawer.html ]                                   |
|            |       ├── Slide-Up Preview Drawer (Collapsed by default, auto-opens when leg is added)               |
|            |       ├── Compact Leg Chips with Side Color Coding (BUY Blue, SELL Red)                              |
|            |       ├── Dynamic Margin Pill & Legs Counter Badge                                                   |
|            |       └── Actions: [Clear], [Execute Basket], [Open Full Workbench (Alt+6)]                          |
|            |                                                                                                      |
|            +---> [ Strategy & Basket Builder Workbench: components/basket_builder_view.html ]                     |
|            |       ├── Header Metadata: Basket Name Editor, Strategy Badge, Target Expiry, Draft Saved Timestamp  |
|            |       ├── Strategy Template Selector: 8 Invariant Scaffolding Cards                                  |
|            |       ├── Global Multiplier Stepper: Synchronized N x LotSize scaling across all legs                |
|            |       ├── Interactive Leg Grid Editor: Side, Symbol, Product, Order Type, Lots, Qty, Price, MP %     |
|            |       ├── Dependency Execution Graph (DAG): Visual Stages (Stage 1 Long Hedges -> Stage 2 Shorts)   |
|            |       ├── Pre-Flight Invariant Validation Checklist: 5-point verification against backend rules       |
|            |       ├── Margin & Capital Summary: Individual Gross Margin, Combined Relief Margin, Net Savings     |
|            |       ├── Exposure State Display: Net Premium Debit/Credit, Notional Exposure, Max P/L, Break-Even   |
|            |       ├── Execution Bar: Global ExecutionMode Indicator & Execute Button                             |
|            |       ├── Real-Time Execution Monitor: Progress Bar, Status Text, Leg FSM Cards, [🛑 Abort Remaining] |
|            |       └── Unsaved Changes Warning Modal: Discard confirmation protection                             |
|            |                                                                                                      |
|            +---> [ Front-End Controllers: static/js/ ]                                                            |
|                    ├── option_chain.js (Matrix table rendering, touchline updates, strike presets, sentiment bar) |
|                    └── basket_builder.js (Leg editor, templates, DAG pipeline, risk calc, auto-save, execution)  |
+-------------------------------------------------------------------------------------------------------------------+
```

---

## 3. Dedicated Architectural Scope Audits

### 3.1. Audit Item 1: Basket Builder UI
- **Location:** `templates/components/basket_builder_view.html`, mounted into `#view-baskets`.
- **Workbench Capabilities:** Provides a full-screen, dedicated trading desk workspace for multi-leg option combinations.
- **Controls & Metadata:** Header provides basket name input, current strategy badge, target expiry indicator, draft save status, and quick-action buttons (`[Clear All]`, `[➕ Add Leg]`, `[🔄 Refresh]`).

### 3.2. Audit Item 2: Strategy Template Selector (8 Invariant Patterns)
- **Scaffolding Engine:** 1-click automatic strike calculation relative to current spot price ($S$):
  1. **Bull Call Spread:** Buy ATM Call ($K_1 = S$), Sell OTM Call ($K_2 = S + \text{step}$).
  2. **Bear Put Spread:** Buy ATM Put ($K_1 = S$), Sell OTM Put ($K_2 = S - \text{step}$).
  3. **Long Straddle:** Buy ATM Call ($K = S$) + Buy ATM Put ($K = S$).
  4. **Long Strangle:** Buy OTM Call ($K_1 = S + \text{step}$) + Buy OTM Put ($K_2 = S - \text{step}$).
  5. **Iron Condor:** Buy OTM Put ($S - 2\Delta$) + Sell OTM Put ($S - \Delta$) + Sell OTM Call ($S + \Delta$) + Buy OTM Call ($S + 2\Delta$).
  6. **Iron Butterfly:** Buy OTM Put ($S - \Delta$) + Sell ATM Put ($S$) + Sell ATM Call ($S$) + Buy OTM Call ($S + \Delta$).
  7. **Covered Call:** Long Equity / Futures ($S$) + Sell OTM Call ($S + \text{step}$).
  8. **Protective Put:** Long Equity / Futures ($S$) + Buy ATM/OTM Put ($S - \text{step}$).

### 3.3. Audit Item 3: Leg Grid Editor
- **Interactive Controls:**
  - **Side Toggle:** Switch between `BUY` and `SELL` (automatically updates Stage 1 / Stage 2 DAG placement).
  - **Order Type:** Supports `LIMIT` and `MARKET`.
  - **Product Type:** Supports `MIS` (Intraday) and `NRML` (Overnight Carry-forward).
  - **Lot Multiplier Stepper:** Individual leg lots and global synchronized multiplier ($N \times \text{LotSize}$).
  - **Price Field:** Numeric input validated against NSE tick size (₹0.05).
  - **Market Protection %:** Defaults to 2.0% for simulated market protection limits.
  - **Actions:** Individual leg deletion (`[✕]`), move up (`[▲]`), and move down (`[▼]`).

### 3.4. Audit Item 4: Dependency DAG Visualization
- **Stage Ordering Invariant:**
  - **Stage 1 (Long Hedges):** All legs with `side == 'BUY'` are grouped into Stage 1. Executed first to guarantee exchange margin relief upfront.
  - **Stage 2 (Short Body / Writes):** All legs with `side == 'SELL'` are grouped into Stage 2. Executed only after Stage 1 fills successfully, avoiding catastrophic naked margin rejections.
- **Visual Nodes:** Color-coded DAG nodes render dynamically in `#dag-pipeline-container` with arrow indicators connecting Stage 1 to Stage 2.

### 3.5. Audit Item 5: Basket Validation Panel
- **Pre-Flight Invariant Checklist:**
  1. **Tick Size & Lot Multipliers:** Confirms prices are multiples of 0.05 and quantities match lot constraints.
  2. **Single-Expiry Spread Invariant:** Checks all legs share the identical expiry date (except for authorized calendar spreads).
  3. **Ratio & Wing Symmetry:** Confirms balanced contract counts for symmetric structures (e.g. Iron Condor 1:1:1:1).
  4. **Account Margin Sufficiency:** Confirms available margin $\ge$ combined relief margin.
  5. **Risk Limits & Exposure Ceiling:** Checks total basket commitment against pre-trade risk thresholds.
- **API Integration:** Hits `POST /api/baskets/validate` for dry-run verification before live order transmission.

### 3.6. Audit Item 6: Basket Risk Summary
- **Financial Metric Cards:**
  - **Individual Gross Margin:** Cumulative unhedged margin requirement across all individual legs:
    $$\text{Gross Margin} = \sum \text{Leg Margin}$$
  - **Combined Relief Margin:** Actual SPAN + Exposure requirement accounting for spread hedging benefits (~65% reduction for spreads):
    $$\text{Relief Margin} = \text{Gross Margin} \times 0.35$$
  - **Margin Savings:** Capital unlocked by sequential hedge construction:
    $$\text{Savings} = \text{Gross Margin} - \text{Relief Margin}$$
  - **Available Realized Cash:** Live account cash available for deployment.

### 3.7. Audit Item 7: Exposure State Display
- **Exposure State Grids:**
  - **Net Premium Flow:** Displays signed net cash flow in Rupees and Index points:
    $$\text{Net Premium} = \sum (\text{Price}_{\text{sell}} \times Q_{\text{sell}}) - \sum (\text{Price}_{\text{buy}} \times Q_{\text{buy}})$$
    Tagged clearly as `CREDIT` (green) or `DEBIT` (blue).
  - **Gross Notional Commitment:** Underwritten notional index value ($\sum Q \times S$).
  - **Max Defined Profit / Loss:** Absolute rupee bounds for defined-risk strategies.
  - **Break-Even Range:** Upper and lower underlying price levels at expiry ($K_{\min} \text{ — } K_{\max}$).
  - **Risk Classification:** Displays `DEFINED RISK` (green) or `UNLIMITED RISK` (red warning badge) when naked short legs exist.

### 3.8. Audit Item 8: Basket Execution Monitor
- **Execution Workflow:**
  - Dispatches `POST /api/baskets/<id>/execute`.
  - Displays `#basket-exec-monitor` with real-time percentage progress bar (`#monitor-progress-bar`).
  - Renders per-leg execution state cards reflecting transitions: `PENDING` $\to$ `SUBMITTED` $\to$ `TRADED` or `FAILED`.
  - **Emergency Abort Kill-Switch:** `[🛑 ABORT REMAINING LEGS]` calls `POST /api/baskets/<id>/cancel` to instantly halt subsequent stages if any leg is rejected or drops.

### 3.9. Audit Item 9: Option Chain UI
- **Matrix Layout:** Symmetrical table with Calls on the left, Strike price in the center, and Puts on the right.
- **Strike Presets:** Filter dropdown supports `ATM_5` (11 strikes), `ATM_10` (21 strikes), `ATM_15` (31 strikes), and `ATM_20` (41 strikes).
- **Visual Moneyness:**
  - ITM Call strikes (below spot) and ITM Put strikes (above spot) feature subtle amber shading (`rgba(255, 193, 7, 0.06)`).
  - The ATM Strike row is highlighted with a distinctive amber border and badge.

### 3.10. Audit Item 10: OI Visualization
- **Relative In-Cell Gradient Bars:**
  - Call OI and Put OI cells render a background progress bar proportional to the maximum OI in the visible chain:
    $$\text{OI Width \%} = \frac{\text{Strike OI}}{\max(\text{Total Chain OI})} \times 100\%$$
  - Provides instantaneous visual detection of major open interest concentration walls.

### 3.11. Audit Item 11: PCR Widget
- **Sentiment Strip:**
  - **Total Call OI & Put OI:** Aggregated contracts for selected expiry.
  - **PCR (Open Interest):** Put/Call ratio based on open interest ($>1.2$ Bullish, $<0.8$ Bearish, $0.8-1.2$ Neutral).
  - **PCR (Volume):** Put/Call ratio based on cumulative intraday volume.
  - **Max Pain Strike:** Theoretical strike price where option sellers face minimal loss.
  - **Key Support & Resistance:** Dynamically identified from peak Put OI (Support) and peak Call OI (Resistance).

### 3.12. Audit Item 12: Strategy Builder Shortcuts
- **Header Shortcut Bar:** 1-click strategy generation directly from the Option Chain view:
  - `[🐂 Bull Call]`, `[🐻 Bear Put]`, `[🎯 Straddle]`, `[⚡ Strangle]`, `[🦅 Iron Condor]`, `[🦋 Iron Butterfly]`.
  - Automatically loads the configured strikes into the Basket Drawer and expands the preview.

### 3.13. Audit Item 13: Option Chain -> Basket Integration
- **Row Action Buttons:**
  - `[B]` and `[S]`: Pre-fills the Order Ticket for direct single-leg trading.
  - `[➕ Leg]`: Adds the specific strike directly into the Active Strategy Basket.
  - `[📌]`: Adds the contract to the active Market Watchlist (`POST /api/market-watch/watchlists/1/items`).
- **Docked Basket Drawer:** `#basket-docked-drawer` sits at the terminal bottom, showing live leg count, estimated margin, and quick execute / expand controls.

### 3.14. Audit Item 14: Basket -> Execution Flow
- **Execution Safeguards:**
  - Validates all legs against the pre-flight endpoint before enabling `[🚀 EXECUTE BASKET]`.
  - In `LIVE` mode, prompts the user to type `CONFIRM_EXECUTE_BASKET`.
  - Sequential execution dispatches Stage 1 first, verifies confirmation, then dispatches Stage 2.

### 3.15. Audit Item 15: ExecutionMode Indicators
- **Visual Styling:**
  - `DISABLED`: Red badge, execution buttons completely disabled, warning tooltip displayed.
  - `PAPER`: Amber badge (`badge-paper`), executes safe paper simulation.
  - `LIVE`: Green pulse badge (`badge-live`), enforces strict typing verification.

### 3.16. Audit Item 16: Compact Mode Support
- **High-Density Ergonomics:**
  - Activating `.compact-mode` compresses row heights to 24px and reduces table cell padding to 2px 4px.
  - Fits 25+ strikes vertically on standard 1080p monitors without vertical scrolling.

### 3.17. Mandatory Addition 1: Basket Draft Auto-Save
- **LocalStorage Persistence:**
  - Persists uncommitted basket state in `localStorage` under `kotak_neo_basket_draft_v1` on every addition, deletion, or modification.
  - Displays `"Draft Auto-Saved: HH:mm:ss"` in `#basket-draft-status`.
  - Automatically restores active legs and metadata when the terminal is refreshed or reopened.

### 3.18. Mandatory Addition 2: Unsaved Changes Warning
- **Safety Modal:**
  - If $\ge 1$ legs exist in the active basket, triggering `[Clear All]`, clicking a different strategy template, or navigating away displays `#unsaved-changes-modal`.
  - Prevents accidental destruction of carefully assembled multi-leg configurations.

---

## 4. Invariants & Safety Verification

| Invariant / Mandate | Architectural Mechanism | Status |
| :--- | :--- | :--- |
| **No Autonomous Trading Bots** | Orders require explicit human click or shortcut. No background execution loops. | Verified |
| **No Greeks / Volatility Analytics** | Front-end strictly avoids Delta/Gamma/Vega/IV calculations. Clean touchline display. | Verified |
| **ExecutionMode Enforcement** | Execution completely refused when `DISABLED`. Mode inherited globally from backend. | Verified |
| **Sequential DAG Execution** | Long Hedges (Stage 1) execute prior to Short Body Writes (Stage 2) for SPAN relief. | Verified |
| **Idempotency & Re-entrancy** | Baskets generate deterministic idempotency keys (`client_basket_id`). | Verified |
| **The Golden Rule** | Missing or non-streaming data renders as `—` or `NONE`. No optimistic fills. | Verified |
| **Abort Remaining Kill-Switch** | Operator can halt in-flight multi-leg execution with a single click. | Verified |

---

## 5. Test Suite Results Summary

The complete integration test suite was executed across all components:

- **Phase 11D Integration Suite:** `tests/integration/test_basket_option_chain_ui_routes.py`
  - `test_terminal_loads_phase11d_components`: PASSED
  - `test_phase11d_static_assets`: PASSED
  - `test_option_chain_apis_integration`: PASSED
  - `test_basket_preflight_and_execution_integration`: PASSED
  - `test_basket_validation_error_on_empty_legs`: PASSED
- **Full Regression Test Suite:** `tests/`
  - Total Tests: **209 Passed**
  - Failures: **0**
  - Execution Time: **16.79s**
  - Code Regressions: **None**

---

## 6. Conclusion & Readiness

Phase 11D fulfills all functional and safety requirements specified in `PHASE11D_DESIGN_SPEC.md`, completing the fourth and final sub-phase of Phase 11. The **Kotak Neo Personal Trading Terminal** now features a unified, responsive, and robust front-end encompassing:
- **Phase 11A:** Terminal Shell & Workspace Layout
- **Phase 11B:** Market Watch Grid & Order Ticket
- **Phase 11C:** Portfolio, Positions, Order Book & Funds Ledger
- **Phase 11D:** Basket Builder & Option Chain Workbench

The system is production-ready for live manual trading operations under full operator control.

