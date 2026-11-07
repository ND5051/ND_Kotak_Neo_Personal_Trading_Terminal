# Phase 11C Architectural Design Specification
## Portfolio & Order Book UI

**Document Version:** 1.0.0  
**Phase:** Phase 11C — Portfolio & Order Book UI  
**Target Milestone:** Sub-Milestone of M6 (Trading Terminal UI & Workbench Integration)  
**Baseline Dependencies:**
- Milestone M1–M5 Baselines Locked (`M1_BASELINE` through `M5_BASELINE`)
- Phase 10 Baseline Locked: Option Chain Workbench & Symmetrical Presets (commit `e163800`)
- Phase 11A Baseline Locked: Terminal Shell, Workspace Persistence & Dark Theme (commit `3e76b57`)
- Phase 11B Baseline Locked: Market Watch Grid & Order Ticket UI (commit `7d3a0c2`)
**Status:** Architectural Design (Pre-Implementation)  
**Implementation Constraint:** **Design specification only — Zero production implementation code generated in this phase**.

---

## Scope Exclusions (Strict Project Governance)

In strict adherence to the **PROJECT_CONSTITUTION** and terminal safety invariants:

- ❌ **No Autonomous Trading / Algorithmic Bots**: Every square-off, position exit, order modification, or cancellation is strictly initiated by explicit human operator action. Zero autonomous stop-loss triggers or automated bracket management exist in Phase 11C.
- ❌ **No Background Market Scanners**: Zero automated background scanners executing trades on P&L or drawdown triggers.
- ❌ **No Greeks / Volatility Analytics**: Calculation of portfolio Greeks (Delta, Gamma, Theta, Vega, Rho) and IV surfaces remains strictly excluded.
- ❌ **No Direct Wire Bypassing**: All position liquidations and order actions must route through the defensive execution pipeline:
  $$\text{Position Exit UI} \longrightarrow \text{Flask /api/orders/place} \longrightarrow \text{OrderExecutionService} \longrightarrow \text{ExecutionMode Gating} \longrightarrow \text{KotakOrderAdapter}$$
- ❌ **No Optimistic UI State Updates**: The UI never marks a position as `CLOSED` or an order as `CANCELLED` until verified by backend reconciliation and EventBus broadcast ("The Golden Rule").
- ❌ **No AI/ML Portfolio Recommendations**: No automated portfolio rebalancing, profit-taking prompts, or predictive allocation suggestions.

---

## 1. Executive Summary & Integration Architecture

Phase 11C designs the operational accounting and lifecycle-tracking core of the **Kotak Neo Personal Trading Terminal**:
1. **The Portfolio Suite:** A unified, real-time portfolio interface comprising **Holdings (CNC)** long-term equity monitoring, **Positions (MIS / NRML)** active intraday and F&O derivatives tracking, an interactive **Live MTM Dashboard**, modular **PnL Widgets**, and single-click / bulk **Position Exit Actions**.
2. **The Order Management Suite:** A complete order lifecycle audit terminal comprising a tabbed **Order Book** (`OPEN`, `EXECUTED`, `CANCELLED`, `REJECTED`, `RECONCILING`), an immutable **Trade Book**, an in-depth **Order History** ledger, a visual **Order Timeline View** mapping FSM state transitions with microsecond timestamps, and an **Expanded Funds Widget**.

