"""
Instrument and MarketQuote In-Memory Models.
Phase 5: Market Watch Foundation.
Provides high-performance data structures for Scrip Master indexing and real-time touchline quotes.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Instrument:
    """
    Normalized instrument definition loaded from Kotak Neo Scrip Master.
    """

    instrument_token: str
    exchange_segment: str
    trading_symbol: str
    symbol_name: str
    display_name: str
    lot_size: int = 1
    tick_size: float = 0.05
    instrument_type: str = "EQ"
    expiry_date: Optional[str] = None
    strike_price: Optional[float] = None
    option_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MarketQuote:
    """
    Real-time touchline quote snapshot maintained in the in-memory quote cache.
    Includes OHLC, volume, LTP, bid/ask, and price change metrics.
    """

    instrument_token: str
    exchange_segment: str
    trading_symbol: str
    ltp: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    net_change: float = 0.0
    percent_change: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    bid_qty: int = 0
    ask_qty: int = 0
    last_trade_time: Optional[str] = None
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instrument_token": self.instrument_token,
            "exchange_segment": self.exchange_segment,
            "trading_symbol": self.trading_symbol,
            "ltp": round(self.ltp, 2),
            "open": round(self.open, 2),
            "high": round(self.high, 2),
            "low": round(self.low, 2),
            "close": round(self.close, 2),
            "volume": self.volume,
            "net_change": round(self.net_change, 2),
            "percent_change": round(self.percent_change, 2),
            "bid": round(self.bid, 2),
            "ask": round(self.ask, 2),
            "bid_qty": self.bid_qty,
            "ask_qty": self.ask_qty,
            "last_trade_time": self.last_trade_time,
            "updated_at": round(self.updated_at, 3),
        }
