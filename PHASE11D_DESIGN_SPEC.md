# Phase 11D Architectural Design Specification
## Basket Builder UI & Option Chain Workbench UI

**Document Version:** 1.1.0  
**Phase:** Phase 11D — Basket Builder UI & Option Chain Workbench UI  
**Target Milestone:** Milestone M6 Completion (Trading Terminal UI & Workbench Integration)  
**Baseline Dependencies:**
- Milestone M1 Baseline Locked (`M1_BASELINE`, commit `4d9341a`)
- Milestone M2 Baseline Locked (`M2_BASELINE`, commit `c4d30e6`): SFeed WebSocket Supervisor, Market Watch & Portfolio MTM
- Milestone M3 Baseline Locked (`M3_BASELINE`, commit `22dd3c8`): Order Domain Foundation, FSM & Risk Engine
- Milestone M4 Baseline Locked (`M4_BASELINE`, commit `2362ba8`): Order Execution Foundation, ExecutionMode & Audited Paper Engine
- Milestone M5 Baseline Locked (`M5_BASELINE`, commit `fcfb088`): Multi-Leg Baskets, Strategy Validation & Exposure Service
- Phase 10 Baseline Locked: Option Chain Matrix Engine, Presets & OI/PCR Scrapers (commit `e163800`)
- Phase 11A Baseline Locked: Terminal Shell, Workspace Persistence & Dark Theme (commit `3e76b57`)
- Phase 11B Baseline Locked: Market Watch Grid, Scrip Search Palette & Order Ticket (commit `3fefec3`)
- Phase 11C Baseline Locked: Demat Holdings, Positions, Order Book, Timeline View & Exit Threshold (commit `c5d8cf4`)
**Status:** Architectural Design (Pre-Implementation)  
**Implementation Constraint:** **Design specification only — Zero production implementation code generated in this phase**.

---

## Scope Exclusions (Strict Project Governance)

In strict adherence to the **PROJECT_CONSTITUTION** and terminal safety invariants:

- ❌ **No Autonomous Trading / Algorithmic Bots**: Zero automated trade dispatchers, auto-hedging algorithms, unprompted square-offs, or headless trade bots. Every basket submission, leg modification, and option order is initiated strictly by explicit operator click or keyboard shortcut.
- ❌ **No Background Market Scanners**: Zero autonomous polling loops scanning the option chain matrix to fire automated trades on breakout or volume thresholds.
- ❌ **No Greeks Engine**: Calculation of Black-Scholes Greeks (Delta, Gamma, Theta, Vega, Rho) remains strictly excluded from Phase 11D.
- ❌ **No Volatility Analytics**: Calculation of Implied Volatility (IV), IV Rank, IV Percentile, volatility smiles, and skew surfaces is excluded from Phase 11D.
- ❌ **No Direct Wire Bypassing**: The UI never communicates directly with raw broker endpoints. All order actions flow through:
  $$\text{Option Chain / Basket UI} \longrightarrow \text{Flask REST API} \longrightarrow \text{OrderExecutionService} \longrightarrow \text{ExecutionMode Gating} \longrightarrow \text{KotakOrderAdapter}$$
- ❌ **No Optimistic UI State Updates**: The UI never assumes a multi-leg basket or option order is `FILLED` until verified by the backend execution engine and EventBus broadcast ("The Golden Rule").
- ❌ **No Auto-Repair of Failed Legs**: If an execution leg fails or is rejected, the system never generates automated synthetic fixes or market orders; it aborts sequential execution and alerts the operator.

---

## 1. Executive Summary & Integration Architecture

Phase 11D delivers the interactive capstone of Milestone M6: the **Option Chain Workbench UI** and the **Multi-Leg Strategy & Basket Builder UI**. In modern derivatives trading, option contracts are not analyzed or executed in isolation. Traders evaluate symmetrical strike matrices around the spot price to assess Open Interest (OI) concentration and Put-Call Ratios (PCR), then assemble multi-leg spreads (e.g. Bull Call Spreads, Straddles, Iron Condors, Covered Calls) to define risk and optimize margin efficiency.

Phase 11D seamlessly bridges:
1. **The Option Chain Workbench (Phase 10):** Real-time symmetrical strike matrix (ATM $\pm 5$ to $\pm 20$), Spot price tracking, OI/Volume bar indicators, PCR widget, Max Pain detection, and single-click contract routing.
2. **The Strategy & Basket Builder (Phase 9):** Strategy template scaffolding, dynamic leg grid editor, visual DAG dependency sequencing (hedges first to secure exchange margin relief), pre-flight dry-run validation, and real-time execution progress monitoring.
3. **Execution Mode Governance (Phase 8):** Strict inheritance of `DISABLED`, `PAPER`, and `LIVE` modes with idempotency deduplication across all legs.
4. **Ergonomic Cockpit Capabilities (Phase 11A):** Native integration with Workspace Persistence and UI Density / Compact Mode toggles.

