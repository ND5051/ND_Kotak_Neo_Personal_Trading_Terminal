"""
Holdings Service.
Phase 6: Portfolio Foundation.
Reconciles Demat equity holdings from Kotak Neo, calculates custody valuation,
and benchmarks day PnL.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional

from app.core.audit import AuditCategory, audit_logger
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import HOLDINGS_RECONCILED
from app.logging.logger import get_logger
from app.market_watch.services.price_engine import (
    MarketWatchPriceEngine,
    price_engine,
)
from app.portfolio.models.holding import Holding

logger = get_logger("app.portfolio.services.holdings_service")


class HoldingsService:
    """
    Parses and calculates Demat holdings from broker responses.
    Integrates with MarketWatchPriceEngine to reflect real-time equity valuation.
    """

    def __init__(
        self, prices: Optional[MarketWatchPriceEngine] = None
    ) -> None:
        self.price_engine = prices or price_engine

    def parse_holdings(
        self, raw_response: Any, source_timestamp: Optional[str] = None
    ) -> List[Holding]:
        """
        Parse polymorphic Kotak Neo holdings response into normalized Holding domain objects.
        Safely extracts records from nested data structures.
        """
        records = self._extract_records(raw_response)
        retrieved_ts = datetime.now(timezone.utc).isoformat()
        now_epoch = time.time()
        holdings: List[Holding] = []

        for row in records:
            if not isinstance(row, dict):
                continue

            token = str(
                row.get("instrumentToken")
                or row.get("token")
                or row.get("pSymbol")
                or row.get("scripToken")
                or ""
            ).strip()

            symbol = str(
                row.get("tradingSymbol")
                or row.get("trdSym")
                or row.get("symbol")
                or row.get("pTrdSymbol")
                or token
            ).strip()

            segment = str(
                row.get("exchangeSegment")
                or row.get("segment")
                or row.get("pSegment")
                or "nse_cm"
            ).strip().lower()

            isin = str(row.get("isin") or row.get("isinCode") or "").strip()

            # Quantity resolution
            try:
                total_qty = int(
                    float(
                        row.get("totalQty")
                        or row.get("holdingQuantity")
                        or row.get("quantity")
                        or row.get("qty")
                        or 0
                    )
                )
            except (ValueError, TypeError):
                total_qty = 0

            try:
                settled_qty = int(
                    float(
                        row.get("settledQty")
                        or row.get("dpQty")
                        or row.get("settledQuantity")
                        or total_qty
                    )
                )
            except (ValueError, TypeError):
                settled_qty = total_qty

            try:
                t1_qty = int(float(row.get("t1Qty") or row.get("unsettledQty") or 0))
            except (ValueError, TypeError):
                t1_qty = 0

            try:
                pledged_qty = int(float(row.get("pledgedQty") or row.get("collateralQty") or 0))
            except (ValueError, TypeError):
                pledged_qty = 0

            # Prices
            try:
                avg_price = float(
                    row.get("averagePrice")
                    or row.get("avgPrice")
                    or row.get("buyPrice")
                    or row.get("costPrice")
                    or 0.0
                )
            except (ValueError, TypeError):
                avg_price = 0.0

            try:
                close_price = float(
                    row.get("closePrice")
                    or row.get("prevClose")
                    or row.get("closingPrice")
                    or avg_price
                )
            except (ValueError, TypeError):
                close_price = avg_price

            # Fetch live price from PriceEngine if available, else fallback to broker payload
            quote = self.price_engine.get_quote(token, segment)
            if quote and quote.ltp > 0:
                current_price = quote.ltp
            else:
                try:
                    current_price = float(
                        row.get("lastPrice")
                        or row.get("ltp")
                        or row.get("currentPrice")
                        or close_price
                    )
                except (ValueError, TypeError):
                    current_price = close_price

            invested_val = total_qty * avg_price
            current_val = total_qty * current_price
            unrealized_pnl = current_val - invested_val
            unrealized_pct = (
                (unrealized_pnl / invested_val * 100.0) if invested_val > 0 else 0.0
            )

            day_pnl = total_qty * (current_price - close_price)
            day_pct = (
                ((current_price - close_price) / close_price * 100.0)
                if close_price > 0
                else 0.0
            )

            collateral_elig = bool(row.get("collateralEligible", True))

            src_ts = (
                source_timestamp
                or row.get("timestamp")
                or row.get("sourceTimestamp")
            )

            holdings.append(
                Holding(
                    instrument_token=token,
                    exchange_segment=segment,
                    trading_symbol=symbol,
                    isin=isin,
                    total_quantity=total_qty,
                    settled_quantity=settled_qty,
                    t1_quantity=t1_qty,
                    pledged_quantity=pledged_qty,
                    average_price=avg_price,
                    invested_value=invested_val,
                    current_price=current_price,
                    current_value=current_val,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_percent=unrealized_pct,
                    close_price=close_price,
                    day_pnl=day_pnl,
                    day_pnl_percent=day_pct,
                    collateral_eligible=collateral_elig,
                    source_timestamp=src_ts,
                    retrieved_timestamp=retrieved_ts,
                    updated_at=now_epoch,
                )
            )

        # Audit and Notify
        tot_invested = sum(h.invested_value for h in holdings)
        tot_current = sum(h.current_value for h in holdings)

        publish(
            HOLDINGS_RECONCILED,
            {
                "total_holdings": len(holdings),
                "invested_value": tot_invested,
                "current_value": tot_current,
                "timestamp": retrieved_ts,
            },
        )

        audit_logger.record(
            category=AuditCategory.BROKER,
            action="HOLDINGS_RECONCILED",
            actor="holdings_service",
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={
                "count": len(holdings),
                "total_invested": tot_invested,
                "total_current": tot_current,
            },
        )

        return holdings

    def _extract_records(self, payload: Any) -> List[Dict[str, Any]]:
        """Polymorphic unpacker for Kotak Neo holdings responses."""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ["data", "result", "dataList", "holdings"]:
                val = payload.get(key)
                if isinstance(val, list):
                    return val
                if isinstance(val, dict):
                    inner = val.get("data") or val.get("result") or val.get("holdings")
                    if isinstance(inner, list):
                        return inner
        return []


# Global Singleton Holdings Service
holdings_service = HoldingsService()
