# Phase 10 Architectural Design Specification
## Option Chain Workbench Foundation

**Document Version:** 1.0.0  
**Phase:** Phase 10 — Option Chain Workbench Foundation  
**Target Milestone:** Milestone M6 (Option Chain Workbench Baseline)  
**Baseline Dependencies:**
- Milestone M1 Baseline Locked (`M1_BASELINE`, commit `4d9341a`)
- Milestone M2 Baseline Locked (`M2_BASELINE`, commit `c4d30e6`): SFeed WebSocket Supervisor, Market Watch & Portfolio MTM
- Milestone M3 Baseline Locked (`M3_BASELINE`, commit `22dd3c8`): Order Domain Foundation, FSM & Risk Engine
- Milestone M4 Baseline Locked (`M4_BASELINE`, commit `2362ba8`): Order Execution Foundation, ExecutionMode & Audited Paper Engine
- Milestone M5 Baseline Locked (`M5_BASELINE`, commit `fcfb088`): Advanced Multi-Leg Baskets, Strategy Validation & Exposure Service
**Status:** Architectural Design (Pre-Implementation)  
**Implementation Constraint:** **Design specification only — Zero production implementation code generated in this phase**.

---

## Scope Exclusions (Strict Project Governance)

In strict compliance with the **PROJECT_CONSTITUTION** and project architectural mandates, the following features are **explicitly prohibited** from Phase 10:

- ❌ **No Greeks Engine**: Calculation of Black-Scholes Greeks (Delta, Gamma, Theta, Vega, Rho) is deferred to future dedicated analytics phases.
- ❌ **No Volatility Analytics**: Implied Volatility (IV), IV Rank, IV Percentile, volatility smiles, and skew surfaces are strictly excluded from Phase 10.
- ❌ **No Delta Hedging**: Zero automated delta-neutral rebalancing or dynamic Greek-based positioning.
- ❌ **No Auto Trading / Autonomous Bots**: Zero automated trade dispatchers, algorithmic triggers, auto-entries, or unprompted square-offs. All user interactions remain strictly human-driven.
- ❌ **No Scanner Engine**: No automated continuous background market scanners or multi-contract alert triggers.
- ❌ **No Direct Wire Bypassing**: The Option Chain Workbench displays market data and constructs order structures. It never dispatches wire orders directly; all execution must route through Phase 9 Basket Builder $\to$ Phase 8 `OrderExecutionService` $\to$ `KotakOrderAdapter`.
- ❌ **No AI/ML Predictions**: Zero machine-learning forecast overlays or predictive direction indicators.

> [!IMPORTANT]
> **Core Architectural Objective of Phase 10:**  
> Phase 10 provides an interactive, institutional-grade **Option Chain Workbench** for visual analysis and multi-leg order construction. It presents real-time strike matrices centered on the underlying spot price, Open Interest (OI) distribution, volume metrics, Put-Call Ratio (PCR), and automated ATM/ITM/OTM classification. Crucially, it serves as the visual launchpad for the **Phase 9 Basket Builder** (enabling one-click strategy creation) and **Phase 5 Watchlist Integration** (enabling one-click strike tracking), driven by real-time SFeed streaming feeds.

---

## 1. Executive Summary & Architectural Invariants

In Indian derivatives markets (NSE / BSE), options traders do not view option contracts in isolation. They evaluate option chains structured symmetrically as a ladder of strikes around the underlying spot price, inspecting Call and Put metrics in parallel.

Milestone M5 successfully established the backend multi-leg basket architecture, structural strategy validation engine, and financial exposure state monitoring. However, manually typing trading symbols like `NIFTY26NOV24500CE` into order dialogs is error-prone, slow, and unsuitable for fast-moving markets.

Phase 10 designs the **Option Chain Workbench**, bridging market data streams to strategy execution:

