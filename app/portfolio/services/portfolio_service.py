"""
Unified Portfolio Service.
Phase 6: Portfolio Foundation.
Coordinates Holdings, Positions, Margins, and MTM calculation engines with multi-tiered caching.
"""

from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, List, Optional

from app.broker.adapters.kotak_adapter import KotakBrokerAdapter
from app.broker.cache.broker_cache import BrokerCache, broker_cache
from app.core.audit import AuditCategory, audit_logger
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import PORTFOLIO_REFRESHED
from app.logging.logger import get_logger
from app.portfolio.models.holding import Holding
from app.portfolio.models.margin import MarginSummary
from app.portfolio.models.portfolio_summary import PortfolioSummary
from app.portfolio.models.position import Position, PositionType
from app.portfolio.services.holdings_service import (
    HoldingsService,
    holdings_service,
)
from app.portfolio.services.margin_service import (
    MarginService,
    margin_service,
)
from app.portfolio.services.mtm_engine import (
    MTMEngine,
    mtm_engine,
)
from app.portfolio.services.positions_service import (
    PositionsService,
    positions_service,
)

logger = get_logger("app.portfolio.services.portfolio_service")


class PortfolioService:
    """
    Central portfolio orchestrator managing TTL caching, broker synchronization,
    and unified portfolio summary aggregation.
    """

    TTL_HOLDINGS = 300.0   # 5 minutes
    TTL_POSITIONS = 5.0    # 5 seconds
    TTL_MARGINS = 10.0     # 10 seconds

    def __init__(
        self,
        holdings: Optional[HoldingsService] = None,
        positions: Optional[PositionsService] = None,
        margins: Optional[MarginService] = None,
        mtm: Optional[MTMEngine] = None,
        cache: Optional[BrokerCache] = None,
        adapter: Optional[KotakBrokerAdapter] = None,
    ) -> None:
        self.holdings_service = holdings or holdings_service
        self.positions_service = positions or positions_service
        self.margin_service = margins or margin_service
        self.mtm_engine = mtm or mtm_engine
        self.cache = cache or broker_cache
        self.adapter = adapter or KotakBrokerAdapter()
        self._lock = threading.RLock()

        # In-memory working copies
        self._cached_holdings: List[Holding] = []
        self._cached_margins: Optional[MarginSummary] = None

    def get_holdings(self, force_refresh: bool = False) -> List[Holding]:
        """Fetch holdings, serving from cache if valid or querying broker adapter."""
        with self._lock:
            cache_key = "portfolio:holdings"
            if not force_refresh:
                cached = self.cache.get(cache_key)
                if cached is not None:
                    return cached

            # Query adapter
            try:
                raw = self.adapter.get_holdings()
            except Exception as e:
                logger.warning(f"Failed to fetch holdings from broker adapter: {str(e)}")
                raw = []

            holdings = self.holdings_service.parse_holdings(raw)
            self._cached_holdings = holdings
            self.cache.set(cache_key, holdings, ttl_seconds=self.TTL_HOLDINGS)
            return holdings

    def get_positions(
        self,
        position_type: PositionType = PositionType.NET,
        force_refresh: bool = False,
    ) -> List[Position]:
        """Fetch positions, serving from cache if valid or querying broker adapter."""
        with self._lock:
            cache_key = f"portfolio:positions:{position_type.value.lower()}"
            if not force_refresh:
                cached = self.cache.get(cache_key)
                if cached is not None:
                    return cached

            # Query adapter
            try:
                raw = self.adapter.get_positions()
            except Exception as e:
                logger.warning(f"Failed to fetch positions from broker adapter: {str(e)}")
                raw = []

            positions = self.positions_service.parse_positions(
                raw, position_type=position_type
            )
            # Register in MTMEngine for live tick tracking
            self.mtm_engine.set_positions(positions)
            self.cache.set(cache_key, positions, ttl_seconds=self.TTL_POSITIONS)
            return positions

    def get_margins(self, force_refresh: bool = False) -> MarginSummary:
        """Fetch account margin limits and cash balances."""
        with self._lock:
            cache_key = "portfolio:margins"
            if not force_refresh:
                cached = self.cache.get(cache_key)
                if cached is not None:
                    return cached

            try:
                raw = self.adapter.get_margins()
            except Exception as e:
                logger.warning(f"Failed to fetch margins from broker adapter: {str(e)}")
                raw = {}

            margins = self.margin_service.parse_margins(raw)
            self._cached_margins = margins
            self.cache.set(cache_key, margins, ttl_seconds=self.TTL_MARGINS)
            return margins

    def get_summary(self, force_refresh: bool = False) -> PortfolioSummary:
        """
        Aggregate high-level portfolio metrics combining holdings, positions, MTM, and margins.
        """
        with self._lock:
            holdings = self.get_holdings(force_refresh=force_refresh)
            positions = self.get_positions(force_refresh=force_refresh)
            margins = self.get_margins(force_refresh=force_refresh)

            # Recalculate live MTM
            unrealized_mtm = self.mtm_engine.recalculate_all()
            realized_pnl = self.mtm_engine.get_total_realized_pnl()
            total_trading_pnl = realized_pnl + unrealized_mtm

            # Holdings totals
            tot_invested = sum(h.invested_value for h in holdings)
            tot_holdings_curr = sum(h.current_value for h in holdings)
            holdings_unrealized = tot_holdings_curr - tot_invested
            holdings_unrealized_pct = (
                (holdings_unrealized / tot_invested * 100.0) if tot_invested > 0 else 0.0
            )
            holdings_day_pnl = sum(h.day_pnl for h in holdings)

            total_portfolio_pnl = holdings_unrealized + total_trading_pnl
            retrieved_ts = datetime.now(timezone.utc).isoformat()
            now_epoch = time.time()

            summary = PortfolioSummary(
                total_invested_value=tot_invested,
                current_holdings_value=tot_holdings_curr,
                holdings_unrealized_pnl=holdings_unrealized,
                holdings_unrealized_pnl_pct=holdings_unrealized_pct,
                holdings_day_pnl=holdings_day_pnl,
                realized_pnl=realized_pnl,
                unrealized_mtm=unrealized_mtm,
                total_trading_pnl=total_trading_pnl,
                total_portfolio_pnl=total_portfolio_pnl,
                available_cash=margins.available_cash,
                total_margin_available=margins.total_margin_available,
                total_margin_used=margins.total_margin_used,
                margin_utilization_percent=margins.margin_utilization_percent,
                open_positions_count=self.mtm_engine.get_open_positions_count(),
                total_holdings_count=len(holdings),
                source_timestamp=margins.source_timestamp,
                retrieved_timestamp=retrieved_ts,
                updated_at=now_epoch,
            )
            return summary

    def force_refresh(self) -> PortfolioSummary:
        """
        Bypasses TTL caches, forces broker re-query, and publishes PORTFOLIO_REFRESHED event.
        """
        with self._lock:
            # Invalidate all portfolio partitions
            self.cache.delete("portfolio:holdings")
            self.cache.delete("portfolio:positions:net")
            self.cache.delete("portfolio:positions:day")
            self.cache.delete("portfolio:margins")

            summary = self.get_summary(force_refresh=True)

            publish(
                PORTFOLIO_REFRESHED,
                {
                    "total_portfolio_pnl": summary.total_portfolio_pnl,
                    "unrealized_mtm": summary.unrealized_mtm,
                    "available_cash": summary.available_cash,
                    "timestamp": summary.retrieved_timestamp,
                },
            )

            audit_logger.record(
                category=AuditCategory.BROKER,
                action="PORTFOLIO_SYNC",
                actor="portfolio_service",
                correlation_id=get_correlation_id(),
                request_id=get_request_id(),
                details={"pnl": summary.total_portfolio_pnl, "cash": summary.available_cash},
            )

            return summary


# Global Singleton Portfolio Service
portfolio_service = PortfolioService()