```
+-------------------------------------------------------------------------------------------------------+
|                                    PHASE 11C INTEGRATION TOPOLOGY                                     |
|                                                                                                       |
|    [ SFeed WebSocket Stream ] (Phase 4)                [ Broker APIs / Kotak Neo Gateway ]             |
|                |                                                        |                             |
|                v Real-time Touchlines                                   v Order & Trade Feeds         |
|   +----------------------------+                       +----------------------------+                 |
|   |  Phase 6 Portfolio Service |                       |  Phase 7 & 8 Order Engine  |                 |
|   |   - HoldingsSummary        |                       |   - OrderModel / FSM       |                 |
|   |   - PositionsNet / Open    |                       |   - OrderEventModel        |                 |
|   |   - MarginSummary          |                       |   - TradeExecutionModel    |                 |
|   |   - Realized & MTM P&L     |                       |   - ExecutionMode Gating   |                 |
|   +----------------------------+                       +----------------------------+                 |
|                |                                                        |                             |
|                +---------------------------+----------------------------+                             |
|                                            |                                                          |
|                                            v                                                          |
|   +-----------------------------------------------------------------------------------------------+   |
|   |                              PHASE 11C USER INTERFACE SURFACE                                 |   |
|   |                                                                                               |   |
|   |  [ PORTFOLIO WORKSPACE ]                              [ ORDER MANAGEMENT WORKSPACE ]          |   |
|   |  1. Holdings Screen (CNC Long-term Equity)            3. Order Book (Open, Executed, Filters) |   |
|   |  2. Positions Screen (MIS/NRML Derivatives)           4. Trade Book (Audit-Grade Fills)       |   |
|   |  5. Live MTM Dashboard (Tick-by-tick P&L)             9. Order History (Ledger Search)        |   |
|   |  6. PnL Segment Widgets & Risk Warnings              10. Order Timeline (Visual FSM Flow)     |   |
|   |  7. Funds Widget Expansion (Span/Exp/Collateral)      8. Position Exit Actions & Bulk Exit    |   |
|   +-----------------------------------------------------------------------------------------------+   |
|                                            |                                                          |
|                                            v [Exit Action Bridge]                                     |
|                         +-------------------------------------+                                       |
|                         | Phase 11B Order Ticket Window       |                                       |
|                         | (Pre-filled reverse-side order)     |                                       |
|                         +-------------------------------------+                                       |
+-------------------------------------------------------------------------------------------------------+
```

---

## 2. Core Functional Specifications

### 2.1. Holdings Screen (CNC Long-Term Equity)
The Holdings screen provides an institutional view of all Cash & Carry (CNC) delivery equity shares held in the trader's Demat account.

```
+----------------------------------------------------------------------------------------------------------------------------------+
| HOLDINGS (CNC DEMAT)                                                         [ 🔄 Refresh (Phase 6) ] [ Filter: All Equities ▼ ] |
| Total Investment: ₹4,25,000.00 | Current Value: ₹4,58,420.50 | Overall P&L: +₹33,420.50 (+7.86%) | Day P&L: +₹4,820.50 (+1.06%)  |
+----------------------------------------------------------------------------------------------------------------------------------+
| Instrument         | Qty (Avail) | T1 (Unsettled) | Buy Avg (₹) | LTP (₹)   | Current Val (₹) | Total P&L (₹) | Day P&L (₹) | Actions|
|--------------------+-------------+----------------+-------------+-----------+-----------------+---------------+-------------+--------|
| RELIANCE EQ        |         100 |              0 |    2,850.00 |  2,945.00 |     2,94,500.00 | +9,500 (+3.3%)| +1,550 (+0.5| [Add][x|
| HDFCBANK EQ        |          50 |              0 |    1,620.00 |  1,680.20 |       84,010.00 | +3,010 (+3.7%)|   -215 (-0.2| [Add][x|
| INFOSYS EQ         |          30 |             10 |    1,750.00 |  1,825.00 |       73,000.00 | +3,000 (+4.3%)|   +660 (+0.9| [Add][x|
| TCS EQ             |           2 |              0 |    3,900.00 |  4,050.00 |        8,100.00 |   +300 (+3.8%)|    +40 (+0.5| [Add][x|
+----------------------------------------------------------------------------------------------------------------------------------+
| Total Items: 4 | Settled Qty: 182 | T1 Unsettled: 10 | Valuation Timestamp: 2026-11-07T10:45:00Z (SFeed Live)                    |
+----------------------------------------------------------------------------------------------------------------------------------+
```

#### Key Architectural Requirements:
1. **Data Source Integration:**
   - Consumes Phase 6 `GET /api/portfolio/holdings` returning list of `HoldingSummary`.
   - Separate accounting for settled Demat holdings (`quantity`) vs unsettled T1 shares (`t1_quantity`).
2. **Real-Time Touchline Updating:**
   - LTP updates via Phase 4 WebSocket or price cache (`PriceEngine.get_ltp(token, 'nse_cm')`).
   - Current Valuation $= (\text{Qty} + \text{T1}) \times \text{LTP}$.
   - Total P&L $= \text{Current Value} - \left( (\text{Qty} + \text{T1}) \times \text{Buy Avg} \right)$.
   - Directional tick animations (`.tick-up` green, `.tick-down` red) on LTP and Current Value cells.
3. **Action Triggers per Holding Row:**
   - `[Add]`: Launches Phase 11B Order Ticket pre-filled with `BUY`, `CNC`, and current scrip metadata.
   - `[Exit]`: Launches Phase 11B Order Ticket pre-filled with `SELL`, `CNC`, and exact available quantity ($\text{Qty} \le \text{Available Settled}$).