```
========================================================================================================
                                     PHASE 10 WORKBENCH ARCHITECTURE
========================================================================================================

    [ REAL-TIME TOUCHLINE FEED ]                  [ BROKER DATA APIS ]
       (Phase 4 SFeed Stream)                   (Kotak Neo SDK v3 / Scrip Master)
                 |                                               |
                 | Spot LTP & Strike Touchlines                  | Expiries, Token Chains
                 v                                               v
+------------------------------------------------------------------------------------------------------+
| 1. OPTION CHAIN AGGREGATOR & DATA PIPELINE (`OptionChainService`)                                    |
|    - Dynamic Underlying & Spot Price Resolution (Index: Nifty 50, Sensex; Equities: Reliance, etc.)   |
|    - Expiry Calendar Management: Weekly (W0, W1) & Monthly (M0, M1) Classification                   |
|    - Local Instrument Cache (5s TTL during market hours; avoids broker rate-limit throttling)         |
+------------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+------------------------------------------------------------------------------------------------------+
| 2. STRIKE MATRIX & DERIVED METRICS ENGINE (`StrikeMatrixEngine`)                                     |
|    - Dynamic Strike Step & ATM Determination: K_ATM = round(Spot / Step) * Step                     |
|    - Symmetrical Matrix Generation: Configurable Window (e.g. +/- 10, 15, 20 Strikes around ATM)     |
|    - Open Interest (OI) & Volume Ingestion: Absolute OI, Change in OI (dOI), Traded Volume          |
|    - PCR Engine: Aggregate Expiry PCR and Strike-Specific PCR                                        |
|    - Intrinsic Value & Moneyness Tagging: ITM / ATM / OTM Visual Shading Boundaries                  |
|    - Max Pain & Key Support / Resistance Strike Identification                                        |
+------------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+------------------------------------------------------------------------------------------------------+
| 3. WORKBENCH REST CONTROLLER (`/api/option-chain`)                                                   |
|    - GET /underlyings  -> F&O Universe with Spot LTP & Step Configuration                            |
|    - GET /expiries     -> Sorted Expiry Dates for Underlying                                         |
|    - GET /             -> Symmetrical Matrix with Calls & Puts, Metrics & Moneyness Tags              |
|    - GET /pcr          -> Granular & Aggregate Put-Call Ratios                                       |
+------------------------------------------------------------------------------------------------------+
                         |                                               |
                         | One-Click Strategy Build                      | One-Click Track
                         v                                               v
+------------------------------------------------+       +---------------------------------------------+
| 4. PHASE 9 BASKET BUILDER INTEGRATION          |       | 5. PHASE 5 WATCHLIST INTEGRATION            |
|    - Click Strike Bid/Ask -> Add Leg to Basket |       |    - Click Bookmark -> Add to Watchlist     |
|    - One-Click Template Shortcuts:             |       |    - Interacts with `WatchlistService`      |
|      * Bull Call Spread / Bear Put Spread      |       |    - Subscribes via SFeed Stream            |
|      * Long / Short Straddle & Strangle        |       +---------------------------------------------+
|      * Iron Condor / Iron Butterfly            |
|    - Emits Phase 9 Compliant `Basket` Payload  |
|    - Triggers Pre-Trade Risk Clearance         |
+------------------------------------------------+
========================================================================================================
```

---

## 2. Underlying Selection Architecture

### 2.1. Supported Underlying Universe
Phase 10 standardizes underlying instrument selection across two primary asset classes traded in Indian derivatives:

1. **Benchmark Indices (Index Derivatives):**
   - `NIFTY` (NSE Nifty 50): Spot Token `nse_cm|Nifty 50` (or `26000`), Default Strike Step $\Delta K = 50$, Lot Size = 25.
   - `BANKNIFTY` (NSE Nifty Bank): Spot Token `nse_cm|Nifty Bank` (or `26001`), Default Strike Step $\Delta K = 100$, Lot Size = 15.
   - `FINNIFTY` (NSE Nifty Financial Services): Spot Token `nse_cm|Nifty Fin Service`, Default Strike Step $\Delta K = 50$, Lot Size = 25.
   - `MIDCPNIFTY` (NSE Nifty Midcap Select): Spot Token `nse_cm|NIFTY MID SELECT`, Default Strike Step $\Delta K = 25$, Lot Size = 50.
   - `SENSEX` (BSE Sensex 30): Spot Token `bse_cm|SENSEX` (or `1`), Default Strike Step $\Delta K = 100$, Lot Size = 10.

2. **Liquid Equity Derivatives (Stock Options):**
   - High-liquidity F&O constituents (e.g., `RELIANCE`, `TCS`, `INFY`, `HDFCBANK`, `ICICIBANK`, `SBIN`, `TATAMOTORS`).
   - Dynamic step and lot size resolution derived from the Scrip Master master file.

### 2.2. Underlying Domain Specification
```python
@dataclass(frozen=True)
class UnderlyingSpecification:
    symbol: str                               # e.g., "NIFTY", "BANKNIFTY", "RELIANCE"
    display_name: str                         # e.g., "Nifty 50 Index", "Reliance Industries"
    exchange_segment: str                     # "nse_cm" (Spot Underlying)
    derivatives_segment: str                  # "nse_fo" or "bse_fo" (Options Contracts)
    spot_instrument_token: str                # Token used to query Spot LTP (e.g. "26000")
    spot_index_name: Optional[str]            # Exact SFeed index string (e.g. "Nifty 50")
    strike_step: float                        # Minimum strike interval (e.g. 50.0, 100.0)
    lot_size: int                             # Exchange lot size (e.g. 25, 15)
    tick_size: float = 0.05                   # Exchange tick size (₹0.05)
```

