"""
Mark-to-Market (MTM) & Real-Time PnL Calculation Engine.
Phase 6: Portfolio Foundation.
Recalculates floating unrealized MTM on incoming ticks without triggering broker REST calls.
"""

from datetime import datetime, timezone
import threading
import time
from typing import Dict, List, Optional, Tuple

from app.events.event_bus import publish
from app.events.event_types import MTM_UPDATED
from app.logging.logger import get_logger
from app.market_watch.services.price_engine import (
    MarketWatchPriceEngine,
    price_engine,
)
from app.portfolio.models.position import Position

logger = get_logger("app.portfolio.services.mtm_engine")


class MTMEngine:
    """
    In-memory computation engine for real-time portfolio Mark-to-Market (MTM).
    Binds open positions to live quotes and recalculates floating PnL with sub-millisecond latency.
    """

    def __init__(
        self, prices: Optional[MarketWatchPriceEngine] = None
    ) -> None:
        self.price_engine = prices or price_engine
        self._lock = threading.RLock()
        # Key: (instrument_token, exchange_segment), Value: Position
        self._active_positions: Dict[Tuple[str, str], Position] = {}
        self._last_unrealized_mtm: float = 0.0

    def set_positions(self, positions: List[Position]) -> None:
        """Register current positions for live MTM tracking."""
        with self._lock:
            self._active_positions.clear()
            for pos in positions:
                key = (pos.instrument_token.strip(), pos.exchange_segment.strip().lower())
                self._active_positions[key] = pos
            self.recalculate_all()

    def update_position(self, position: Position) -> None:
        """Add or update a single position."""
        key = (position.instrument_token.strip(), position.exchange_segment.strip().lower())
        with self._lock:
            self._active_positions[key] = position
            self._recalculate_single(position)

    def on_tick_received(self, token: str, segment: str, ltp: float) -> Optional[float]:
        """
        Invoked when a real-time price tick arrives for an instrument.
        Recalculates position MTM if instrument is an open commitment.
        """
        key = (str(token).strip(), str(segment).strip().lower())
        with self._lock:
            pos = self._active_positions.get(key)
            if not pos:
                return None

            pos.current_price = ltp
            self._recalculate_single(pos)
            tot_mtm = self.get_total_unrealized_mtm()

            publish(
                MTM_UPDATED,
                {
                    "token": token,
                    "segment": segment,
                    "ltp": ltp,
                    "unrealized_mtm": tot_mtm,
                    "timestamp": time.time(),
                },
            )
            return tot_mtm

    def recalculate_all(self) -> float:
        """Recalculate MTM across all tracked open positions using latest PriceEngine quotes."""
        with self._lock:
            for key, pos in self._active_positions.items():
                quote = self.price_engine.get_quote(key[0], key[1])
                if quote and quote.ltp > 0:
                    pos.current_price = quote.ltp
                self._recalculate_single(pos)

            self._last_unrealized_mtm = sum(
                p.unrealized_pnl for p in self._active_positions.values() if p.is_open
            )
            return self._last_unrealized_mtm

    def get_total_unrealized_mtm(self) -> float:
        """Return cached total open unrealized MTM."""
        with self._lock:
            return sum(p.unrealized_pnl for p in self._active_positions.values() if p.is_open)

    def get_total_realized_pnl(self) -> float:
        """Return total realized PnL from closed position volume."""
        with self._lock:
            return sum(p.realized_pnl for p in self._active_positions.values())

    def get_open_positions_count(self) -> int:
        """Return count of currently open positions."""
        with self._lock:
            return sum(1 for p in self._active_positions.values() if p.is_open)

    def get_positions(self) -> List[Position]:
        """Return all tracked positions."""
        with self._lock:
            return list(self._active_positions.values())

    def _recalculate_single(self, pos: Position) -> None:
        """Internal helper evaluating Long, Short, or Closed MTM."""
        if not pos.is_open:
            pos.unrealized_pnl = 0.0
            pos.total_pnl = pos.realized_pnl
            pos.updated_at = time.time()
            return

        ltp = pos.current_price
        if pos.net_quantity > 0:
            # Long: net_qty * (LTP - buy_avg)
            pos.unrealized_pnl = pos.net_quantity * (ltp - pos.average_buy_price)
        elif pos.net_quantity < 0:
            # Short: |net_qty| * (sell_avg - LTP)
            pos.unrealized_pnl = abs(pos.net_quantity) * (pos.average_sell_price - ltp)
        else:
            pos.unrealized_pnl = 0.0

        pos.total_pnl = pos.realized_pnl + pos.unrealized_pnl
        pos.updated_at = time.time()


# Global Singleton MTM Engine
mtm_engine = MTMEngine()