---

### 2.2. Positions Screen (Intraday MIS & Positional NRML)
The Positions screen tracks active derivative and intraday positions, calculating mark-to-market valuations in real time.

```
+----------------------------------------------------------------------------------------------------------------------------------+
| POSITIONS (DERIVATIVES & INTRADAY)             [ Sub-tabs: (●) ALL (4) | OPEN (3) | CLOSED (1) ]    [ Filter: MIS / NRML ▼ ]     |
| Realized P&L: +₹2,100.00 | Unrealized MTM: +₹3,275.00 | Net P&L: +₹5,375.00 | Exposure Margin: ₹1,45,200.00                      |
+----------------------------------------------------------------------------------------------------------------------------------+
| Product | Instrument             | Net Qty | Buy Avg | Sell Avg | LTP (₹)  | Realized (₹) | MTM P&L (₹) | Net P&L (₹) | Actions    |
|---------+------------------------+---------+---------+----------+----------+--------------+-------------+-------------+------------|
| NRML    | NIFTY 28NOV 24500 CE   |     +50 |  120.00 |     0.00 |   142.50 |         0.00 |  +1,125.00  |  +1,125.00  | [Add] [Exit|
| NRML    | NIFTY 28NOV 24700 CE   |     -50 |    0.00 |    45.00 |    38.00 |         0.00 |    +350.00  |    +350.00  | [Add] [Exit|
| MIS     | RELIANCE               |    +100 | 2930.00 |     0.00 |  2945.00 |         0.00 |  +1,500.00  |  +1,500.00  | [Add] [Exit|
| MIS     | BANKNIFTY 28NOV 52000PE|       0 |  180.00 |   210.00 |   195.00 |    +1,500.00 |        0.00 |  +1,500.00  | [ CLOSED ] |
+----------------------------------------------------------------------------------------------------------------------------------+
| Action Bar: [ ⚠️ SQUARE OFF ALL POSITIONS (Emergency) ]                                       Total Open: 3 Legs | Net Lots: 4   |
+----------------------------------------------------------------------------------------------------------------------------------+
```

#### Key Architectural Requirements:
1. **Data Source Integration:**
   - Consumes Phase 6 `GET /api/portfolio/positions` (supporting filters `?type=net&status=open`).
2. **Polymorphic Position Calculations:**
   - Long Position ($\text{Net Qty} > 0$): $\text{MTM} = \text{Net Qty} \times (\text{LTP} - \text{Buy Avg})$.
   - Short Position ($\text{Net Qty} < 0$): $\text{MTM} = |\text{Net Qty}| \times (\text{Sell Avg} - \text{LTP})$.
   - Closed Position ($\text{Net Qty} = 0$): $\text{MTM} = 0.00$; displays $\text{Realized P&L} = (\text{Sell Avg} - \text{Buy Avg}) \times \text{Traded Qty}$.
3. **The Golden Rule Handling:**
   - If a live tick is absent from the price engine, MTM P&L renders as `NONE` or `—` rather than calculating from stale or zero values.
4. **Position Quick Actions & Triggers:**
   - `[Add]`: Launches Order Ticket with same side and default 1 lot/quantity to scale or average into position.
   - `[Exit]`: Single-click liquidation launches Order Ticket pre-filled with opposite side:
     - Long $+50 \implies \text{Order Ticket pre-fills } \text{SELL}, \text{Qty}=50, \text{NRML}$.
     - Short $-50 \implies \text{Order Ticket pre-fills } \text{BUY}, \text{Qty}=50, \text{NRML}$.
   - `[Reverse]`: Position flipping workflow. Automatically generates an order with $2 \times |\text{Net Qty}|$ in the opposite direction (e.g. Long $+50 \implies \text{SELL } 100 \implies \text{New Net Qty } -50$). Launches Order Ticket with a prominent `"REVERSE POSITION"` warning badge.
5. **Portfolio Snapshot Timestamp & Header Refresh:**
   - Header prominently displays `"Last Refreshed: HH:mm:ss"` parsed from the backend `retrieved_timestamp`.
   - Incorporates a dedicated `[🔄 Refresh]` button dispatching `POST /api/portfolio/refresh` to force-sync holdings, positions, and margins with the broker.

---

