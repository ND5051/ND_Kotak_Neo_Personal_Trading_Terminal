# Phase 11D Architectural Design Specification
## Basket Builder & Option Chain UI

**Document Version:** 1.0.0  
**Phase:** Phase 11D — Basket Builder & Option Chain UI  
**Target Milestone:** Milestone M6 Completion (Trading Terminal UI & Workbench Integration)  
**Baseline Dependencies:**
- Milestone M1 Baseline Locked (`M1_BASELINE`, commit `4d9341a`)
- Milestone M2 Baseline Locked (`M2_BASELINE`, commit `c4d30e6`): WebSocket Supervisor, Market Watch & Portfolio MTM
- Milestone M3 Baseline Locked (`M3_BASELINE`, commit `22dd3c8`): Order Domain Foundation, FSM & Risk Engine
- Milestone M4 Baseline Locked (`M4_BASELINE`, commit `2362ba8`): Order Execution Foundation, ExecutionMode & Audited Paper Engine
- Milestone M5 Baseline Locked (`M5_BASELINE`, commit `fcfb088`): Multi-Leg Baskets, Strategy Validation & Exposure Service
- Phase 10 Baseline Locked: Option Chain Matrix Engine, Presets & OI/PCR Scrapers (commit `e163800`)
- Phase 11A Baseline Locked: Terminal Shell, Workspace Persistence & Dark Theme (commit `3e76b57`)
- Phase 11B Baseline Locked: Market Watch Grid, Scrip Search Palette & Order Ticket (commit `3fefec3`)
- Phase 11C Baseline Locked: Demat Holdings, Positions, Order Book & Timeline View (commit `d234825`)
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

Phase 11D delivers the interactive capstone of Milestone M6: the **Option Chain Workbench UI** and the **Multi-Leg Strategy & Basket Builder UI**. In modern derivatives trading, option contracts are not analyzed or executed in isolation. Traders evaluate symmetrical strike matrices around the spot price to assess Open Interest (OI) concentration and Put-Call Ratios (PCR), then assemble multi-leg spreads (e.g. Bull Call Spreads, Straddles, Iron Condors) to define risk and optimize margin efficiency.