### 2.3. Spot Price Ingestion Pipeline
To classify strikes into In-The-Money (ITM) or Out-Of-The-Money (OTM) and locate the At-The-Money (ATM) anchor in real time:
1. The service queries the Phase 5 [`PriceEngine`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/market_watch/services/price_engine.py) for the spot instrument token or index name.
2. If real-time stream is active, use the SFeed `SFeedIndex` or `SFeedScrip` Touchline LTP.
3. If stream is disconnected or uninitialized, fall back to broker REST snapshot (`client.search_scrip`).
4. **Safety Rule:** If spot price cannot be obtained, return an explicit error state (`SPOT_PRICE_UNAVAILABLE`) rather than guessing or computing with a stale default of 0.0.

---

## 3. Expiry Selection Architecture

### 3.1. Contract Expiry Pipeline
Contract expiries in Indian derivatives follow standardized weekly (Thursdays/Wednesdays) and monthly cycles (last Thursday of the month).

The `OptionChainService` retrieves and normalizes expiries via:
1. **Primary Source:** Upstream broker API: `client.expiries(exchange_segment="nse_fo", symbol="NIFTY")`.
2. **Fallback Source:** Local Scrip Master database query extracting distinct expiry values for the requested underlying symbol.
3. **Normalization:** All expiry dates are parsed and formatted as ISO-8601 strings: `YYYY-MM-DD`.

### 3.2. Expiry Categorization Model
The service sorts all active expiries chronologically and tags them for UI consumption:

```python
@dataclass
class ExpiryInfo:
    expiry_date: str                          # ISO-8601: "2026-11-26"
    display_label: str                        # "26-Nov-2026 (Monthly)"
    days_to_expiry: int                       # DTE (Calendar days remaining)
    is_current_weekly: bool                   # True for the nearest upcoming expiry
    is_monthly: bool                          # True for the last expiry of the calendar month
    trading_symbol_token: str                 # Expiry representation in symbol (e.g. "26NOV")
```

### 3.3. DTE (Days to Expiry) Calculation
$$DTE = \max\left(0, \;\lceil (\text{expiry\_datetime} - \text{current\_datetime}).\text{total\_seconds}() / 86400 \rceil\right)$$
Where market expiry cutoff is standardized to `15:30:00 IST` (UTC `10:00:00`).

---

## 4. Strike Matrix Design & Data Model

### 4.1. Symmetrical Strike Ladder Generation
A standard option chain displays an equal number of strikes above and below the At-The-Money strike:
* Operator selects a Strike Window $N$ (Default: 15; Supported: 10, 15, 20, 25, 30).
* The engine resolves the ATM strike $K_{ATM}$.
* The engine projects $N$ lower strikes ($K_{ATM} - i \cdot \Delta K$) and $N$ higher strikes ($K_{ATM} + i \cdot \Delta K$) for $i \in [1, N]$.
* Total strikes displayed: $2N + 1$.

```
                      +-------------------+
                      | Spot: 24,512.40   |
                      | K_ATM: 24,500.00  |
                      +-------------------+
                                |
        CALLS (CE)              |              PUTS (PE)
--------------------------------+--------------------------------
LTP   OI    Vol   Moneyness  Strike  Moneyness   LTP   OI    Vol
-----------------------------------------------------------------
210  1.2M   450k    ITM     24,350     OTM       35   2.1M  380k
145  2.5M   890k    ITM     24,400     OTM       52   3.4M  620k
 95  4.1M  1.4M     ITM     24,450     OTM       78   4.8M  910k
-----------------------------------------------------------------
 58  8.2M  2.9M     ATM  [ 24,500 ]    ATM      115   7.9M  2.6M  <-- ATM STRIKE
-----------------------------------------------------------------
 32  5.6M  1.8M     OTM     24,550     ITM      162   3.1M  780k
 18  3.8M  1.1M     OTM     24,600     ITM      220   1.8M  420k
  9  2.1M   610k    OTM     24,650     ITM      295   980k  210k
```

### 4.2. Core Domain Data Models