```
+===================================================================================================================+
|                                           PHASE 11D INTEGRATION TOPOLOGY                                          |
+===================================================================================================================+
|                                                                                                                   |
|    [ SFeed WebSocket Stream (Phase 4) ]                [ Kotak Neo SDK v3 / Scrip Master (Phase 10) ]              |
|                   │                                                           │                                   |
|                   ▼ Spot LTP & Strike Quotes                                  ▼ Expiries, Token Chains, OI        |
|  +─────────────────────────────────────────────────────────────────────────────────────────────────────────────+  |
|  │ OPTION CHAIN WORKBENCH UI (Phase 11D)                                                                       │  |
|  │  ├── Underlying Selector (Indices: NIFTY, BANKNIFTY; Equities: RELIANCE, etc.) & Favourites (★)             │  |
|  │  ├── Expiry Selector (Weekly W0, W1; Monthly M0, M1)                                                        │  |
|  │  ├── Strike Filter Presets: ATM ±5, ATM ±10, ATM ±15, ATM ±20                                               │  |
|  │  ├── Symmetrical Strike Matrix Grid (Call OI, Vol, LTP │ Strike │ LTP, Vol, Put OI)                         │  |
|  │  ├── Visual OI Horizontal Bar Distribution & Max Pain / PCR Sentiment Widget                                │  |
|  │  └── Row Quick Actions: [B] Buy, [S] Sell, [📌] Pin to Watchlist, [+] Add Leg to Basket                    │  |
|  +──────────────────────────────────────────────────────┬──────────────────────────────────────────────────────+  |
|                                                         │                                                         |
|         Single-Click Leg Addition                       │ Strategy Template Scaffolding                           |
|         (Calls, Puts, Selected Strikes)                 │ (8 Pre-Defined Invariant Templates)                     |
|                                                         ▼                                                         |
|  +─────────────────────────────────────────────────────────────────────────────────────────────────────────────+  |
|  │ MULTI-LEG STRATEGY & BASKET BUILDER UI (Phase 11D)                                                          │  |
|  │  ├── Strategy Template Selector (Bull Call, Bear Put, Straddle, Strangle, Iron Condor, Iron Butterfly,     │  |
|  │  │                                Covered Call, Protective Put, Custom)                                     │  |
|  │  ├── Leg Grid Editor (Leg #, Side BUY/SELL, Ratio, Product MIS/NRML, Order Type, Price, Lot Stepper)        │  |
|  │  ├── Dependency Sequencer (Visual DAG: Stage 1 Long Hedges ───► Stage 2 Short Body Strikes)                 │  |
|  │  ├── Pre-Flight Validation Panel (POST /api/baskets/validate -> Syntax, Lot Size, Tick 0.05, Expiry Invariant)│
|  │  ├── Risk & Margin Breakdown (Combined Margin Required vs Available Realized Cash)                           │  |
|  │  ├── Exposure State Display (Net Premium Debit/Credit, Gross Notional Exposure, Max Loss / Max Profit)      │  |
|  │  └── Execution Monitor (POST /api/baskets/execute -> Sequential Execution Progress Bar 0-100%, Leg FSMs)   │  |
|  +──────────────────────────────────────────────────────┬──────────────────────────────────────────────────────+  |
|                                                         │                                                         |
|                                                         ▼ Dispatches Atomic Orders via EventBus                   |
|  +─────────────────────────────────────────────────────────────────────────────────────────────────────────────+  |
|  │ PHASE 8 ORDER EXECUTION ENGINE (ExecutionMode: DISABLED, PAPER, LIVE)                                       │  |
|  │  ├── Idempotency Key Deduplication (client_basket_id + leg client_order_id)                                  │  |
|  │  ├── Execution Gating & FSM State Transitions (DRAFT ──► VALIDATED ──► SUBMITTED ──► PENDING ──► TRADED)    │  |
|  │  └── Circuit Breaker & The Golden Rule of Reconciliation                                                    │  |
|  +─────────────────────────────────────────────────────────────────────────────────────────────────────────────+  |
+===================================================================================================================+
```

---

## 2. Detailed Component Specifications (15 Target Items)

### 2.1. Basket Builder Screen (`#view-baskets`)

The Basket Builder serves as the primary composition, risk inspection, and execution desk for multi-leg orders.