### 2.3. Order Book (Active & Filtered Order Pipeline)
The Order Book provides a live audit trail of all orders placed during the trading day, reflecting the Phase 7/8 formal Finite State Machine (FSM).

```
+----------------------------------------------------------------------------------------------------------------------------------+
| ORDER BOOK                                                                                    [ 🔄 Refresh ] [ 🔍 Search Order ] |
| Filter Tabs: [ (●) ALL (8) ]  [ OPEN (2) ]  [ EXECUTED (4) ]  [ CANCELLED (1) ]  [ REJECTED (1) ]  [ RECONCILING (0) ]           |
+----------------------------------------------------------------------------------------------------------------------------------+
| Time     | Client Order ID  | Instrument         | Product | Type  | Side | Qty / Filled | Price (₹) | Status      | Actions    |
|----------+------------------+--------------------+---------+-------+------+--------------+-----------+-------------+------------|
| 10:42:15 | cli_ord_1107_001 | NIFTY28NOV24500CE  | NRML    | LIMIT | BUY  |    50 / 0    |    140.00 | OPEN        | [Mod] [Can]|
| 10:41:02 | cli_ord_1107_002 | BANKNIFTY 52000 PE | MIS     | LIMIT | SELL |    15 / 0    |    195.00 | OPEN        | [Mod] [Can]|
| 10:35:10 | cli_ord_1107_003 | RELIANCE           | CNC     | LIMIT | BUY  |   100 / 100  |   2930.00 | TRADED      | [Timeline] |
| 10:30:45 | cli_ord_1107_004 | NIFTY28NOV24700CE  | NRML    | LIMIT | SELL |    50 / 50   |     45.00 | TRADED      | [Timeline] |
| 10:15:20 | cli_ord_1107_005 | HDFCBANK           | MIS     | LIMIT | BUY  |    25 / 0    |   1650.00 | CANCELLED   | [Timeline] |
| 09:45:12 | cli_ord_1107_006 | INFY               | MIS     | LIMIT | BUY  |    50 / 0    |   1820.00 | REJECTED    | [Error]    |
+----------------------------------------------------------------------------------------------------------------------------------+
| Batch Control: [ CANCEL ALL OPEN ORDERS (2 Orders) ]                                           Execution Mode: [ PAPER MODE ]    |
+----------------------------------------------------------------------------------------------------------------------------------+
```

#### Key Architectural Requirements:
1. **FSM State Color Semantics:**
   - `OPEN` / `PENDING`: Blue badge (`#1b73e8`).
   - `TRADED` / `FILLED`: Green badge (`#00d09c`).
   - `CANCELLED`: Neutral gray badge (`#8b949e`).
   - `REJECTED`: Crimson badge (`#eb5757`).
   - `RECONCILING`: Warning Amber pulsing badge (`#f2994a`).
2. **Order Modification & Cancellation Hooks:**
   - `[Mod]` (Modify): Opens Order Ticket in edit mode, allowing modification of price and quantity, dispatching `PUT /api/orders/{client_order_id}/modify`.
   - `[Can]` (Cancel): Prompts confirmation and dispatches `DELETE /api/orders/{client_order_id}/cancel`.
3. **Emergency Batch Action:**
   - `[CANCEL ALL OPEN ORDERS]`: Dispatches `POST /api/orders/cancel-all`.

---

### 2.4. Trade Book (Audit-Grade Executed Fills)
The Trade Book provides an immutable, chronological register of all filled trades, complying with exchange execution audit trail requirements.

```
+----------------------------------------------------------------------------------------------------------------------------------+
| TRADE BOOK (COMPLETED FILLS)                                                   [ Total Trades: 4 | Total Turnover: ₹4,18,750.00 ]|
+----------------------------------------------------------------------------------------------------------------------------------+
| Trade Time (IST)        | Trade ID   | Order ID         | Symbol            | Segment | Side | Qty | Fill Price (₹) | Value (₹)    |
|-------------------------+------------+------------------+-------------------+---------+------+-----+----------------+--------------|
| 2026-11-07 10:35:10.142 | TRD_982145 | cli_ord_1107_003 | RELIANCE          | NSE_CM  | BUY  | 100 |       2,930.00 |  2,93,000.00 |
| 2026-11-07 10:30:45.891 | TRD_982144 | cli_ord_1107_004 | NIFTY28NOV24700CE | NSE_FO  | SELL |  50 |          45.00 |    56,250.00 |
| 2026-11-07 10:12:18.234 | TRD_982143 | cli_ord_1107_007 | NIFTY28NOV24500CE | NSE_FO  | BUY  |  50 |         120.00 |    60,000.00 |
| 2026-11-07 09:55:04.551 | TRD_982142 | cli_ord_1107_008 | BANKNIFTY 52000PE | NSE_FO  | BUY  |  15 |         180.00 |     9,500.00 |
+----------------------------------------------------------------------------------------------------------------------------------+
```