#### 1. `OptionContractQuote`
Encapsulates real-time touchline, liquidity, and volume metrics for a single option contract (Call or Put):
```python
@dataclass
class OptionContractQuote:
    instrument_token: str                     # Broker instrument token (e.g. "45210")
    trading_symbol: str                       # e.g., "NIFTY26NOV24500CE"
    option_type: str                          # "CE" or "PE"
    strike_price: float                       # 24500.0
    expiry_date: str                          # "2026-11-26"
    
    # Touchline Market Data
    ltp: float = 0.0                          # Last Traded Price
    price_change: float = 0.0                 # Absolute change from previous close
    percent_change: float = 0.0               # % change from previous close
    bid_price: float = 0.0                    # Best Bid
    bid_quantity: int = 0                     # Best Bid Quantity
    ask_price: float = 0.0                    # Best Ask
    ask_quantity: int = 0                     # Best Ask Quantity
    
    # Liquidity & Flow Metrics
    open_interest: int = 0                    # Total Open Contracts
    change_in_oi: int = 0                     # Absolute dOI from previous session
    percent_change_in_oi: float = 0.0         # % dOI
    volume: int = 0                           # Total traded contracts today
    total_traded_value: float = 0.0           # Turnover (INR)
    
    # Structural Attributes
    moneyness: str = "OTM"                    # "ITM", "ATM", "OTM"
    intrinsic_value: float = 0.0              # max(0, Spot - Strike) for CE; max(0, Strike - Spot) for PE
    is_max_oi: bool = False                   # True if this strike has highest OI on this side
    is_max_volume: bool = False               # True if this strike has highest volume on this side
```

#### 2. `OptionStrikeRow`
Represents a paired horizontal strike tier containing both Call and Put quotes:
```python
@dataclass
class OptionStrikeRow:
    strike_price: float                       # Common strike price
    is_atm: bool = False                      # True if nearest to Spot
    distance_from_spot: float = 0.0           # Strike - Spot
    call_quote: Optional[OptionContractQuote] = None
    put_quote: Optional[OptionContractQuote] = None
```

#### 3. `OptionChainSnapshot`
Top-level container holding the full aggregated chain view with regulatory dual timestamps:
```python
@dataclass
class OptionChainSnapshot:
    underlying_symbol: str                    # "NIFTY"
    spot_price: float                         # 24512.40
    spot_price_change: float = 0.0
    spot_percent_change: float = 0.0
    expiry_date: str                          # "2026-11-26"
    atm_strike: float = 24500.0
    strike_step: float = 50.0
    lot_size: int = 25
    
    # Aggregated Chain Analytics
    total_call_oi: int = 0
    total_put_oi: int = 0
    total_call_volume: int = 0
    total_put_volume: int = 0
    pcr_oi: float = 0.0                       # Put-Call Ratio (OI)
    pcr_volume: float = 0.0                   # Put-Call Ratio (Volume)
    max_pain_strike: Optional[float] = None   # Strike causing maximum financial loss to option buyers
    max_call_oi_strike: Optional[float] = None# Key Resistance Level
    max_put_oi_strike: Optional[float] = None # Key Support Level
    
    # Strike Ladder
    strikes: List[OptionStrikeRow] = field(default_factory=list)
    
    # Regulatory Dual Timestamps (Mandated across Portfolios and Orders)
    source_timestamp: Optional[str] = None    # Upstream broker tick time
    retrieved_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
```

---

## 5. Open Interest (OI) & Volume Architecture

### 5.1. Open Interest (OI) Mechanics
In exchange derivatives, Open Interest represents the total number of outstanding active derivative contracts that have not been settled or closed out:
* **Absolute OI:** Total contracts currently held by market participants.
* **Net Change in OI ($\Delta OI$):**
  $$\Delta OI = OI_{\text{current}} - OI_{\text{previous\_close}}$$
* **Percent Change in OI:**
  $$\%\Delta OI = \begin{cases} \left(\frac{\Delta OI}{OI_{\text{previous\_close}}}\right) \times 100 & \text{if } OI_{\text{previous\_close}} > 0 \\ 0.0 & \text{otherwise} \end{cases}$$

### 5.2. Market Activity Classification Matrix
The combination of Price direction and Open Interest change reveals institutional participant flow:

| Price Change | $\Delta OI$ | Volume | Market Interpretation | Workbench Visual Indicator |
|---|---|---|---|---|
| $\Delta P > 0$ | $\Delta OI > 0$ | High | **Long Buildup** (Fresh Bullish Buying) | Green Tag `LONG_BUILDUP` |
| $\Delta P < 0$ | $\Delta OI > 0$ | High | **Short Buildup** (Fresh Bearish Selling) | Red Tag `SHORT_BUILDUP` |
| $\Delta P < 0$ | $\Delta OI < 0$ | Moderate | **Long Unwinding** (Bulls Exiting / Profit Booking) | Amber Tag `LONG_UNWINDING` |
| $\Delta P > 0$ | $\Delta OI < 0$ | Moderate | **Short Covering** (Bears Scrambling to Exit) | Blue Tag `SHORT_COVERING` |