```
+----------------------------------------------------------------------------------------------------------------------------------+
| BASKET BUILDER: [ Iron Condor (NIFTY 28NOV) ✏️ ]   [ Template: IRON_CONDOR ▼ ]  [ Clear All ]  [ Add Leg (Ctrl+L) ] [ 🔄 Refresh ]|
| Legs: 4 / 10 | Target Expiry: 28-NOV-2026 | Combined Lot Multiplier: [ 1x (25 Qty) ▲ ▼ ] | Strategy Invariant: VALID HEDGE PASS   |
+----------------------------------------------------------------------------------------------------------------------------------+
| # | Seq | Side | Instrument Symbol      | Product | Type  | Lots | Qty | Ref Price | Limit (₹) | MP (%) | Actions             |
|---+-----+------+------------------------+---------+-------+------+-----+-----------+-----------+--------+---------------------|
| 1 |  1  | BUY  | NIFTY28NOV24300PE (Put)| NRML    | LIMIT |  1x  |  25 |     85.50 |     86.00 |  2.0%  | [▲] [▼] [Mod] [✕]   |
| 2 |  1  | BUY  | NIFTY28NOV24700CE (Cal)| NRML    | LIMIT |  1x  |  25 |     88.00 |     88.50 |  2.0%  | [▲] [▼] [Mod] [✕]   |
| 3 |  2  | SELL | NIFTY28NOV24400PE (Put)| NRML    | LIMIT |  1x  |  25 |    112.00 |    111.50 |  2.0%  | [▲] [▼] [Mod] [✕]   |
| 4 |  2  | SELL | NIFTY28NOV24600CE (Cal)| NRML    | LIMIT |  1x  |  25 |    132.00 |    131.50 |  2.0%  | [▲] [▼] [Mod] [✕]   |
+----------------------------------------------------------------------------------------------------------------------------------+
| DEPENDENCY EXECUTION GRAPH (DAG):                                                                                                |
|   Stage 1 (Hedge Wings): [ BUY 24300 PE ] + [ BUY 24700 CE ] (Executes first to guarantee margin relief)                        |
|             │                                                                                                                    |
|             ▼ (On Stage 1 Confirmation)                                                                                          |
|   Stage 2 (Short Body):  [ SELL 24400 PE ] + [ SELL 24600 CE ] (Executes under reduced margin block)                             |
+----------------------------------------------------------------------------------------------------------------------------------+
| MARGIN & RISK SUMMARY:                                                                                                           |
|   Individual Leg Gross Margin: ₹2,45,000.00  │ Combined Basket Relief Margin: ₹58,400.00  │ Est. Net Credit: +₹1,750.00 (70 pts) |
|   Available Realized Cash:     ₹1,85,000.00  │ Margin Sufficiency Status:     PASS (SAFE) │ Max Loss (Wings):   -₹3,250.00 (130 pts)|
+----------------------------------------------------------------------------------------------------------------------------------+
| EXECUTION MODE: [ PAPER TRADING MODE ]                                          [ VALIDATE BASKET ]  [ EXECUTE BASKET (Enter) ]  |
+----------------------------------------------------------------------------------------------------------------------------------+
```

#### Key Architecture & Interaction Points:
- **Dual Presentation Modes:**
  1. *Dedicated View:* Full workbench loaded into `#view-baskets`.
  2. *Integrated Option Chain Drawer:* Slide-up drawer (`#basket-docked-drawer`) accessible directly within `#view-option-chain`.
- **Capacity Constraint:** Strictly capped at 10 legs per basket in accordance with Phase 9 invariants.
- **Client Basket UUID:** Automatically generates a canonical `client_basket_id` (UUIDv4) upon creation, enforcing client-side deduplication.

---

### 2.2. Strategy Template Selector

The Strategy Template Selector provides instant 1-click scaffolding for the **8 constitutional strategy patterns** validated by Phase 9 `StrategyValidator`:

```
+-----------------------------------------------------------------------------------------------------------------------+
| STRATEGY TEMPLATES SELECTOR                                                                                           |
+-----------------------------------------------------------------------------------------------------------------------+
|  [ 1. BULL CALL SPREAD ]     [ 2. BEAR PUT SPREAD ]      [ 3. LONG STRADDLE ]        [ 4. LONG STRANGLE ]             |
|  Buy ATM Call + Sell OTM Call  Buy ATM Put + Sell OTM Put  Buy ATM Call + Put          Buy OTM Call + Put             |
|  (Debit Directional Bullish) (Debit Directional Bearish) (Vol Breakout Debit)       (Vol Expansion Debit)             |
|                                                                                                                       |
|  [ 5. IRON CONDOR ]          [ 6. IRON BUTTERFLY ]       [ 7. COVERED CALL ]         [ 8. PROTECTIVE PUT ]            |
|  Buy Wings + Sell Body       Buy Wings + Sell ATM Straddle Long Cash Stock + Short Call Long Cash Stock + Long Put     |
|  (Defined Risk Credit)       (Defined Risk High Premium) (Income on Demat Holdings)  (Downside Insurance on Holdings) |
+-----------------------------------------------------------------------------------------------------------------------+
```

#### Mathematical & Structural Rules per Template:
1. **Bull Call Spread (2 Legs, Debit):**
   - Leg 1: BUY $K_{\text{ATM}}$ Call ($1$ lot, NRML/MIS).
   - Leg 2: SELL $K_{\text{ATM}} + \text{Offset}$ Call ($1$ lot, NRML/MIS).
   - Invariant: Expiry identical; $K_{\text{Sell}} > K_{\text{Buy}}$.
2. **Bear Put Spread (2 Legs, Debit):**
   - Leg 1: BUY $K_{\text{ATM}}$ Put ($1$ lot).
   - Leg 2: SELL $K_{\text{ATM}} - \text{Offset}$ Put ($1$ lot).
   - Invariant: Expiry identical; $K_{\text{Sell}} < K_{\text{Buy}}$.
3. **Long Straddle (2 Legs, Volatility Debit):**
   - Leg 1: BUY $K_{\text{ATM}}$ Call ($1$ lot).
   - Leg 2: BUY $K_{\text{ATM}}$ Put ($1$ lot).
   - Invariant: Expiry and Strike identical ($K_{\text{Call}} = K_{\text{Put}} = K_{\text{ATM}}$).