#### Key Architectural Requirements:
1. **Data Source Integration:**
   - Consumes Phase 8 `GET /api/orders/trades` returning `TradeExecutionModel` entities.
2. **Sub-Second Precision:**
   - Timestamps formatted with millisecond precision (`YYYY-MM-DD HH:mm:ss.SSS`).
3. **Turnover Metrics:**
   - Computes aggregate turnover: $\sum (\text{Qty}_i \times \text{Fill Price}_i)$.

---

### 2.5. Live MTM Dashboard
The Live MTM Dashboard provides an institutional summary bar anchored across the primary portfolio views.

```
+----------------------------------------------------------------------------------------------------------------------------------+
| LIVE PORTFOLIO MTM DASHBOARD                                                [ Auto-Refresh: 1s ] [ Mode: PAPER ] [ Risk: HEALTHY]|
+----------------------------------------------------------------------------------------------------------------------------------+
| Total P&L              | Day MTM P&L            | Realized P&L           | Unrealized P&L         | Portfolio Valuation          |
| +₹38,795.50 (+8.47%)   | +₹4,820.50 (+1.06%)    | +₹2,100.00             | +₹2,720.50             | ₹4,58,420.50                 |
| [====================] | [====================] | Closed Day Fills       | 3 Open Derivative Legs | Cash + Holdings + MTM        |
+----------------------------------------------------------------------------------------------------------------------------------+
```

#### Mathematical Formulas:
$$\text{Unrealized MTM} = \sum_{i \in \text{Open Positions}} \left( \text{Net Qty}_i \times (\text{LTP}_i - \text{Avg Price}_i) \right)$$
$$\text{Realized P&L} = \sum_{j \in \text{Closed Trades}} \left( (\text{Sell Price}_j - \text{Buy Price}_j) \times \text{Qty}_j \right)$$
$$\text{Day Total P&L} = \text{Realized P&L} + \text{Unrealized MTM}$$
$$\text{Total Portfolio Value} = \text{Available Cash} + \text{Collateral Value} + \text{CNC Holdings Value} + \text{Unrealized MTM}$$

---

### 2.6. PnL Widgets & Drawdown Risk Alerts
To protect traders from emotional decision-making during severe market drawdowns, the interface incorporates automated visual risk indicators.

```
+----------------------------------------------------------------------------------------------------------------------------------+
| ⚠️ DRAWDOWN RISK ALERT: Intraday Loss exceeds -₹15,000.00 (75% of Daily Drawdown Limit: -₹20,000.00)                             |
| Current Day MTM: -₹16,420.00 | Suggestion: Review open derivative legs or reduce gross exposure.                                  |
+----------------------------------------------------------------------------------------------------------------------------------+
```

#### Functional Invariants:
1. **Drawdown Threshold Tiers:**
   - Normal ($> -₹10,000$): Standard theme.
   - Caution ($-₹10,000$ to $-₹19,999$): Amber banner atop Portfolio tab.
   - Limit Hit ($\le -₹20,000$): Crimson banner; locks out new position-increasing orders via Phase 8 `OrderRiskService`.
2. **Segment P&L Breakdown Cards:**
   - Separate mini-cards showing Equity Cash P&L vs F&O Derivative P&L.

---

### 2.7. Funds Widget Expansion
The Funds screen provides an exhaustive, multi-tier accounting ledger expanding beyond the compact widget delivered in Phase 11A.

