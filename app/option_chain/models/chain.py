"""
Option Chain Domain Models.
Phase 10: Option Chain Workbench.
Encapsulates real-time strike rows, Call/Put contract quotes,
liquidity metrics, PCR, and regulatory dual timestamps.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional

from app.option_chain.models.underlying import StrikeFilterPreset


@dataclass
class ExpiryInfo:
    """Standardized expiry metadata and categorization."""

    expiry_date: str                          # ISO-8601: "YYYY-MM-DD"
    display_label: str                        # e.g., "26-Nov-2026 (Monthly)"
    days_to_expiry: int                       # DTE (Calendar days remaining)
    is_current_weekly: bool = False           # True for the nearest upcoming expiry
    is_monthly: bool = False                  # True for monthly series expiry
    trading_symbol_token: str = ""            # Expiry token in trading symbol (e.g. "26NOV")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "expiry_date": self.expiry_date,
            "display_label": self.display_label,
            "days_to_expiry": self.days_to_expiry,
            "is_current_weekly": self.is_current_weekly,
            "is_monthly": self.is_monthly,
            "trading_symbol_token": self.trading_symbol_token,
        }


@dataclass
class OptionContractQuote:
    """
    Real-time market touchline, liquidity, and volume metrics for an individual Call or Put contract.
    """

    instrument_token: str                     # Broker instrument token (e.g. "45210")
    trading_symbol: str                       # Contract symbol (e.g. "NIFTY26NOV24500CE")
    option_type: str                          # "CE" or "PE"
    strike_price: float                       # 24500.0
    expiry_date: str                          # "2026-11-26"

    # Touchline Market Data
    ltp: float = 0.0                          # Last Traded Price
    price_change: float = 0.0                 # Net price change
    percent_change: float = 0.0               # % price change
    bid_price: float = 0.0                    # Best Bid Price
    bid_quantity: int = 0                     # Best Bid Quantity
    ask_price: float = 0.0                    # Best Ask Price
    ask_quantity: int = 0                     # Best Ask Quantity

    # Liquidity & Flow Metrics
    open_interest: int = 0                    # Total Open Contracts
    change_in_oi: int = 0                     # Absolute dOI from prior session
    percent_change_in_oi: float = 0.0         # % dOI
    volume: int = 0                           # Total traded contracts today
    total_traded_value: float = 0.0           # Turnover (INR)
    oi_source_timestamp: Optional[str] = None # Upstream exchange OI broadcast timestamp

    # Moneyness & Invariant Flags
    moneyness: str = "OTM"                    # "ITM", "ATM", "OTM"
    intrinsic_value: float = 0.0              # max(0, Spot - Strike) for CE, max(0, Strike - Spot) for PE
    is_max_oi: bool = False                   # True if strike holds max OI on this side
    is_max_volume: bool = False               # True if strike holds max volume on this side
    activity_tag: str = "NEUTRAL"             # LONG_BUILDUP, SHORT_BUILDUP, LONG_UNWINDING, SHORT_COVERING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instrument_token": self.instrument_token,
            "trading_symbol": self.trading_symbol,
            "option_type": self.option_type,
            "strike_price": self.strike_price,
            "expiry_date": self.expiry_date,
            "ltp": round(self.ltp, 2),
            "price_change": round(self.price_change, 2),
            "percent_change": round(self.percent_change, 2),
            "bid_price": round(self.bid_price, 2),
            "bid_quantity": self.bid_quantity,
            "ask_price": round(self.ask_price, 2),
            "ask_quantity": self.ask_quantity,
            "open_interest": self.open_interest,
            "change_in_oi": self.change_in_oi,
            "percent_change_in_oi": round(self.percent_change_in_oi, 2),
            "volume": self.volume,
            "total_traded_value": round(self.total_traded_value, 2),
            "oi_source_timestamp": self.oi_source_timestamp,
            "moneyness": self.moneyness,
            "intrinsic_value": round(self.intrinsic_value, 2),
            "is_max_oi": self.is_max_oi,
            "is_max_volume": self.is_max_volume,
            "activity_tag": self.activity_tag,
        }


@dataclass
class OptionStrikeRow:
    """Paired horizontal strike tier containing Call and Put quotes."""

    strike_price: float
    is_atm: bool = False
    distance_from_spot: float = 0.0
    call_quote: Optional[OptionContractQuote] = None
    put_quote: Optional[OptionContractQuote] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strike_price": self.strike_price,
            "is_atm": self.is_atm,
            "distance_from_spot": round(self.distance_from_spot, 2),
            "call_quote": self.call_quote.to_dict() if self.call_quote else None,
            "put_quote": self.put_quote.to_dict() if self.put_quote else None,
        }


@dataclass
class OptionChainSnapshot:
    """
    Top-level Option Chain aggregated matrix with PCR, total OI, Max Pain,
    filter preset, and dual regulatory timestamps.
    """

    underlying_symbol: str
    spot_price: float
    spot_price_change: float = 0.0
    spot_percent_change: float = 0.0
    expiry_date: str = ""
    atm_strike: float = 0.0
    strike_step: float = 50.0
    lot_size: int = 25
    preset: StrikeFilterPreset = StrikeFilterPreset.ATM_10

    # Aggregated Liquidity & Sentiments
    total_call_oi: int = 0
    total_put_oi: int = 0
    total_call_volume: int = 0
    total_put_volume: int = 0
    pcr_oi: float = 0.0
    pcr_volume: float = 0.0
    max_pain_strike: Optional[float] = None
    max_call_oi_strike: Optional[float] = None
    max_put_oi_strike: Optional[float] = None

    # Paired Strike Matrix
    strikes: List[OptionStrikeRow] = field(default_factory=list)

    # Dual Regulatory Timestamps
    source_timestamp: Optional[str] = None
    oi_source_timestamp: Optional[str] = None
    retrieved_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "underlying_symbol": self.underlying_symbol,
            "spot_price": round(self.spot_price, 2),
            "spot_price_change": round(self.spot_price_change, 2),
            "spot_percent_change": round(self.spot_percent_change, 2),
            "expiry_date": self.expiry_date,
            "atm_strike": round(self.atm_strike, 2),
            "strike_step": self.strike_step,
            "lot_size": self.lot_size,
            "preset": self.preset.value if isinstance(self.preset, StrikeFilterPreset) else str(self.preset),
            "total_call_oi": self.total_call_oi,
            "total_put_oi": self.total_put_oi,
            "total_call_volume": self.total_call_volume,
            "total_put_volume": self.total_put_volume,
            "pcr_oi": round(self.pcr_oi, 4),
            "pcr_volume": round(self.pcr_volume, 4),
            "max_pain_strike": self.max_pain_strike,
            "max_call_oi_strike": self.max_call_oi_strike,
            "max_put_oi_strike": self.max_put_oi_strike,
            "total_strikes": len(self.strikes),
            "strikes": [s.to_dict() for s in self.strikes],
            "source_timestamp": self.source_timestamp,
            "oi_source_timestamp": self.oi_source_timestamp,
            "retrieved_timestamp": self.retrieved_timestamp,
            "created_at": self.created_at,
        }