4. **Long Strangle (2 Legs, OTM Volatility Debit):**
   - Leg 1: BUY $K_{\text{ATM}} + \text{Offset}$ Call ($1$ lot).
   - Leg 2: BUY $K_{\text{ATM}} - \text{Offset}$ Put ($1$ lot).
   - Invariant: Expiry identical; $K_{\text{Call}} > K_{\text{Put}}$.
5. **Iron Condor (4 Legs, Defined Risk Credit):**
   - Leg 1 (Put Wing / Hedge): BUY $K_{\text{ATM}} - 2 \times \text{Offset}$ Put (Stage 1).
   - Leg 2 (Call Wing / Hedge): BUY $K_{\text{ATM}} + 2 \times \text{Offset}$ Call (Stage 1).
   - Leg 3 (Put Body / Short): SELL $K_{\text{ATM}} - 1 \times \text{Offset}$ Put (Stage 2).
   - Leg 4 (Call Body / Short): SELL $K_{\text{ATM}} + 1 \times \text{Offset}$ Call (Stage 2).
   - Invariant: 4 distinct strikes; symmetric wing offsets; $1:1:1:1$ ratio.
6. **Iron Butterfly (4 Legs, Defined Risk High Credit):**
   - Leg 1 (Put Wing): BUY $K_{\text{ATM}} - \text{Offset}$ Put (Stage 1).
   - Leg 2 (Call Wing): BUY $K_{\text{ATM}} + \text{Offset}$ Call (Stage 1).
   - Leg 3 (Short Straddle Body): SELL $K_{\text{ATM}}$ Call (Stage 2).
   - Leg 4 (Short Straddle Body): SELL $K_{\text{ATM}}$ Put (Stage 2).
   - Invariant: Short Call and Short Put share $K_{\text{ATM}}$; outer wings symmetric.
7. **Covered Call (2 Legs, Income Generation):**
   - Leg 1 (Equity Underlying): LONG Equity Stock ($1$ lot equivalent, CNC Demat or MIS).
   - Leg 2 (Short Option): SELL $K_{\text{ATM}} + \text{Offset}$ Call ($1$ lot, NRML/MIS).
   - Invariant: Short Call quantity $\le$ Underlying equity lot size.
8. **Protective Put (2 Legs, Portfolio Insurance):**
   - Leg 1 (Equity Underlying): LONG Equity Stock ($1$ lot equivalent, CNC Demat or MIS).
   - Leg 2 (Hedge Option): BUY $K_{\text{ATM}}$ or $K_{\text{ATM}} - \text{Offset}$ Put ($1$ lot, NRML/MIS).
   - Invariant: Put hedge quantity matches underlying position.

---

### 2.3. Leg Grid Editor

The Leg Grid Editor provides interactive manipulation of individual legs within the strategy structure:

- **Row Controls:**
  - **Index / Sequence Stepper:** `[▲]` / `[▼]` moves leg up or down in execution order.
  - **Side Toggle:** Switch between `BUY` (Blue) and `SELL` (Crimson).
  - **Instrument Display:** Trading symbol, segment pill (`NSE_FO`, `BSE_FO`, `NSE_CM`), and contract moneyness badge (`ITM`, `ATM`, `OTM`).
  - **Product Selector:** Dropdown for `NRML`, `MIS`, or `CNC` (equities only).
  - **Order Type:** `LIMIT` or `MARKET`.
  - **Price Inputs:** Modulo rounding to $0.05$ tick size. When `MARKET` is selected, price input disables and displays Market Protection Buffer ($2.0\%$).
  - **Individual Lot Stepper:** Step lot size up/down while respecting the exchange lot multiplier ($25, 50, 75 \dots$).
  - **Delete Action:** `[✕]` deletes the leg and triggers real-time strategy re-validation.
- **Global Lot Multiplier Bar:**
  - Synchronously scales all leg quantities by integer factor $N \times \text{LotSize}$ while preserving strategy ratios (e.g. $1:1$ or $1:2$).

---

### 2.4. Basket Pre-Flight Validation Panel

The Validation Panel invokes `POST /api/baskets/validate` without touching broker wires. It displays a visual pre-flight inspection checklist:

```
+-------------------------------------------------------------------------------------------------------+
| PRE-FLIGHT BASKET VALIDATION CHECKLIST                                               [ Status: PASS ] |
+-------------------------------------------------------------------------------------------------------+
| [✓] 1. SYNTAX & LOT SIZES:   All 4 legs match NSE lot size (25) and tick size modulo 0.05.           |
| [✓] 2. EXPIRY INVARIANT:     All 4 legs belong to identical expiry: 28-NOV-2026.                      |
| [✓] 3. RATIO INVARIANTS:     1:1:1:1 Iron Condor ratio balance confirmed.                             |
| [✓] 4. MARGIN SUFFICIENCY:   Required ₹58,400.00 <= Available Realized Cash ₹1,85,000.00.             |
| [✓] 5. SPREAD RISK CEILING:  Max loss ₹3,250.00 is well within daily loss limit (₹20,000.00).         |
| [✓] 6. EXECUTION MODE:       PAPER mode active. Virtual exchange simulator engaged.                  |
+-------------------------------------------------------------------------------------------------------+
| Result: Strategy structure approved. Ready for human-authorized execution.                            |
+-------------------------------------------------------------------------------------------------------+
```