```
+----------------------------------------------------------------------------------------------------------------------------------+
| FUNDS & COLLATERAL ACCOUNT LEDGER                                          [ 🔄 Refresh Balances ] [ 💳 Add Funds ] [ 🏧 Withdraw]|
+----------------------------------------------------------------------------------------------------------------------------------+
| 1. TRADING CAPITAL BREAKDOWN                               | 2. MARGIN UTILIZATION BREAKDOWN                                     |
|    Available Realized Cash:        ₹2,45,000.00            |    Span Margin Used (F&O):              ₹95,200.00               |
|    Collateral from Pledged Shares: ₹1,80,000.00            |    Exposure Margin Used:                ₹42,000.00               |
|    Unrealized Intraday MTM Credit:    +₹3,275.00            |    Option Premium Blocked:               ₹8,000.00               |
|    Total Margin Available:         ₹4,28,275.00            |    Total Margin Used:                  ₹1,45,200.00               |
+------------------------------------------------------------+---------------------------------------------------------------------+
| 3. MARGIN UTILIZATION PROGRESS:                                                                                                  |
|    [========================|===================================================] 33.9% Utilized (₹1,45,200 / ₹4,28,275)          |
|    Status: SAFE CAPITAL BUFFER (Thresholds: 70% Caution, 85% Hard Limit)                                                         |
+----------------------------------------------------------------------------------------------------------------------------------+
| 4. RISK SNAPSHOT METRICS:                                                                                                        |
|    Peak Margin Today:              ₹1,62,000.00            | Broker Entity:                  Kotak Securities Ltd             |
|    Ad-hoc Margin:                         ₹0.00            | Segment Coverage:               NSE_CM, BSE_CM, NSE_FO           |
|    Balance Timestamp:       2026-11-07T10:45:00Z            | Upstream Status:                RECONCILED                       |
+----------------------------------------------------------------------------------------------------------------------------------+
```

---

### 2.8. Position Exit Actions & Emergency Square Off All

#### 2.8.1. Single Position Exit, Safety Threshold & Reverse Workflows:
1. **Single Exit Workflow & Position Exit Safety Threshold:**
   - Operator clicks `[Exit]` on an active row in the Positions table.
   - **Position Exit Safety Threshold Enforcement:**
     - Computes nominal position gross exposure:
       $$\text{Position Exposure} = |\text{Net Qty}| \times \max(\text{LTP}, \text{Buy Avg}, \text{Sell Avg})$$
     - If $\text{Position Exposure} > ₹1,00,000$:
       - System intercepts the exit action and presents a dedicated **High-Exposure Exit Confirmation Modal**:
         *"⚠️ HIGH EXPOSURE WARNING: Position exposure of ₹X exceeds safety threshold of ₹1,00,000.00. Are you sure you want to proceed with exit?"*
       - Displays exact liquidation side, quantity, current mark, and estimated turnover.
       - Operator must explicitly click `[Proceed with Exit]` before the Order Ticket is hydrated and displayed.
     - If $\text{Position Exposure} \le ₹1,00,000$:
       - Directly launches Order Ticket pre-filled with exit parameters.
   - Generates an exit payload:
     - Opposite side: If $\text{Net Qty} > 0 \implies \text{SELL}$; if $\text{Net Qty} < 0 \implies \text{BUY}$.
     - Exact net open quantity: $\text{Qty} = |\text{Net Qty}|$.
     - Same product type (`MIS` or `NRML`).
     - Order type initialized to `LIMIT` pre-filled with current Best Bid (for exit sell) or Best Ask (for exit buy).
   - Phase 11B Order Ticket opens with badge: `[EXIT POSITION: SYMBOL]`.

2. **Position Reverse Workflow:**
   - Operator clicks `[Reverse]` on an active open position.
   - Calculates reversal size: $\text{Reverse Qty} = 2 \times |\text{Net Qty}|$.
   - Direction: Opposite to current net exposure (e.g. Long $+50 \implies \text{SELL } 100$).
   - Launches Order Ticket pre-filled with reverse parameters and prompts modal confirmation:
     *"Are you sure you want to REVERSE position from LONG (+50) to SHORT (-50)?"*
   - Pre-flight margin preview verifies sufficiency for the new position.

#### 2.8.2. Emergency "Square Off All Positions" Workflow:

```
+--------------------------------------------------------------------+
| ⚠️ EMERGENCY: SQUARE OFF ALL OPEN POSITIONS               [ Esc ]  |
+--------------------------------------------------------------------+
| Are you sure you want to close ALL 3 active positions?             |
| This will immediately dispatch MARKET exit orders:                 |
|                                                                    |
|   1. SELL  50 Qty  NIFTY 28NOV 24500 CE   (NRML)                   |
|   2. BUY   50 Qty  NIFTY 28NOV 24700 CE   (NRML)                   |
|   3. SELL 100 Qty  RELIANCE               (MIS)                    |
|                                                                    |
| Estimated Market Slippage: ~0.5% - 1.2%                            |
| Execution Mode: [ PAPER MODE ]                                     |
+--------------------------------------------------------------------+
| In LIVE mode, type CONFIRM_EXIT_ALL: [                       ]     |
+--------------------------------------------------------------------+
| [ CANCEL (Esc) ]                  [ EXECUTE SQUARE OFF ALL ORDERS ]|
+--------------------------------------------------------------------+
```