*(Note: These tags provide informational context on the Workbench UI; they never generate automated trade signals).*

### 5.3. Support and Resistance Derivation
* **Key Resistance Strike ($R_{key}$):** Strike with the maximum absolute Call Open Interest ($\max(OI_{CE})$). Option writers have committed maximum capital asserting price will expire below this strike.
* **Key Support Strike ($S_{key}$):** Strike with the maximum absolute Put Open Interest ($\max(OI_{PE})$). Option writers have committed maximum capital asserting price will expire above this strike.

---

## 6. Put-Call Ratio (PCR) Engine

### 6.1. Mathematical Definitions
The Put-Call Ratio is the premier sentiment indicator in derivatives analysis:

1. **Open Interest PCR ($\text{PCR}_{OI}$):**
   $$\text{PCR}_{OI} = \frac{\sum_{i=1}^{M} OI_{PE, i}}{\sum_{i=1}^{M} OI_{CE, i}}$$
   Where $M$ is the count of active strikes in the selected expiry.

2. **Volume PCR ($\text{PCR}_{Vol}$):**
   $$\text{PCR}_{Vol} = \frac{\sum_{i=1}^{M} \text{Volume}_{PE, i}}{\sum_{i=1}^{M} \text{Volume}_{CE, i}}$$

3. **Strike-Specific PCR ($\text{PCR}_{K}$):**
   $$\text{PCR}_{K} = \begin{cases} \frac{OI_{PE, K}}{OI_{CE, K}} & \text{if } OI_{CE, K} > 0 \\ 0.0 & \text{otherwise} \end{cases}$$

### 6.2. Safe Division & Edge Cases
* **Zero Denominator Protection:** If $\sum OI_{CE} == 0$, $\text{PCR}_{OI}$ returns `0.0` and flags `ZERO_CALL_OI` rather than throwing `ZeroDivisionError`.
* **Outlier Capping:** PCR values are clamped to `[0.0, 10.0]` for display stability.

### 6.3. Sentiment Classification Reference
*(Informational baseline only; strictly zero automated action):*
* $\text{PCR}_{OI} > 1.30$: Bullish sentiment (High Put writing / support floor).
* $0.80 \le \text{PCR}_{OI} \le 1.30$: Neutral / Balanced range-bound market.
* $\text{PCR}_{OI} < 0.80$: Bearish sentiment (Heavy Call writing / resistance ceiling).

---

## 7. ATM, ITM, and OTM Classification Engine

### 7.1. Dynamic ATM Strike Calculation
Given Spot Reference Price $S$ and Strike Step $\Delta K$:
$$K_{ATM} = \text{round}\left(\frac{S}{\Delta K}\right) \times \Delta K$$

**Example Computations:**
* If NIFTY Spot $S = 24,512.40$, Step $\Delta K = 50.0$:
  $$K_{ATM} = \text{round}(24512.40 / 50.0) \times 50.0 = \text{round}(490.248) \times 50.0 = 490 \times 50.0 = \mathbf{24,500.0}$$
* If BANKNIFTY Spot $S = 51,280.00$, Step $\Delta K = 100.0$:
  $$K_{ATM} = \text{round}(51280.00 / 100.0) \times 100.0 = \text{round}(512.8) \times 100.0 = 513 \times 100.0 = \mathbf{51,300.0}$$

### 7.2. Moneyness & Intrinsic Value Classification Rules

| Side | Condition | Moneyness | Intrinsic Value Formula | Visual UI Shading |
|---|---|---|---|---|
| **Call (CE)** | $K < K_{ATM}$ | **ITM** (In-The-Money) | $\max(0, \; S - K)$ | Soft Yellow / Cream background |
| **Call (CE)** | $K == K_{ATM}$ | **ATM** (At-The-Money) | $\max(0, \; S - K)$ | High-contrast Highlight border |
| **Call (CE)** | $K > K_{ATM}$ | **OTM** (Out-Of-The-Money) | $0.0$ | Clean White / Transparent |
| **Put (PE)** | $K > K_{ATM}$ | **ITM** (In-The-Money) | $\max(0, \; K - S)$ | Soft Yellow / Cream background |
| **Put (PE)** | $K == K_{ATM}$ | **ATM** (At-The-Money) | $\max(0, \; K - S)$ | High-contrast Highlight border |
| **Put (PE)** | $K < K_{ATM}$ | **OTM** (Out-Of-The-Money) | $0.0$ | Clean White / Transparent |