- **Structural Violations:** If an invariant fails (e.g. mixed expiries, broken wing symmetry), the panel turns crimson and lists specific failure codes (`INVALID_EXPIRY_MISMATCH`, `ASYMMETRIC_WINGS`).
- **Execution Button Gating:** The `[EXECUTE BASKET]` button remains strictly disabled until validation returns `valid: true`.

---

### 2.5. Basket Risk Summary

The Risk Summary widget computes algebraic risk metrics across the strategy legs:

1. **Individual Leg Gross Margin:** $\sum \text{Isolated Margin}_i$ (unhedged margin requirement).
2. **Combined Basket Relief Margin:** Exchange SPAN margin accounting for cross-leg risk offset.
3. **Margin Relief Savings:**
   $$\text{Margin Relief (₹)} = \text{Individual Gross Margin} - \text{Combined Basket Margin}$$
4. **Estimated Net Premium Flow:**
   $$\text{Net Flow (₹)} = \sum_{\text{Short Legs}} (\text{Qty}_i \times \text{Price}_i) - \sum_{\text{Long Legs}} (\text{Qty}_j \times \text{Price}_j)$$
   - Positive $\implies$ Net Credit Received (Green badge).
   - Negative $\implies$ Net Debit Paid (Blue badge).
5. **Capital Adequacy Gauge:** Visual badge indicating whether `Available Cash` $\ge$ `Combined Margin Required`.

---

### 2.6. Exposure State Display

The Exposure State Display provides clear financial visibility into the gross notional commitment:

```
+-------------------------------------------------------------------------------------------------------+
| BASKET EXPOSURE STATE DISPLAY                                                                         |
+-------------------------------------------------------------------------------------------------------+
| Net Premium Flow:         +₹1,750.00 [ NET CREDIT (70.00 pts) ]                                       |
| Gross Notional Exposure:   ₹24,53,240.00 (Total underlying contract commitment: 100 Qty @ 24,532.40)   |
| Maximum Defined Profit:   +₹1,750.00 (Achieved if underlying closes between 24,400 and 24,600)       |
| Maximum Defined Loss:     -₹3,250.00 (Wing spread 200 pts - Net credit 70 pts = 130 pts * 25 Qty)     |
| Risk-Reward Ratio:         1 : 1.86                                                                   |
| Lower Break-Even:         24,330.00 (24,400 Body - 70 pts credit)                                     |
| Upper Break-Even:         24,670.00 (24,600 Body + 70 pts credit)                                     |
+-------------------------------------------------------------------------------------------------------+
```

- **Defined Risk vs Naked Risk Warning:**
  - If strategy is defined risk (e.g. Iron Condor, Bull Call Spread), displays green badge `[ DEFINED RISK ]`.
  - If strategy contains naked short legs (e.g. Short Straddle, Naked Call), displays flashing amber warning banner:
    `⚠️ UNLIMITED RISK STRATEGY: Maximum theoretical loss is undefined. Requires active monitoring.`

---

### 2.7. Basket Execution Monitor & Real-Time FSM Progress

Tracks sequential multi-stage execution in real time:

```
+-------------------------------------------------------------------------------------------------------+
| BASKET EXECUTION IN PROGRESS: bsk_1107_9821                                  [ Mode: PAPER ] [ 75% ]  |
+-------------------------------------------------------------------------------------------------------+
| Overall Progress: [===========================================|==============] (3 of 4 Legs Filled)   |
| Elapsed Time: 185 ms │ Stage 1: COMPLETED (120 ms) │ Stage 2: IN PROGRESS                             |
+-------------------------------------------------------------------------------------------------------+
| Leg # | Symbol            | Side | Qty | Order ID          | Stage   | Status    | Fill Price (₹)     |
|-------+-------------------+------+-----+-------------------+---------+-----------+--------------------|
| 1     | NIFTY 24300 PE    | BUY  |  25 | cli_ord_1107_01   | Stage 1 | FILLED    | 85.80 (Slippage: +0|
| 2     | NIFTY 24700 CE    | BUY  |  25 | cli_ord_1107_02   | Stage 1 | FILLED    | 88.20 (Slippage: +0|
| 3     | NIFTY 24400 PE    | SELL |  25 | cli_ord_1107_03   | Stage 2 | FILLED    | 112.00 (Exact)     |
| 4     | NIFTY 24600 CE    | SELL |  25 | cli_ord_1107_04   | Stage 2 | SUBMITTED | Pending Exchange...|
+-------------------------------------------------------------------------------------------------------+
| Emergency Action: [ 🛑 ABORT REMAINING LEGS ]                                                          |
+-------------------------------------------------------------------------------------------------------+
```