- Requires operator confirmation. If `ExecutionMode = LIVE`, requires typing `CONFIRM_EXIT_ALL`.
- Dispatches sequential or parallel exit orders through Phase 8 `OrderExecutionService`.

---

### 2.9. Order History & Search Ledger
The Order History screen provides historical querying of past and completed orders beyond the active day's buffer.
- Date range picker (Today, Yesterday, Past 7 Days, Custom Range).
- Search filter by Trading Symbol, Client Order ID, or Exchange Order ID.
- Expanding row reveals the raw broker exchange confirmation payload and regulatory timestamps.

---

### 2.10. Order Timeline View (Visual FSM Progression)
Clicking `[Timeline]` on any order opens an interactive modal visualizing the Phase 7/8 formal state transitions.

```
+-------------------------------------------------------------------------------------------------------+
| ORDER EXECUTION TIMELINE: cli_ord_1107_003 (RELIANCE 100 Qty @ ₹2,930.00)                    [ Close ]|
+-------------------------------------------------------------------------------------------------------+
|                                                                                                       |
|    [ (1) DRAFT ] ───> [ (2) VALIDATED ] ───> [ (3) SUBMITTED ] ───> [ (4) PENDING ] ───> [ (5) TRADED]|
|       10:35:08.100        10:35:08.125          10:35:08.150          10:35:08.210        10:35:10.142|
|                                                                                                       |
+-------------------------------------------------------------------------------------------------------+
| DETAILED TRANSITION AUDIT LOG:                                                                        |
|                                                                                                       |
| 1. [10:35:08.100] DRAFT created via Order Ticket UI. Idempotency Key generated.                       |
| 2. [10:35:08.125] VALIDATED: NSE tick size (0.05), lot size (1), and margin checked (Risk passed).    |
| 3. [10:35:08.150] SUBMITTED: Wire dispatch initiated via KotakOrderAdapter (Mode: PAPER).             |
| 4. [10:35:08.210] PENDING: Exchange acknowledged. Broker Order ID: PAPER_1107103508.                  |
| 5. [10:35:10.142] TRADED: Full fill confirmed (100 / 100 Qty @ ₹2,930.00). Broker Trade ID: TRD_98214|
+-------------------------------------------------------------------------------------------------------+
```

#### FSM Exception Paths Visualized:
- **Reconciliation Path:** `PENDING` $\longrightarrow$ `RECONCILING` $\longrightarrow$ `TRADED` (Amber pulse indicating Golden Rule poller active).
- **Rejection Path:** `SUBMITTED` $\longrightarrow$ `REJECTED` (Red node with specific RMS failure code).
- **Cancellation Path:** `PENDING` $\longrightarrow$ `CANCELLED` (Neutral gray node with cancellation timestamp).

---

## 3. Data Models & Front-End State Contracts

```typescript
// Holdings State Contract
interface HoldingItem {
  instrument_token: string;
  exchange_segment: string;
  trading_symbol: string;
  quantity: number;
  t1_quantity: number;
  average_price: number;
  last_price: number;
  close_price: number;
  pnl: number;
  pnl_percent: number;
  day_pnl: number;
}

// Positions State Contract
interface PositionItem {
  instrument_token: string;
  exchange_segment: string;
  trading_symbol: string;
  product_type: 'MIS' | 'NRML';
  net_quantity: number;
  buy_quantity: number;
  buy_average: number;
  sell_quantity: number;
  sell_average: number;
  last_price: number;
  realized_pnl: number;
  unrealized_pnl: number;
  net_pnl: number;
  status: 'OPEN' | 'CLOSED';
}

// Order State Contract
interface OrderBookItem {
  client_order_id: string;
  broker_order_id: string | null;
  trading_symbol: string;
  exchange_segment: string;
  order_side: 'BUY' | 'SELL';
  order_type: 'LIMIT' | 'MARKET' | 'SL' | 'SL-M';
  product_type: 'MIS' | 'NRML' | 'CNC';
  quantity: number;
  filled_quantity: number;
  price: number;
  trigger_price: number;
  status: 'DRAFT' | 'VALIDATED' | 'SUBMITTED' | 'PENDING' | 'TRADED' | 'REJECTED' | 'CANCELLED' | 'RECONCILING';
  created_at: string;
}

// Order Timeline Event Contract
interface OrderTimelineEvent {
  from_status: string;
  to_status: string;
  reason: string;
  timestamp: string;
}
```