---

## 8. Option Chain REST APIs

Phase 10 publishes authenticated, high-performance endpoints under the `/api/option-chain` blueprint prefix:

### 8.1. Endpoints Specification

#### 1. `GET /api/option-chain/underlyings`
Returns the catalog of configured derivatives underlyings, their spot token mappings, and default strike intervals.
* **Authentication:** Required (`@login_required`).
* **Response:**
  ```json
  {
    "status": "success",
    "data": {
      "underlyings": [
        {
          "symbol": "NIFTY",
          "display_name": "Nifty 50 Index",
          "segment": "nse_fo",
          "spot_segment": "nse_cm",
          "spot_token": "26000",
          "strike_step": 50.0,
          "lot_size": 25,
          "spot_ltp": 24512.40
        },
        {
          "symbol": "BANKNIFTY",
          "display_name": "Bank Nifty Index",
          "segment": "nse_fo",
          "spot_segment": "nse_cm",
          "spot_token": "26001",
          "strike_step": 100.0,
          "lot_size": 15,
          "spot_ltp": 51280.00
        }
      ]
    }
  }
  ```

#### 2. `GET /api/option-chain/expiries`
Retrieves sorted, categorized contract expiries for a specified underlying.
* **Query Parameters:**
  * `symbol` (Required, string): e.g., `NIFTY`
* **Response:**
  ```json
  {
    "status": "success",
    "data": {
      "symbol": "NIFTY",
      "expiries": [
        {
          "expiry_date": "2026-11-12",
          "display_label": "12-Nov-2026 (Weekly)",
          "days_to_expiry": 6,
          "is_current_weekly": true,
          "is_monthly": false
        },
        {
          "expiry_date": "2026-11-26",
          "display_label": "26-Nov-2026 (Monthly)",
          "days_to_expiry": 20,
          "is_current_weekly": false,
          "is_monthly": true
        }
      ]
    }
  }
  ```

#### 3. `GET /api/option-chain`
Retrieves the full symmetrical strike matrix, paired quotes, OI, Volume, PCR, and Moneyness flags.
* **Query Parameters:**
  * `symbol` (Required, string): e.g., `NIFTY`
  * `expiry` (Optional, string): ISO date `YYYY-MM-DD`. Defaults to current nearest expiry.
  * `strike_count` (Optional, integer): Number of strikes above/below ATM (default: 15, max: 30).
* **Response Structure:**
  ```json
  {
    "status": "success",
    "data": {
      "underlying_symbol": "NIFTY",
      "spot_price": 24512.40,
      "spot_change": 85.20,
      "expiry_date": "2026-11-26",
      "atm_strike": 24500.0,
      "strike_step": 50.0,
      "lot_size": 25,
      "pcr_oi": 1.15,
      "pcr_volume": 0.94,
      "total_call_oi": 48500200,
      "total_put_oi": 55775230,
      "max_call_oi_strike": 25000.0,
      "max_put_oi_strike": 24000.0,
      "source_timestamp": "2026-11-06T10:00:00.125Z",
      "retrieved_timestamp": "2026-11-06T10:00:01.050Z",
      "strikes": [
        {
          "strike_price": 24500.0,
          "is_atm": true,
          "call_quote": {
            "trading_symbol": "NIFTY26NOV24500CE",
            "instrument_token": "45210",
            "ltp": 145.20,
            "bid_price": 145.10,
            "ask_price": 145.30,
            "open_interest": 8200500,
            "change_in_oi": 450000,
            "volume": 2900000,
            "moneyness": "ATM",
            "intrinsic_value": 12.40
          },
          "put_quote": {
            "trading_symbol": "NIFTY26NOV24500PE",
            "instrument_token": "45211",
            "ltp": 115.00,
            "bid_price": 114.85,
            "ask_price": 115.10,
            "open_interest": 7900000,
            "change_in_oi": -120000,
            "volume": 2600000,
            "moneyness": "ATM",
            "intrinsic_value": 0.0
          }
        }
      ]
    }
  }
  ```

#### 4. `GET /api/option-chain/pcr`
Lightweight summary endpoint returning solely PCR and aggregate OI distribution.

---

## 9. Basket Builder Integration Architecture

The primary operational mission of the Option Chain Workbench is to eliminate manual symbol entry and feed directly into the **Phase 9 Multi-Leg Basket Foundation**.