- **Progress Bar:** Real-time visual progress fill ($0\% \to 100\%$).
- **Sequential Stage Gating:** Stage 2 orders are not dispatched until all Stage 1 orders transition to `FILLED`.
- **Immediate Abort:** Clicking `[🛑 ABORT REMAINING LEGS]` halts remaining stages via `POST /api/baskets/{id}/cancel`.

---

### 2.8. Option Chain Screen (`#view-option-chain`)

The Option Chain Screen presents the symmetrical strike ladder centered dynamically on the underlying spot price.

```
+----------------------------------------------------------------------------------------------------------------------------------+
| OPTION CHAIN WORKBENCH                                               [ ★ Favourites: NIFTY 50 ▼ ] [ SFeed: LIVE (12ms) ] [ 🔄 ]  |
| Underlying: [ NIFTY 50 ▼ ]  Spot: 24,532.40 (+124.50, +0.51%)  Expiry: [ 28-NOV-2026 (Monthly M0) ▼ ]  Filter: [ ATM ±10 ▼ ]     |
| Total Call OI: 14,25,400 | Total Put OI: 18,52,200 | PCR (OI): 1.30 (BULLISH) | PCR (Vol): 1.15 | Max Pain Strike: 24,500        |
+----------------------------------------------------------------------------------------------------------------------------------+
|               CALLS (NSE_FO)              |   STRIKE   |               PUTS (NSE_FO)               |           ACTIONS           |
|   OI (Lots) | Vol (k) | Chg (₹) | LTP (₹) |   PRICE    | LTP (₹) | Chg (₹) | Vol (k) |   OI (Lots) | Pin to WL | Add to Basket   |
|-------------+---------+---------+---------+------------+---------+---------+---------+-------------+-----------+-----------------|
| [====] 45.2k|   12.4  |  +45.20 |  310.00 |  24,300 ITM|   85.50 |  -35.10 |    8.2  | [==]  18.4k | [📌]      | [B] [S] [➕ Leg] |
| [===]  32.1k|   18.5  |  +38.00 |  242.00 |  24,400 ITM|  112.00 |  -42.00 |   14.5  | [===] 28.1k | [📌]      | [B] [S] [➕ Leg] |
| [======]82.4|   45.2  |  +30.50 |  185.00 |  24,500 ATM|  154.50 |  -51.20 |   32.1  | [======]78.2| [📌]      | [B] [S] [➕ Leg] |
| [====] 48.0k|   28.1  |  +22.00 |  132.00 |  24,600 OTM|  205.00 |  -60.00 |   22.4  | [====]42.0k | [📌]      | [B] [S] [➕ Leg] |
| [==]   24.5k|   15.2  |  +14.50 |   88.00 |  24,700 OTM|  262.00 |  -72.00 |   18.0  | [==]  21.5k | [📌]      | [B] [S] [➕ Leg] |
+----------------------------------------------------------------------------------------------------------------------------------+
```

- **Symmetrical Presets:** `ATM ±5` (11 strikes), `ATM ±10` (21 strikes), `ATM ±15` (31 strikes), `ATM ±20` (41 strikes).
- **Moneyness Shading:** ITM Call and Put zones shaded soft amber/gold (`rgba(255, 193, 7, 0.08)`).
- **ATM Strike Highlighting:** Center strike row styled with bright border and badge.

---

### 2.9. Open Interest (OI) & Volume Visualization

- **Horizontal Magnitude Bars:** Background CSS linear gradient bars in OI cells indicate relative open interest compared to the maximum strike OI across the chain.
- **Key Support & Resistance Markers:**
  - Strike with highest Call OI labeled with **Resistance badge** `[R: 25,000 CE]`.
  - Strike with highest Put OI labeled with **Support badge** `[S: 24,000 PE]`.
- **Change in OI (dOI):** Positive change rendered in green; unwinding (negative change) rendered in red.

---

### 2.10. Put-Call Ratio (PCR) Widget

- Displays both Open Interest PCR and Traded Volume PCR:
  $$\text{PCR}_{\text{OI}} = \frac{\sum \text{Put OI}}{\sum \text{Call OI}}, \quad \text{PCR}_{\text{Vol}} = \frac{\sum \text{Put Volume}}{\sum \text{Call Volume}}$$
- **Sentiment Indicator Badge:**
  - `PCR > 1.20`: Bullish (Green).
  - `0.80 <= PCR <= 1.20`: Neutral (Amber).
  - `PCR < 0.80`: Bearish (Red).
- **Max Pain Strike:** Calculated via cumulative intrinsic loss minimization and displayed prominently in the header.

---

### 2.11. Strategy Builder Shortcuts

Quick-action toolbar positioned directly atop the Option Chain:

- `[🐂 Bull Call]`: Auto-selects ATM Call + OTM Call and pushes into Basket Builder.
- `[🐻 Bear Put]`: Auto-selects ATM Put + OTM Put and pushes into Basket Builder.
- `[🎯 Long Straddle]`: Auto-selects ATM Call + ATM Put.
- `[🦅 Iron Condor]`: Auto-selects 4 strikes around ATM with symmetric wings.
- `[🧺 Open Basket (Alt+B)]`: Slides open the docked strategy drawer.

---

