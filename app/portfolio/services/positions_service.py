"""
Positions Service & State Reconciliation.
Phase 6: Portfolio Foundation.
Implements resilient polymorphic parsing and the Cardinal Golden Rule of State Reconciliation
(Absence of Data != Value Zero).
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional

from app.core.audit import AuditCategory, audit_logger
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import POSITIONS_RECONCILED
from app.logging.logger import get_logger
from app.market_watch.services.price_engine import (
    MarketWatchPriceEngine,
    price_engine,
)
from app.portfolio.models.position import Position, PositionType, ProductCode

logger = get_logger("app.portfolio.services.positions_service")


class PositionsService:
    """
    Parses Day and Net positions from Kotak Neo broker endpoints.
    Enforces safe state reconciliation without assuming zero on missing records.
    """

    def __init__(
        self, prices: Optional[MarketWatchPriceEngine] = None
    ) -> None:
        self.price_engine = prices or price_engine

    def parse_positions(
        self,
        raw_response: Any,
        position_type: PositionType = PositionType.NET,
        source_timestamp: Optional[str] = None,
    ) -> List[Position]:
        """
        Parse polymorphic Kotak Neo positions response into normalized Position domain objects.
        Safely computes Realized PnL and initializes Unrealized MTM.
        """
        records = self._extract_records(raw_response)
        retrieved_ts = datetime.now(timezone.utc).isoformat()
        now_epoch = time.time()
        positions: List[Position] = []

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

            symbol_raw = (
                row.get("tradingSymbol")
                or row.get("trdSym")
                or row.get("symbol")
                or row.get("pTrdSymbol")
                or row.get("dispSym")
                or token
            )
            symbol = str(symbol_raw).strip()

            segment = str(
                row.get("exchangeSegment")
                or row.get("segment")
                or row.get("pSegment")
                or "nse_fo"
            ).strip().lower()

            # Product Code Resolution
            prod_str = str(
                row.get("product")
                or row.get("prodType")
                or row.get("pProduct")
                or "NRML"
            ).strip().upper()

            if prod_str in ("MIS", "INTRADAY"):
                product = ProductCode.MIS
            elif prod_str in ("CNC", "DELIVERY"):
                product = ProductCode.CNC
            else:
                product = ProductCode.NRML

            # Quantity Resolution
            try:
                buy_qty = int(float(row.get("flBuyQty") or row.get("buyQty") or row.get("buyQuantity") or 0))
            except (ValueError, TypeError):
                buy_qty = 0

            try:
                sell_qty = int(float(row.get("flSellQty") or row.get("sellQty") or row.get("sellQuantity") or 0))
            except (ValueError, TypeError):
                sell_qty = 0

            # Direct Net Quantity check with fallback to buy_qty - sell_qty
            net_qty = None
            for q_key in ["netQty", "netQuantity", "flNetQty", "net_qty", "qty"]:
                val = row.get(q_key)
                if val is not None:
                    try:
                        net_qty = int(float(val))
                        break
                    except (ValueError, TypeError):
                        pass
            if net_qty is None:
                net_qty = buy_qty - sell_qty

            # Prices
            try:
                avg_buy_px = float(
                    row.get("buyAvgPrc")
                    or row.get("buyPrice")
                    or row.get("avgBuyPrice")
                    or 0.0
                )
            except (ValueError, TypeError):
                avg_buy_px = 0.0

            try:
                avg_sell_px = float(
                    row.get("sellAvgPrc")
                    or row.get("sellPrice")
                    or row.get("avgSellPrice")
                    or 0.0
                )
            except (ValueError, TypeError):
                avg_sell_px = 0.0

            try:
                close_px = float(
                    row.get("closePrice")
                    or row.get("prevClose")
                    or row.get("closingPrice")
                    or 0.0
                )
            except (ValueError, TypeError):
                close_px = 0.0

            try:
                multiplier = int(row.get("multiplier") or 1)
            except (ValueError, TypeError):
                multiplier = 1

            buy_amount = buy_qty * avg_buy_px
            sell_amount = sell_qty * avg_sell_px

            # Closed quantity and Realized PnL
            closed_qty = min(buy_qty, sell_qty)
            realized_pnl = closed_qty * (avg_sell_px - avg_buy_px)

            # Live current price from PriceEngine or broker payload
            quote = self.price_engine.get_quote(token, segment)
            if quote and quote.ltp > 0:
                current_price = quote.ltp
            else:
                try:
                    current_price = float(
                        row.get("lastPrice")
                        or row.get("ltp")
                        or row.get("actPrc")
                        or close_px
                    )
                except (ValueError, TypeError):
                    current_price = close_px

            # Calculate Unrealized MTM
            is_open = net_qty != 0
            if net_qty > 0:
                unrealized_pnl = net_qty * (current_price - avg_buy_px)
            elif net_qty < 0:
                unrealized_pnl = abs(net_qty) * (avg_sell_px - current_price)
            else:
                unrealized_pnl = 0.0

            total_pnl = realized_pnl + unrealized_pnl

            src_ts = (
                source_timestamp
                or row.get("timestamp")
                or row.get("sourceTimestamp")
            )

            positions.append(
                Position(
                    instrument_token=token,
                    exchange_segment=segment,
                    trading_symbol=symbol,
                    product=product,
                    position_type=position_type,
                    buy_quantity=buy_qty,
                    buy_amount=buy_amount,
                    average_buy_price=avg_buy_px,
                    sell_quantity=sell_qty,
                    sell_amount=sell_amount,
                    average_sell_price=avg_sell_px,
                    net_quantity=net_qty,
                    multiplier=multiplier,
                    close_price=close_px,
                    current_price=current_price,
                    realized_pnl=realized_pnl,
                    unrealized_pnl=unrealized_pnl,
                    total_pnl=total_pnl,
                    is_open=is_open,
                    source_timestamp=src_ts,
                    retrieved_timestamp=retrieved_ts,
                    updated_at=now_epoch,
                )
            )

        # Audit and Notify
        open_count = sum(1 for p in positions if p.is_open)
        closed_count = len(positions) - open_count
        tot_realized = sum(p.realized_pnl for p in positions)

        publish(
            POSITIONS_RECONCILED,
            {
                "open_positions": open_count,
                "closed_positions": closed_count,
                "realized_pnl": tot_realized,
                "timestamp": retrieved_ts,
            },
        )

        audit_logger.record(
            category=AuditCategory.BROKER,
            action="POSITIONS_RECONCILED",
            actor="positions_service",
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={
                "open": open_count,
                "closed": closed_count,
                "realized_pnl": tot_realized,
            },
        )

        return positions

    def get_net_position_for_symbol(
        self, raw_positions_response: Any, target_symbol: str
    ) -> Optional[int]:
        """
        Cardinal Golden Rule:
        Returns:
            int: Net open quantity (+ for Long, - for Short, 0 if confirmed closed)
            None: If undetermined, API errored, or symbol missing from confirmed response
        """
        if raw_positions_response is None or not target_symbol:
            return None

        # Fail safe on error responses
        if isinstance(raw_positions_response, dict):
            if any(err_key in raw_positions_response for err_key in ("error", "Error", "Error Message")):
                return None

        records = self._extract_records(raw_positions_response)
        clean_target = "".join(str(target_symbol).strip().upper().split())

        for p in records:
            if not isinstance(p, dict):
                continue

            sym_raw = (
                p.get("trdSym")
                or p.get("tradingSymbol")
                or p.get("symbol")
                or p.get("pTrdSymbol")
                or p.get("dispSym")
                or ""
            )
            clean_sym = "".join(str(sym_raw).strip().upper().split())

            if clean_sym == clean_target or clean_target in clean_sym or clean_sym in clean_target:
                for q_key in ["netQty", "netQuantity", "flNetQty", "net_qty", "qty"]:
                    raw_val = p.get(q_key)
                    if raw_val is not None:
                        try:
                            return int(float(raw_val))
                        except (ValueError, TypeError):
                            pass
                # Fallback to buy - sell
                try:
                    b = float(p.get("flBuyQty") or p.get("buyQty") or 0.0)
                    s = float(p.get("flSellQty") or p.get("sellQty") or 0.0)
                    return int(b - s)
                except (ValueError, TypeError):
                    return None

        # Symbol was not found in response: Return None (Undetermined), NEVER 0!
        return None

    def _extract_records(self, payload: Any) -> List[Dict[str, Any]]:
        """Polymorphic unpacker for Kotak Neo positions responses."""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ["data", "result", "dataList", "positions"]:
                val = payload.get(key)
                if isinstance(val, list):
                    return val
                if isinstance(val, dict):
                    inner = val.get("data") or val.get("result") or val.get("positions")
                    if isinstance(inner, list):
                        return inner
        return []


# Global Singleton Positions Service
positions_service = PositionsService()
