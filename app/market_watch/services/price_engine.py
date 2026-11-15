"""
Market Watch Price Engine & In-Memory Quote Cache.
Phase 5: Market Watch Foundation.
Ingests real-time SFeed touchline/index packets, applies exchange scalers,
normalizes spot index payloads, and maintains low-latency quote snapshots.
"""

from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from app.events.event_bus import publish
from app.events.event_types import PRICE_TICK_INGESTED
from app.logging.logger import get_logger
from app.market_watch.models.instrument import MarketQuote

logger = get_logger("app.market_watch.services.price_engine")


class MarketWatchPriceEngine:
    """
    Real-time market price processor and in-memory quote cache.
    Applies segment dividers, normalizes Kotak Neo SFeed ticks, and stores touchline metrics.
    """

    # Exchange Segment Price Dividers (Scalers)
    PRICE_DIVIDERS = {
        "nse_cm": 100.0,
        "bse_cm": 100.0,
        "nse_fo": 100.0,
        "bse_fo": 100.0,
        "cde_fo": 10000.0,  # Currency 4 decimals
    }

    # Standard Spot Index Name to Token/Segment Mapping
    INDEX_NAME_MAP = {
        "NIFTY 50": ("26000", "nse_cm", "Nifty 50"),
        "NIFTY BANK": ("26001", "nse_cm", "Nifty Bank"),
        "BANKNIFTY": ("26001", "nse_cm", "Nifty Bank"),
        "SENSEX": ("1", "bse_cm", "SENSEX"),
    }

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Key: (instrument_token, exchange_segment), Value: MarketQuote
        self._quotes: Dict[Tuple[str, str], MarketQuote] = {}
        self._last_tick_timestamp: Optional[float] = None
        self._last_tick_symbol: Optional[str] = None

    def get_quote(self, token: str, segment: str) -> Optional[MarketQuote]:
        """Fetch quote snapshot for an instrument."""
        key = (str(token).strip(), str(segment).strip().lower())
        with self._lock:
            return self._quotes.get(key)

    def get_touchline(self, segment: str, token: str) -> Optional[MarketQuote]:
        """Convenience alias for retrieving quotes via (segment, token) or (token, segment)."""
        with self._lock:
            q = self.get_quote(token=token, segment=segment)
            if q is not None:
                return q
            return self.get_quote(token=segment, segment=token)

    def get_all_quotes(self) -> Dict[str, Dict[str, Any]]:
        """Fetch all cached quotes formatted as token key map: 'segment:token' -> quote dict."""
        with self._lock:
            return {f"{k[1]}:{k[0]}": v.to_dict() for k, v in self._quotes.items()}

    def get_quotes_count(self) -> int:
        """Return total number of distinct quotes currently cached."""
        with self._lock:
            return len(self._quotes)

    def get_last_tick_timestamp(self) -> Optional[str]:
        """Return ISO timestamp of the most recent price tick ingested."""
        with self._lock:
            if self._last_tick_timestamp:
                return datetime.fromtimestamp(self._last_tick_timestamp, tz=timezone.utc).isoformat()
            return None

    def get_last_tick_symbol(self) -> Optional[str]:
        """Return trading symbol of the most recent price tick ingested."""
        with self._lock:
            return self._last_tick_symbol

    def get_quotes_batch(
        self, tokens: List[Tuple[str, str]]
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch multiple quotes formatted as a token key map: 'segment:token' -> quote dict."""
        result: Dict[str, Dict[str, Any]] = {}
        with self._lock:
            for token, segment in tokens:
                key = (str(token).strip(), str(segment).strip().lower())
                quote = self._quotes.get(key)
                if quote:
                    result[f"{key[1]}:{key[0]}"] = quote.to_dict()
        return result

    def ingest_tick(self, packet: Dict[str, Any]) -> Optional[MarketQuote]:
        """
        Process incoming tick from KotakStreamAdapter.
        Supports both standard SFeedScrip touchline and SFeedIndex frames.
        """
        if not packet or not isinstance(packet, dict):
            return None

        # Check if this is an Index packet (identified by index name or explicit index indicator)
        index_name = (
            packet.get("index_name")
            or packet.get("name")
            or packet.get("trading_symbol")
            or packet.get("indexSymbol")
            or packet.get("pIndexName")
            or ""
        ).strip().upper()

        if index_name in self.INDEX_NAME_MAP:
            token, segment, display_sym = self.INDEX_NAME_MAP[index_name]
            return self._process_index_tick(packet, token, segment, display_sym)

        # Standard touchline scrip packet
        token = str(
            packet.get("instrument_token")
            or packet.get("token")
            or packet.get("pSymbol")
            or ""
        ).strip()
        segment = str(
            packet.get("exchange_segment")
            or packet.get("segment")
            or packet.get("pSegment")
            or "nse_cm"
        ).strip().lower()

        if not token:
            return None

        symbol = str(
            packet.get("trading_symbol")
            or packet.get("symbol")
            or packet.get("pTrdSymbol")
            or token
        ).strip()

        divider = self.PRICE_DIVIDERS.get(segment, 100.0)

        # Helper to scale raw integer ticks (paise) by divider while preserving float inputs
        def scale(val: Any) -> float:
            if val is None:
                return 0.0
            try:
                if isinstance(val, bool):
                    return 0.0
                if isinstance(val, int):
                    return float(val) / divider
                if isinstance(val, float):
                    return val
                sval = str(val).strip()
                if "." in sval:
                    return float(sval)
                return float(sval) / divider
            except (ValueError, TypeError):
                return 0.0

        ltp = scale(
            packet.get("ltp")
            or packet.get("last_traded_price")
            or packet.get("last_price")
            or packet.get("iv")
            or 0.0
        )
        open_px = scale(packet.get("open") or packet.get("open_price") or ltp)
        high_px = scale(packet.get("high") or packet.get("high_price") or ltp)
        low_px = scale(packet.get("low") or packet.get("low_price") or ltp)
        close_px = scale(packet.get("close") or packet.get("close_price") or ltp)
        volume = int(packet.get("volume") or packet.get("volume_traded_today") or packet.get("v") or 0)

        # In SFeed, price change can be named net_change or change
        net_change = scale(packet.get("net_change") or packet.get("change") or (ltp - close_px if close_px else 0.0))
        pct_change = float(
            packet.get("percent_change")
            or packet.get("net_change_percent")
            or packet.get("per_change")
            or ((net_change / close_px * 100.0) if close_px > 0 else 0.0)
        )

        buy_list = packet.get("buy")
        sell_list = packet.get("sell")
        first_buy_px = (buy_list[0].get("price") if isinstance(buy_list[0], dict) else getattr(buy_list[0], "price", 0.0)) if buy_list else 0.0
        first_sell_px = (sell_list[0].get("price") if isinstance(sell_list[0], dict) else getattr(sell_list[0], "price", 0.0)) if sell_list else 0.0
        first_buy_qty = (buy_list[0].get("quantity") if isinstance(buy_list[0], dict) else getattr(buy_list[0], "quantity", 0)) if buy_list else 0
        first_sell_qty = (sell_list[0].get("quantity") if isinstance(sell_list[0], dict) else getattr(sell_list[0], "quantity", 0)) if sell_list else 0

        bid = scale(packet.get("bid") or packet.get("buy_price") or first_buy_px)
        ask = scale(packet.get("ask") or packet.get("sell_price") or first_sell_px)
        bid_qty = int(packet.get("bid_qty") or packet.get("buy_qty") or first_buy_qty)
        ask_qty = int(packet.get("ask_qty") or packet.get("sell_qty") or first_sell_qty)
        ltt = packet.get("last_trade_time") or packet.get("ltt")

        key = (token, segment)
        with self._lock:
            quote = self._quotes.get(key)
            if quote is None:
                quote = MarketQuote(
                    instrument_token=token,
                    exchange_segment=segment,
                    trading_symbol=symbol,
                    ltp=ltp,
                    open=open_px,
                    high=high_px,
                    low=low_px,
                    close=close_px,
                    volume=volume,
                    net_change=net_change,
                    percent_change=pct_change,
                    bid=bid,
                    ask=ask,
                    bid_qty=bid_qty,
                    ask_qty=ask_qty,
                    last_trade_time=str(ltt) if ltt else None,
                    updated_at=time.time(),
                )
                self._quotes[key] = quote
            else:
                if ltp > 0:
                    quote.ltp = ltp
                if open_px > 0:
                    quote.open = open_px
                if high_px > 0:
                    quote.high = high_px
                if low_px > 0:
                    quote.low = low_px
                if close_px > 0:
                    quote.close = close_px
                if volume > 0:
                    quote.volume = volume
                quote.net_change = net_change
                quote.percent_change = pct_change
                if bid > 0:
                    quote.bid = bid
                if ask > 0:
                    quote.ask = ask
                if bid_qty > 0:
                    quote.bid_qty = bid_qty
                if ask_qty > 0:
                    quote.ask_qty = ask_qty
                if ltt:
                    quote.last_trade_time = str(ltt)
                quote.updated_at = time.time()

            self._last_tick_timestamp = quote.updated_at
            self._last_tick_symbol = quote.trading_symbol

        publish(
            PRICE_TICK_INGESTED,
            {
                "instrument_token": token,
                "exchange_segment": segment,
                "ltp": ltp,
                "percent_change": pct_change,
                "timestamp": quote.updated_at,
            },
        )
        try:
            from app.websocket.socket_manager import socket_manager
            if socket_manager.socketio is not None:
                socket_manager.emit("tick", quote.to_dict())
        except Exception:
            pass

        return quote

    def _process_index_tick(
        self,
        packet: Dict[str, Any],
        token: str,
        segment: str,
        display_sym: str,
    ) -> MarketQuote:
        """Process special Kotak Neo SFeedIndex packet."""
        divider = self.PRICE_DIVIDERS.get(segment, 100.0)

        def scale(val: Any) -> float:
            if val is None:
                return 0.0
            try:
                if isinstance(val, bool):
                    return 0.0
                if isinstance(val, int):
                    return float(val) / divider
                if isinstance(val, float):
                    return val
                sval = str(val).strip()
                if "." in sval:
                    return float(sval)
                return float(sval) / divider
            except (ValueError, TypeError):
                return 0.0

        ltp = scale(
            packet.get("ltp")
            or packet.get("last_traded_price")
            or packet.get("iv")
            or packet.get("last_price")
            or 0.0
        )
        open_px = scale(packet.get("open") or packet.get("open_price") or ltp)
        high_px = scale(packet.get("high") or packet.get("high_price") or ltp)
        low_px = scale(packet.get("low") or packet.get("low_price") or ltp)
        close_px = scale(packet.get("close") or packet.get("close_price") or ltp)

        # Critical Kotak Neo Quirk: SFeedIndex uses 'change' attribute instead of 'net_change'
        net_change = scale(packet.get("change") or packet.get("net_change") or (ltp - close_px if close_px else 0.0))
        pct_change = float(
            packet.get("percent_change")
            or packet.get("net_change_percent")
            or packet.get("per_change")
            or ((net_change / close_px * 100.0) if close_px > 0 else 0.0)
        )

        key = (token, segment)
        with self._lock:
            quote = self._quotes.get(key)
            if quote is None:
                quote = MarketQuote(
                    instrument_token=token,
                    exchange_segment=segment,
                    trading_symbol=display_sym,
                    ltp=ltp,
                    open=open_px,
                    high=high_px,
                    low=low_px,
                    close=close_px,
                    volume=0,
                    net_change=net_change,
                    percent_change=pct_change,
                    updated_at=time.time(),
                )
                self._quotes[key] = quote
            else:
                if ltp > 0:
                    quote.ltp = ltp
                if open_px > 0:
                    quote.open = open_px
                if high_px > 0:
                    quote.high = high_px
                if low_px > 0:
                    quote.low = low_px
                if close_px > 0:
                    quote.close = close_px
                quote.net_change = net_change
                quote.percent_change = pct_change
                quote.updated_at = time.time()

            self._last_tick_timestamp = quote.updated_at
            self._last_tick_symbol = quote.trading_symbol

        publish(
            PRICE_TICK_INGESTED,
            {
                "instrument_token": token,
                "exchange_segment": segment,
                "ltp": ltp,
                "percent_change": pct_change,
                "timestamp": quote.updated_at,
            },
        )
        try:
            from app.websocket.socket_manager import socket_manager
            if socket_manager.socketio is not None:
                socket_manager.emit("tick", quote.to_dict())
        except Exception:
            pass

        return quote

    def clear(self) -> None:
        """Clear cached quotes."""
        with self._lock:
            self._quotes.clear()


# Global Singleton Price Engine
price_engine = MarketWatchPriceEngine()