### 2.12. Option Chain $\longrightarrow$ Basket Builder Integration

- **Seamless Data Flow:** Clicking `[➕ Leg]` on any strike row pushes the contract payload:
  $$\{ \text{token}, \text{symbol}, \text{segment}, \text{side}, \text{price}, \text{lot\_size}, \text{product} \}$$
  directly into `window.basketBuilderController.addLeg(payload)`.
- **Zero Page Reload:** Adds leg dynamically to the docked drawer without resetting option chain scroll position or WebSocket streaming subscriptions.

---

### 2.13. Basket $\longrightarrow$ Execution Flow

The end-to-end execution lifecycle strictly follows the Phase 9 Finite State Machine:

```
[ Operator Clicks Execute Basket ]
                │
                ▼
+───────────────────────────────────────+
| 1. Idempotency Lock & Key Generation  |
|    client_basket_id + Leg Order UUIDs |
+───────────────────────────────────────+
                │
                ▼
+───────────────────────────────────────+
| 2. ExecutionMode Safety Gate Check    |
|    - DISABLED: Refused with warning   |
|    - PAPER: Simulates exchange fills  |
|    - LIVE: Challenge string check     |
+───────────────────────────────────────+
                │
                ▼
+───────────────────────────────────────+
| 3. Pre-Flight Risk & Margin Approval  |
|    - Margin sufficiency verified      |
|    - Invariants and tick size valid   |
+───────────────────────────────────────+
                │
                ▼
+───────────────────────────────────────+
| 4. Stage 1 Execution (Long Hedges)    |
|    - Wire dispatch to Kotak Adapter   |
|    - Poller monitors fills            |
+───────────────────────────────────────+
                │
      (All Stage 1 Filled?)
     ┌──────────┴──────────┐
     ▼ YES                 ▼ NO (Rejected / Timeout)
+──────────────────+   +───────────────────────────────────+
| 5. Stage 2       |   | 6. Emergency Sequential Abort     |
|    (Short Body)  |   |    Stage 2 canceled; Alert Trader |
+──────────────────+   +───────────────────────────────────+
```

---

### 2.14. ExecutionMode Indicators & Visual Governance

- **Persistent Header Badge:** Displays current active mode (`DISABLED`, `PAPER`, `LIVE`).
- **Execution Bar Theme:**
  - `DISABLED`: Red warning banner; submit button disabled with lockout tooltip.
  - `PAPER`: Gold/Amber banner indicating simulated fills.
  - `LIVE`: High-visibility Crimson/Green banner with prompt requiring typing challenge string `CONFIRM_EXECUTE_BASKET`.

---

### 2.15. Compact Mode Support (`.compact-mode`)

Integrated with the Phase 11A UI density engine:

- When `#app-root` carries `.compact-mode`:
  - Table row height reduces from $36\text{px}$ to $26\text{px}$.
  - Data cells use dense $11\text{px}$ monospace numeric typography.
  - Symmetrical strike matrix displays 25+ strikes without vertical scrolling on standard $1080\text{p}$ monitors.
  - Basket drawer collapses into a high-density single-line summary strip.
  - Action buttons shrink to ultra-compact $20\text{px}$ icon triggers (`.btn-xs`).

---

### 2.16. Basket Draft Auto-Save Architecture

To protect options traders from accidental data loss during active spread modeling:
- **Persistence Storage:** Working basket state is automatically serialized to `localStorage` under `kotak_neo_basket_draft_v1`.
- **Payload Schema:** Stores `client_basket_id`, `name`, `strategy_type`, `underlying`, `expiry_date`, `lot_multiplier`, and full array of `legs`.
- **Auto-Save Frequency:** Debounced auto-save triggers on every modification:
  - Leg addition, deletion, or sequence adjustment.
  - Price, order type, product, or lot size change.
  - Template scaffolding instantiation.
- **Visual Feedback:** Header displays real-time auto-save label: `"Draft Auto-Saved: HH:mm:ss"`.
- **Session Restoration:** Automatically restores uncommitted basket draft upon workspace tab activation or browser refresh.

---

### 2.17. Unsaved Changes Warning System

Prevents inadvertent destruction of complex multi-leg strategy configurations:
- **Dirty State Tracking:** The Basket Controller maintains `isDirty` and `hasUnsavedChanges()` flags. A draft is considered "dirty" when it contains $\ge 1$ legs that have not yet been executed.
- **Protected Actions:**
  1. **Clear All Basket Action (`[Clear All]` or `Alt + C`):** Intercepts reset and prompts confirmation dialog:
     *"⚠️ DISCARD BASKET: You have active strategy legs in your draft basket. Are you sure you want to discard all changes?"*
  2. **Strategy Template Switching:** If legs exist and the operator selects a different strategy template, warns before overwriting current leg grid.
  3. **Browser Unload / Tab Navigation:** Binds `window.addEventListener('beforeunload', ...)` when dirty, triggering standard browser confirmation.

---

## 3. Data Models & Front-End State Contracts