```
[ Option Chain UI ]
        |
        | User clicks "Bid" or "Ask" on CE/PE, or clicks "Iron Condor"
        v
[ Client-Side Workbench State ]
        |
        | Constructs Basket Payload conforming to Phase 9 Schema
        v
[ POST /api/baskets/validate ] (Dry-Run Pre-Trade Risk Check)
        |
        +---> Returns: margin_snapshot, upfront_margin, structural validation
        |
        v
[ POST /api/baskets ] (Save Draft Container)
        |
        v
[ User Clicks 'Execute Basket' ] ---> [ POST /api/baskets/<id>/execute ]
```

### 9.1. Interactive Selection to Basket Leg Mapping
When an operator interacts with a strike in the workbench:
* Clicking **Bid Column** on a Call/Put: Prepares a `SELL` (Short) `BasketLeg`.
* Clicking **Ask Column** on a Call/Put: Prepares a `BUY` (Long) `BasketLeg`.
* Quantity defaults to 1 lot ($1 \times \text{lot\_size}$).
* Order Type defaults to `LIMIT` with price snapped to current touchline (Bid/Ask).

### 9.2. Automated Strategy Template Builders
The workbench provides one-click template macros that auto-populate Phase 9 compliant multi-leg structures around the selected strike $K$:

1. **Bull Call Spread Builder:**
   * Leg 0: Buy Call @ $K$ (e.g. $K_{ATM}$)
   * Leg 1: Sell Call @ $K + \Delta K$
   * Automatically sets `strategy_type = StrategyType.BULL_CALL_SPREAD`.

2. **Bear Put Spread Builder:**
   * Leg 0: Buy Put @ $K$ (e.g. $K_{ATM}$)
   * Leg 1: Sell Put @ $K - \Delta K$
   * Automatically sets `strategy_type = StrategyType.BEAR_PUT_SPREAD`.

3. **Long Straddle Builder:**
   * Leg 0: Buy Call @ $K_{ATM}$
   * Leg 1: Buy Put @ $K_{ATM}$
   * Sets `strategy_type = StrategyType.LONG_STRADDLE`.

4. **Iron Condor Builder:**
   * User specifies wing width $W$ (e.g. 200 pts):
   * Leg 0: Buy OTM Put @ $K_{ATM} - 2W$
   * Leg 1: Sell Put @ $K_{ATM} - W$
   * Leg 2: Sell Call @ $K_{ATM} + W$
   * Leg 3: Buy OTM Call @ $K_{ATM} + 2W$
   * Sets `strategy_type = StrategyType.IRON_CONDOR`, `basket_execution_mode = DEPENDENCY` (Wings first, Body second).

---

## 10. Watchlist Integration Architecture

The workbench allows operators to monitor specific option contracts continuously by dispatching them into **Phase 5 Watchlists**:

```
[ Option Chain Contract Row ]
             |
             | Operator clicks "Add to Watchlist" (Star Icon)
             v
[ POST /api/market-watch/watchlist/<id>/items ]
   Payload: {
     "trading_symbol": "NIFTY26NOV24500CE",
     "exchange_segment": "nse_fo",
     "instrument_token": "45210"
   }
             |
             v
[ Phase 5 WatchlistService ]
   - Validates quota (max 50 scrips per watchlist)
   - Increments SubscriptionManager ref_count
   - Adds token to SFeed WebSocket subscription batch
```

---

## 11. Streaming Integration Architecture (SFeed)

### 11.1. Dynamic Subscription Management
A full option chain with 30 strikes across Call and Put sides requires tracking **60 active option contracts plus 1 spot index**. 

The Kotak Neo SFeed streaming engine operates under a global session subscription limit of 3,000 instruments. To prevent quota starvation and unnecessary network bandwidth consumption:
1. **Windowed Subscription:** The workbench subscribes *only* to the currently visible strike matrix ($2N + 1$ strikes $\times 2$ sides).
2. **Batch Subscription:** When an expiry is selected, the tokens are batched via Phase 4 [`SubscriptionManager`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/market_watch/services/subscription_manager.py) (`subscribe_scrips(tokens)`).
3. **Automatic Teardown on Expiry Change:** When the operator selects a different expiry or navigates away, the previous expiry tokens are unsubscribed (`unsubscribe_scrips(tokens)`), decrementing reference counts cleanly.

### 11.2. Streaming Ingestion Pipeline
Incoming SFeed WebSocket ticks are processed as follows:
```
[ SFeed WebSocket Frame ]
           |
           +---> SFeedIndex (Spot Index) -> Updates Spot LTP -> Re-evaluates ATM Strike
           |
           +---> SFeedScrip (Option Leg) -> Updates Contract LTP, Bid/Ask, OI, Volume
                                        -> Re-calculates PCR_OI and PCR_Vol dynamically
```