Phase 11D seamlessly bridges:
1. **The Option Chain Workbench (Phase 10):** Real-time symmetrical strike matrix (ATM $\pm 5$ to $\pm 20$), Spot price tracking, OI/Volume bar indicators, PCR widget, Max Pain detection, and single-click contract routing.
2. **The Strategy & Basket Builder (Phase 9):** Strategy template scaffolding, dynamic leg grid editor, visual DAG dependency sequencing (hedges first to secure exchange margin relief), pre-flight dry-run validation, and real-time execution progress monitoring.
3. **Execution Mode Governance (Phase 8):** Strict inheritance of `DISABLED`, `PAPER`, and `LIVE` modes with idempotency deduplication across all legs.

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
|         (Calls, Puts, Selected Strikes)                 │ (Bull Call, Iron Condor, Straddle)                      |
|                                                         ▼                                                         |
|  +─────────────────────────────────────────────────────────────────────────────────────────────────────────────+  |
|  │ MULTI-LEG STRATEGY & BASKET BUILDER UI (Phase 11D)                                                          │  |
|  │  ├── Strategy Template Picker (Bull Call, Bear Put, Straddle, Strangle, Iron Condor, Custom)                │  |
|  │  ├── Leg Grid Editor (Leg #, Side BUY/SELL, Ratio, Product MIS/NRML, Order Type, Price, Lot Stepper)        │  |
|  │  ├── Dependency Sequencer (Visual DAG: Stage 1 Long Hedges ───► Stage 2 Short Body Strikes)                 │  |
|  │  ├── Pre-Flight Validation View (POST /api/baskets/validate -> Syntax, Lot Size, Tick 0.05, Expiry Invariant)│
|  │  ├── Risk & Margin Breakdown (Combined Margin Required vs Available Realized Cash)                           │  |
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

## 2. Core Functional Requirements & Wireframe Specifications

### 2.1. Option Chain Workbench UI (`#view-option-chain`)

The Option Chain Workbench provides an institutional, high-density view of the option contracts surrounding the underlying spot price.

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
| Quick Strategy Templates: [ 🐂 Bull Call Spread ] [ 🐻 Bear Put Spread ] [ 🎯 Long Straddle ] [ 🦅 Iron Condor ] [ Build Basket ]|
+----------------------------------------------------------------------------------------------------------------------------------+
```

#### Key Functional Invariants:
1. **Underlying Selector & Favourites:**
   - Dropdown with instant auto-complete supporting Index underlyings (`NIFTY`, `BANKNIFTY`, `FINNIFTY`, `MIDCPNIFTY`, `SENSEX`) and high-liquidity stock underlyings (`RELIANCE`, `HDFCBANK`, `TCS`, `INFY`).
   - Single-click star toggle (`★`) persists user favourites via `POST /api/option-chain/favourites`.
2. **Expiry Selection:**
   - Populated dynamically via `GET /api/option-chain/expiries?underlying={symbol}`.
   - Categorized as Weekly (`W0`, `W1`, `W2`) and Monthly (`M0`, `M1`).
3. **Symmetrical Strike Matrix Window:**
   - Presets: `ATM ±5` (11 strikes), `ATM ±10` (21 strikes), `ATM ±15` (31 strikes), `ATM ±20` (41 strikes).
   - Dynamic calculation of ATM Strike: $K_{\text{ATM}} = \text{round}(\text{Spot} / \text{Step}) \times \text{Step}$ (e.g. NIFTY step $50$, BANKNIFTY step $100$).
4. **Moneyness Visual Shading:**
   - ITM Calls (Strikes $< \text{Spot}$): Shaded soft amber/gold background (`rgba(255, 193, 7, 0.08)`).
   - ITM Puts (Strikes $> \text{Spot}$): Shaded soft amber/gold background.
   - ATM Strike: Highlighted with high-contrast accent border and badge.
   - OTM Calls/Puts: Dark contrast neutral background.
5. **Open Interest (OI) & Volume In-Cell Bars:**
   - Horizontal CSS bar fills inside cells displaying relative open interest magnitude relative to the max OI on the chain.
   - Highest Call OI strike identified with Resistance marker (`[R]`); Highest Put OI strike identified with Support marker (`[S]`).
6. **Row Action Integrations:**
   - `[B]` (Buy): Launches Phase 11B Order Ticket pre-filled with contract parameters.
   - `[S]` (Sell): Launches Phase 11B Order Ticket pre-filled with `SELL`.
   - `[➕ Leg]`: Adds the specific contract as a leg to the active Basket Builder.
   - `[📌]` (Pin): Dispatches `POST /api/market-watch/watchlists/{id}/items` to pin the strike directly to the active watchlist.

---

### 2.2. Put-Call Ratio (PCR) & Max Pain Sentiment Widget

Anchored directly into the Option Chain Workbench header:

```
+-------------------------------------------------------------------------------------------------------+
| PUT-CALL RATIO & EXPIRY RISK ANALYTICS                                            [ Expiry: 28-NOV ]  |
+-------------------------------------------------------------------------------------------------------+
| PCR (Open Interest):   1.30 [ BULLISH SENTIMENT  ] (Total Put OI: 18,52,200 / Total Call OI: 14,25,400)|
| PCR (Volume):          1.15 [ MODERATE BULLISH   ] (Total Put Vol: 4,85,100 / Total Call Vol: 4,21,800)|
| Max Pain Strike:     24,500 [ Expiry Attraction  ] (Zero intrinsic loss level for option writers)      |
| Key Support Strike:  24,000 (Highest Put OI: 95,400 Lots)                                             |
| Key Resistance Strike:25,000 (Highest Call OI: 1,12,000 Lots)                                          |
+-------------------------------------------------------------------------------------------------------+
```

#### Analytical Formulas:
$$\text{PCR}_{\text{OI}} = \frac{\sum_{i} \text{Put Open Interest}_i}{\sum_{i} \text{Call Open Interest}_i}$$
$$\text{PCR}_{\text{Vol}} = \frac{\sum_{i} \text{Put Traded Volume}_i}{\sum_{i} \text{Call Traded Volume}_i}$$
$$\text{Sentiment Interpretation:} \quad \begin{cases} \text{BULLISH} & \text{if } \text{PCR}_{\text{OI}} > 1.20 \\ \text{NEUTRAL} & \text{if } 0.80 \le \text{PCR}_{\text{OI}} \le 1.20 \\ \text{BEARISH} & \text{if } \text{PCR}_{\text{OI}} < 0.80 \end{cases}$$

$$\text{Max Pain Strike } K^* = \arg\min_{K} \sum_{i} \left[ \text{Call OI}_i \times \max(0, K - K_i) + \text{Put OI}_i \times \max(0, K_i - K) \right]$$

---

### 2.3. Strategy Templates Scaffolding

Traders can deploy pre-built option structures with a single click. When clicked, the system auto-resolves strikes relative to the current spot price:

```
+-------------------------------------------------------------------------------------------------------+
| STRATEGY TEMPLATES PICKER                                                                             |
+-------------------------------------------------------------------------------------------------------+
|  [ 1. BULL CALL SPREAD ]     [ 2. BEAR PUT SPREAD ]      [ 3. LONG STRADDLE ]     [ 4. SHORT STRADDLE ]|
|  Buy ATM Call + Sell OTM Call  Buy ATM Put + Sell OTM Put  Buy ATM Call + Put       Sell ATM Call + Put |
|                                                                                                       |
|  [ 5. LONG STRANGLE ]        [ 6. SHORT STRANGLE ]       [ 7. IRON CONDOR ]       [ 8. IRON BUTTERFLY ]|
|  Buy OTM Call + Buy OTM Put    Sell OTM Call + Put         Buy Wings + Sell Body    Buy Wings + Sell ATM|
+-------------------------------------------------------------------------------------------------------+
```

#### Automated Strike Resolution Logic:
1. **Bull Call Spread (Debit):**
   - Leg 1: BUY $K_{\text{ATM}}$ Call ($1$ lot).
   - Leg 2: SELL $K_{\text{ATM}} + \text{Offset}$ Call ($1$ lot, e.g. $+100$ pts on NIFTY).
2. **Bear Put Spread (Debit):**
   - Leg 1: BUY $K_{\text{ATM}}$ Put ($1$ lot).
   - Leg 2: SELL $K_{\text{ATM}} - \text{Offset}$ Put ($1$ lot).
3. **Long Straddle:**
   - Leg 1: BUY $K_{\text{ATM}}$ Call ($1$ lot).
   - Leg 2: BUY $K_{\text{ATM}}$ Put ($1$ lot).
4. **Iron Condor (Defined Risk Credit Spread):**
   - Leg 1 (Put Wing): BUY $K_{\text{ATM}} - 2 \times \text{Offset}$ Put.
   - Leg 2 (Put Body): SELL $K_{\text{ATM}} - 1 \times \text{Offset}$ Put.
   - Leg 3 (Call Body): SELL $K_{\text{ATM}} + 1 \times \text{Offset}$ Call.
   - Leg 4 (Call Wing): BUY $K_{\text{ATM}} + 2 \times \text{Offset}$ Call.

---

### 2.4. Multi-Leg Strategy & Basket Builder UI (`#view-baskets`)

The Basket Builder serves as the primary composition and execution desk for multi-leg orders.

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

---

### 2.5. Leg Grid Editor Capabilities

1. **Reordering & Sequencing:**
   - Operators can drag rows or click `[▲]` / `[▼]` to change the internal index.
   - Legs assigned identical sequence numbers execute concurrently within that stage.
2. **Synchronized Lot Multiplier:**
   - Global multiplier stepper changes all leg quantities simultaneously in integer multiples of exchange lot size ($25, 50, 75 \dots$).
   - Custom lot ratios (e.g. Ratio Spreads $1:2$) can be configured by unlocking leg linkage.
3. **Price Type & Slippage Buffer:**
   - Supports `LIMIT` (with auto-calculated tick rounding to $0.05$) and `MARKET` with configurable Market Protection Buffer ($2.0\%$).
4. **Leg Modification & Removal:**
   - `[Mod]` opens quick popover to adjust strike or limit price.
   - `[✕]` deletes the leg and immediately re-evaluates strategy validity.

---

### 2.6. Dependency Visualization (Sequential DAG Execution)

Executing naked short options before long hedges incurs massive temporary margin requirements that can trigger RMS rejections. Phase 9 established sequential DAG execution:

$$\text{Stage 1: Long Legs (Hedges / Wings)} \xrightarrow{\text{All Confirmed}} \text{Stage 2: Short Legs (Body / Credit)}$$

The UI features a dynamic DAG component:
- Displays nodes for each stage.
- Green checkmarks (`✓`) light up as legs transition to `FILLED`.
- In case of failure in Stage 1, Stage 2 is automatically aborted.

---

### 2.7. Basket Pre-Flight Validation View

Clicking `[VALIDATE BASKET]` dispatches `POST /api/baskets/validate` without submitting wire orders. The modal or inline panel displays a rigorous pre-flight checklist:

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

---

### 2.8. Basket Execution Monitor & Real-Time FSM Progress

Upon clicking `[EXECUTE BASKET]`, the UI transitions into the live execution tracking state:

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

#### Execution Safety Controls:
1. **Idempotency Locking:** Button immediately disables with a spinner to prevent accidental double-clicks.
2. **Atomic Abort Kill-Switch:** `[🛑 ABORT REMAINING LEGS]` calls `POST /api/baskets/{id}/cancel` to halt subsequent stages if a leg stalls.
3. **Golden Rule Adherence:** If a leg status is unconfirmed, it displays `RECONCILING` and continues polling; it never assumes success.

---

## 3. Data Models & Front-End State Contracts

```typescript
// Strike Row in Option Chain Matrix
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

// Option Chain Matrix Response
interface OptionChainMatrixResponse {
  underlying: string;
  spot_price: number;
  spot_change: number;
  spot_change_pct: number;
  expiry_date: string;
  atm_strike: number;
  step_size: number;
  pcr_oi: number;
  pcr_volume: number;
  max_pain_strike: number;
  source_timestamp: string;
  retrieved_timestamp: string;
  strikes: OptionChainStrikeRow[];
}

// Basket Leg Model
interface BasketLeg {
  id: string; // client UUID
  instrument_token: string;
  trading_symbol: string;
  exchange_segment: string;
  side: 'BUY' | 'SELL';
  product_type: 'MIS' | 'NRML';
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

// Basket Order Model
interface BasketModel {
  client_basket_id: string;
  name: string;
  strategy_type: 'BULL_CALL_SPREAD' | 'BEAR_PUT_SPREAD' | 'STRADDLE' | 'STRANGLE' | 'IRON_CONDOR' | 'IRON_BUTTERFLY' | 'CUSTOM';
  underlying: string;
  expiry_date: string;
  legs: BasketLeg[];
  lot_multiplier: number;
  execution_mode: 'DISABLED' | 'PAPER' | 'LIVE';
  status: 'DRAFT' | 'VALIDATED' | 'EXECUTING' | 'COMPLETED' | 'FAILED' | 'ABORTED';
}

// Basket Validation Response
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
}
```

---

## 4. UI Layout, Split-Pane Ergonomics & Persistence

### 4.1. Dual-Pane Ergonomics
Phase 11D enables two intuitive layouts:
1. **Option Chain View (`#view-option-chain`):** Full-screen analytical view for comprehensive strike ladder analysis. Features a collapsible bottom drawer: `"Active Strategy Basket (n Legs)"` that slides up when strikes are added.
2. **Basket Workspace View (`#view-baskets`):** Dedicated multi-leg workbench with the Leg Grid Editor, DAG Sequencer, Validation Panel, and Risk Summary.
3. **Workspace Persistence:**
   - Active underlying selection persists via `WorkspaceManager.set('selected_underlying', symbol)`.
   - Active strike filter preset persists via `WorkspaceManager.set('strike_preset', 'ATM_10')`.
   - Draft basket state is cached in `localStorage` so in-progress spread designs survive browser reloads.

---

## 5. Keyboard Shortcuts & Workflow Accelerators

Institutional-grade speed requires extensive hotkey support:

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

## 6. Mobile & Tablet Responsive Adaptations

- **Option Chain Single-Side Toggle:** On viewports $< 1024\text{px}$, the symmetrical chain toggles between `[CALLS]` and `[PUTS]` with the Strike column fixed on the left/right, preventing horizontal crowding.
- **Sticky Basket Footer:** On mobile, the Basket drawer collapses into a floating pill: `[ 🧺 Iron Condor (4 Legs) - ₹58.4k Margin ▶ ]` which expands full-screen on tap.

---

## 7. Implementation Roadmap (Sub-Phase 11D Plan)

Following the proven modular sub-phase methodology, implementation will proceed through:

1. **HTML Component Templates:**
   - `templates/components/option_chain_view.html`: Full symmetrical strike matrix, underlying/expiry dropdowns, PCR widget.
   - `templates/components/basket_builder_view.html`: Leg grid editor, template buttons, DAG visualizer, risk card.
   - `templates/components/basket_drawer.html`: Slide-up docked drawer for Option Chain $\to$ Basket integration.
2. **Stylesheets (`static/css/baskets_option_chain.css`):**
   - High-contrast matrix grid, in-cell OI horizontal bar charts, ITM amber shading, DAG node pipeline.
3. **Front-End Controllers (`static/js/`):**
   - `option_chain.js`: Symmetrical matrix renderer, WebSocket touchline listener, PCR calculator, watchlist pin handler.
   - `basket_builder.js`: Leg grid state manager, template instantiator, validation runner, sequential execution monitor.
4. **Integration Testing (`tests/integration/test_basket_option_chain_ui_routes.py`):**
   - Verifying all template mounts, static assets, Option Chain $\to$ Basket data transfer, pre-flight validation, and paper basket execution.
5. **Phase 11D Architecture Review:**
   - Formal audit and sign-off document (`PHASE11D_ARCHITECTURE_REVIEW.md`).