```typescript
// Symmetrical Strike Row in Option Chain
interface OptionChainStrikeRow {
  strike_price: number;
  is_atm: boolean;
  moneyness: 'ITM' | 'ATM' | 'OTM';
  call: {
    instrument_token: string;
    trading_symbol: string;
    exchange_segment: string;
    last_price: number;
    change: number;
    change_percent: number;
    open_interest: number;
    change_oi: number;
    volume: number;
    oi_relative_pct: number;
    is_key_resistance: boolean;
  };
  put: {
    instrument_token: string;
    trading_symbol: string;
    exchange_segment: string;
    last_price: number;
    change: number;
    change_percent: number;
    open_interest: number;
    change_oi: number;
    volume: number;
    oi_relative_pct: number;
    is_key_support: boolean;
  };
}

// Basket Leg Model
interface BasketLeg {
  id: string; // client UUID
  instrument_token: string;
  trading_symbol: string;
  exchange_segment: string;
  side: 'BUY' | 'SELL';
  product_type: 'MIS' | 'NRML' | 'CNC';
  order_type: 'LIMIT' | 'MARKET';
  lot_size: number;
  lots: number;
  quantity: number;
  price: number;
  trigger_price: number;
  market_protection_percent: number;
  execution_stage: number; // 1 for hedges, 2 for shorts
  client_order_id?: string;
  status?: 'DRAFT' | 'VALIDATED' | 'SUBMITTED' | 'PENDING' | 'FILLED' | 'REJECTED' | 'CANCELLED';
  fill_price?: number;
}

// Basket Model
interface BasketModel {
  client_basket_id: string;
  name: string;
  strategy_type: 'BULL_CALL_SPREAD' | 'BEAR_PUT_SPREAD' | 'STRADDLE' | 'STRANGLE' | 'IRON_CONDOR' | 'IRON_BUTTERFLY' | 'COVERED_CALL' | 'PROTECTIVE_PUT' | 'CUSTOM';
  underlying: string;
  expiry_date: string;
  legs: BasketLeg[];
  lot_multiplier: number;
  execution_mode: 'DISABLED' | 'PAPER' | 'LIVE';
  status: 'DRAFT' | 'VALIDATED' | 'EXECUTING' | 'COMPLETED' | 'FAILED' | 'ABORTED';
}

// Basket Validation Result
interface BasketValidationResult {
  valid: boolean;
  strategy_recognized: boolean;
  strategy_name: string;
  violations: string[];
  total_gross_margin: number;
  net_basket_margin: number;
  margin_relief: number;
  available_cash: number;
  is_margin_sufficient: boolean;
  estimated_net_cost: number; // positive = debit, negative = credit
  max_loss?: number;
  max_profit?: number;
  break_even_lower?: number;
  break_even_upper?: number;
}
```

---

## 4. Keyboard Shortcuts & Workflow Ergonomics

| Key Binding | Scope | Action |
| :--- | :--- | :--- |
| `Alt + 5` | Global | Switch to Option Chain Workbench tab |
| `Alt + 6` | Global | Switch to Basket Builder tab |
| `Alt + B` | Option Chain | Toggle / Slide active Basket drawer |
| `Alt + C` | Basket Builder | Clear current basket legs |
| `Ctrl + Enter`| Basket Builder | Run Pre-Flight Validation / Submit Execution |
| `Esc` | Modals / Drawer | Close modals or slide down basket drawer |
| `Ctrl + L` | Basket Builder | Open manual leg addition dialog |
| `↑` / `↓` | Option Chain | Navigate strikes vertically |
| `B` / `S` | Selected Strike | Open Order Ticket with highlighted strike |
| `+` | Selected Strike | Add highlighted strike to Basket |
| `Ctrl + P` | Selected Strike | Pin highlighted contract to active Watchlist |

---

## 5. Implementation Roadmap (Sub-Phase 11D Plan)

Following the proven modular sub-phase methodology, implementation will proceed through:

1. **HTML Component Templates:**
   - `templates/components/option_chain_view.html`: Full symmetrical strike matrix, underlying/expiry dropdowns, PCR widget, strategy shortcut bar.
   - `templates/components/basket_builder_view.html`: Leg grid editor, 8 template buttons, DAG visualizer, risk card, exposure state display.
   - `templates/components/basket_drawer.html`: Docked slide-up drawer for Option Chain $\to$ Basket integration.
2. **Stylesheets (`static/css/baskets_option_chain.css`):**
   - High-contrast matrix grid, in-cell OI horizontal bar charts, ITM amber shading, DAG node pipeline, and compact mode overrides.
3. **Front-End Controllers (`static/js/`):**
   - `option_chain.js`: Symmetrical matrix renderer, WebSocket touchline listener, PCR calculator, watchlist pin handler.
   - `basket_builder.js`: Leg grid state manager, 8 template instantiators, validation runner, sequential execution monitor.
4. **Integration Testing (`tests/integration/test_basket_option_chain_ui_routes.py`):**
   - Verifying all template mounts, static assets, Option Chain $\to$ Basket data transfer, 8 strategy templates, pre-flight validation, and paper basket execution.
5. **Phase 11D Architecture Review:**
   - Formal audit and sign-off document (`PHASE11D_ARCHITECTURE_REVIEW.md`).