---

## 4. Keyboard Shortcuts & Ergonomics

| Shortcut | Scope | Action |
|:---|:---|:---|
| `3` | Global Terminal | Switch to **Holdings** Tab |
| `4` | Global Terminal | Switch to **Positions** Tab |
| `2` | Global Terminal | Switch to **Orders** Tab |
| `7` | Global Terminal | Switch to **Funds** Tab |
| `R` | Portfolio / Orders | Trigger manual refresh of active tab |
| `X` | Focused Position Row | Trigger **Position Exit** workflow |
| `T` | Focused Order Row | Open **Order Timeline** view |
| `Shift + Esc` | Global Terminal | Open **Emergency Cancel All Orders** modal |
| `Esc` | Modal / Drawer | Dismiss Timeline modal or Square Off confirmation |

---

## 5. Responsive Mobile & Tablet Adaptations

1. **Table Horizontal Scrolling:** Table wrappers implement `overflow-x: auto` with sticky first columns (Symbol & Side) on viewports $< 1024\text{px}$.
2. **Mobile Position Cards:** On screens $< 768\text{px}$, tabular rows collapse into high-density card layouts featuring prominent Net Quantity, LTP, and Net P&L.
3. **Swipe-to-Exit Gesture:** Mobile touch gesture on a position card reveals a red `[Exit]` action drawer.

---

## 6. Test & Verification Strategy for Phase 11C

Phase 11C implementation will be validated through dedicated unit and integration tests:

1. **Holdings UI Tests (`test_holdings_ui.py`):**
   - Verify calculation of Current Value and P&L from mock touchline ticks.
   - Verify settled vs T1 quantity segregation.
   - Verify `[Exit]` triggers Order Ticket in `SELL` mode with exact quantity.
2. **Positions UI Tests (`test_positions_ui.py`):**
   - Verify polymorphic MTM calculations for Long, Short, and Closed positions.
   - Verify Golden Rule handling (`NONE` on absent quotes).
   - Verify single exit and emergency `Square Off All` modal challenge logic.
3. **Order Book & FSM Tests (`test_order_book_ui.py`):**
   - Verify filter tab switching (`ALL`, `OPEN`, `EXECUTED`, `CANCELLED`, `RECONCILING`).
   - Verify Order modification (`PUT /modify`) and cancellation (`DELETE /cancel`).
   - Verify batch `Cancel All` API dispatch.
4. **Order Timeline Tests (`test_order_timeline_ui.py`):**
   - Verify sequential state transition rendering (`DRAFT` $\to$ `VALIDATED` $\to$ `PENDING` $\to$ `TRADED`).
   - Verify error details display on rejected orders.
5. **Full Regression Guarantee:**
   - 100% pass across all 200 existing tests with zero regressions.

---

## 7. Deliverables Summary

Upon approval of this specification, implementation of Phase 11C will deliver:
1. `templates/components/holdings_view.html`: CNC equity holdings table, summary metrics strip, and exit actions.
2. `templates/components/positions_view.html`: Live MTM positions grid, filter tabs, and emergency square-off modal.
3. `templates/components/order_book_view.html`: Tabbed order book, modification/cancellation controls, and batch cancel.
4. `templates/components/trade_book_view.html`: Chronological executed trade register with sub-second timestamps.
5. `templates/components/order_timeline_modal.html`: Visual FSM state transition modal with detailed audit log.
6. `templates/components/funds_expanded_view.html`: Comprehensive margin account ledger and collateral breakdown.
7. `static/css/portfolio.css`: Dedicated styling for tables, P&L badges, timeline nodes, and risk banners.
8. `static/js/portfolio.js`: Holdings and positions controllers, live MTM formulas, and square-off logic.
9. `static/js/order_book.js`: Order filtering, modification/cancellation handlers, and timeline visualization.
10. `tests/integration/test_portfolio_order_book_ui_routes.py`: Comprehensive test suite verifying all Phase 11C components.
11. `PHASE11C_ARCHITECTURE_REVIEW.md`: Post-implementation architectural audit.