---

## 12. In-Memory Caching & Performance Architecture

To protect upstream Kotak Neo broker endpoints from rate-limiting penalties:
1. **Expiry Cache:** Active contract expiries change once per day. Cached in-memory with a **4-hour TTL**.
2. **Instrument Master Token Cache:** Instrument token lookups for strike pairs are cached in-memory with a **1-day TTL**.
3. **Chain Snapshot Cache:** REST responses for static option chain snapshots are cached with a **3-second TTL** during market hours (`09:15 - 15:30 IST`), transparently invalidated by incoming WebSocket streaming ticks.

---

## 13. Test Strategy & Verification Plan

Phase 10 verification requires a multi-layered test suite enforcing mathematical precision, edge-case safety, and seamless inter-phase integration:

### 13.1. Unit Test Coverage
1. **Underlying Specifications (`test_option_chain_underlyings.py`):**
   - Verify lot sizes, tick sizes, and strike steps across all benchmark contracts (NIFTY 25/50, BANKNIFTY 15/100, etc.).
2. **ATM & Moneyness Engine (`test_atm_and_moneyness.py`):**
   - Verify ATM rounding for spot prices across step boundaries (e.g. 24,524.90 $\to$ 24,500; 24,525.10 $\to$ 24,550).
   - Verify Call ITM/OTM rules ($K < S \implies \text{ITM}$, $K > S \implies \text{OTM}$).
   - Verify Put ITM/OTM rules ($K > S \implies \text{ITM}$, $K < S \implies \text{OTM}$).
   - Verify intrinsic value computation matches exact mathematical formulas.
3. **PCR & Open Interest Aggregator (`test_pcr_engine.py`):**
   - Verify aggregate $\text{PCR}_{OI}$ and $\text{PCR}_{Vol}$ formulas.
   - Verify zero Call OI denominator safety (returns `0.0`, zero unhandled exceptions).
   - Verify Max Pain and Max OI strike detection ($R_{key}$, $S_{key}$).
4. **Strategy Template Builders (`test_chain_strategy_builder.py`):**
   - Test automated Bull Call Spread, Bear Put Spread, and Iron Condor payload synthesis directly from chain strikes.
   - Verify generated payloads strictly satisfy Phase 9 `StrategyValidationService` rules.

### 13.2. Integration & REST API Tests (`test_option_chain_routes.py`)
1. **Public/Authenticated Routes:** Verify authentication requirements (`@login_required`).
2. **GET `/api/option-chain/underlyings`:** Verify schema, status 200, spot token linkage.
3. **GET `/api/option-chain/expiries`:** Verify expiry sorting, weekly/monthly tagging.
4. **GET `/api/option-chain`:** Verify symmetrical matrix generation ($2N + 1$ rows), Call/Put pairing, and dual timestamps.
5. **Watchlist & Basket Integration Flow:** Verify clicking a strike emits a valid watchlist item and can be passed to Phase 9 `POST /api/baskets`.

### 13.3. Negative & Boundary Scenarios
1. **Missing Spot Price:** Spot stream unavailable $\implies$ Returns HTTP 503 / `SPOT_PRICE_UNAVAILABLE`.
2. **Invalid Expiry Date:** Requesting non-existent expiry $\implies$ Returns HTTP 400 / `INVALID_EXPIRY`.
3. **Empty Contract Matrix:** Holiday or closed segment $\implies$ Graceful degradation with empty strikes array.

---

## 14. Summary & Implementation Approval Checklist

Phase 10 provides the complete architectural design specification for the Option Chain Workbench.

### Pre-Implementation Review Checklist:
- [x] Underlying selection architecture defined (Index & Stock F&O)
- [x] Expiry pipeline and categorization specified
- [x] Symmetrical strike matrix and domain models designed
- [x] Open Interest, volume metrics, and buildup classification specified
- [x] PCR engine with zero-division safety designed
- [x] Real-time ATM, ITM, and OTM classification formulas defined
- [x] REST API contracts specified under `/api/option-chain`
- [x] Phase 9 Basket Builder integration pipeline documented
- [x] Phase 5 Watchlist and Phase 4 SFeed streaming integration designed
- [x] Zero implementation code generated in this design specification
- [x] Strict scope exclusions enforced (Greeks, Volatility Analytics, Delta Hedging, Auto Trading excluded)

**Status:** Ready for human operator review and approval.
