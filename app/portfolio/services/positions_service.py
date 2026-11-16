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
                row.get("tok")
                or row.get("token")
                or row.get("instrumentToken")
                or row.get("pSymbol")
                or row.get("scripToken")
                or ""
            ).strip()

            symbol_raw = (
                row.get("trdSym")
                or row.get("tradingSymbol")
                or row.get("sym")
                or row.get("pTrdSymbol")
                or row.get("dispSym")
                or token
            )
            symbol = str(symbol_raw).strip()

            segment = str(
                row.get("exSeg")
                or row.get("exchangeSegment")
                or row.get("segment")
                or row.get("pSegment")
                or "nse_fo"
            ).strip().lower()

            # Product Code Resolution (Kotak Neo uses 'prod', 'type', 'prodType')
            prod_str = str(
                row.get("prod")
                or row.get("product")
                or row.get("prodType")
                or row.get("type")
                or row.get("pProduct")
                or "NRML"
            ).strip().upper()

            if prod_str in ("MIS", "INTRADAY"):
                product = ProductCode.MIS
            elif prod_str in ("CNC", "DELIVERY", "CASH"):
                product = ProductCode.CNC
            else:
                product = ProductCode.NRML

            # Quantity Resolution (Kotak Neo uses 'flBuyQty', 'buyQty', 'cfBuyQty')
            try:
                b_raw = row.get("flBuyQty")
                if b_raw is None or (isinstance(b_raw, (int, float, str)) and float(b_raw or 0) == 0):
                    b_raw = row.get("buyQty") or row.get("cfBuyQty") or row.get("buyQuantity") or 0
                buy_qty = int(float(b_raw or 0))
            except (ValueError, TypeError):
                buy_qty = 0

            try:
                s_raw = row.get("flSellQty")
                if s_raw is None or (isinstance(s_raw, (int, float, str)) and float(s_raw or 0) == 0):
                    s_raw = row.get("sellQty") or row.get("cfSellQty") or row.get("sellQuantity") or 0
                sell_qty = int(float(s_raw or 0))
            except (ValueError, TypeError):
                sell_qty = 0

            # Direct Net Quantity check with fallback to buy_qty - sell_qty
            net_qty = None
            for q_key in ["qty", "netQty", "netQuantity", "flNetQty", "net_qty"]:
                val = row.get(q_key)
                if val is not None:
                    try:
                        net_qty = int(float(val))
                        break
                    except (ValueError, TypeError):
                        pass
            if net_qty is None:
                net_qty = buy_qty - sell_qty

            is_open = net_qty != 0

            # Amounts & Execution Prices
            # Kotak Neo reports total traded amounts in 'buyAmt' and 'sellAmt'
            try:
                b_amt_raw = row.get("buyAmt")
                if b_amt_raw is None or (isinstance(b_amt_raw, (int, float, str)) and float(b_amt_raw or 0) == 0):
                    b_amt_raw = row.get("buyAmount") or row.get("cfBuyAmt") or 0.0
                buy_amount = float(b_amt_raw or 0.0)
            except (ValueError, TypeError):
                buy_amount = 0.0

            try:
                s_amt_raw = row.get("sellAmt")
                if s_amt_raw is None or (isinstance(s_amt_raw, (int, float, str)) and float(s_amt_raw or 0) == 0):
                    s_amt_raw = row.get("sellAmount") or row.get("cfSellAmt") or 0.0
                sell_amount = float(s_amt_raw or 0.0)
            except (ValueError, TypeError):
                sell_amount = 0.0

            # Compute or extract average buy price
            if buy_qty > 0 and buy_amount > 0:
                avg_buy_px = buy_amount / buy_qty
            else:
                try:
                    avg_buy_px = float(
                        row.get("buyAvgPrc")
                        or row.get("buyPrice")
                        or row.get("avgBuyPrice")
                        or 0.0
                    )
                except (ValueError, TypeError):
                    avg_buy_px = 0.0

            if buy_amount == 0.0 and buy_qty > 0 and avg_buy_px > 0:
                buy_amount = buy_qty * avg_buy_px

            # Compute or extract average sell price
            if sell_qty > 0 and sell_amount > 0:
                avg_sell_px = sell_amount / sell_qty
            else:
                try:
                    avg_sell_px = float(
                        row.get("sellAvgPrc")
                        or row.get("sellPrice")
                        or row.get("avgSellPrice")
                        or 0.0
                    )
                except (ValueError, TypeError):
                    avg_sell_px = 0.0

            if sell_amount == 0.0 and sell_qty > 0 and avg_sell_px > 0:
                sell_amount = sell_qty * avg_sell_px

            try:
                close_px = float(
                    row.get("closePrice")
                    or row.get("prevClose")
                    or row.get("closingPrice")
                    or row.get("clsPrc")
                    or 0.0
                )
            except (ValueError, TypeError):
                close_px = 0.0

            try:
                multiplier = int(row.get("multiplier") or row.get("lotSz") or 1)
            except (ValueError, TypeError):
                multiplier = 1

            # Closed quantity and Realized PnL
            # For completely closed positions, sell_amount - buy_amount equals closed PnL exactly
            closed_qty = min(buy_qty, sell_qty)
            if closed_qty > 0:
                if buy_qty == sell_qty and buy_amount > 0 and sell_amount > 0:
                    realized_pnl = sell_amount - buy_amount
                else:
                    realized_pnl = closed_qty * (avg_sell_px - avg_buy_px)
            else:
                realized_pnl = 0.0

            # Live current price from PriceEngine or broker payload
            quote = self.price_engine.get_quote(token, segment)
            if quote and quote.ltp > 0:
                current_price = quote.ltp
            else:
                try:
                    current_price = float(
                        row.get("lp")
                        or row.get("lastPrice")
                        or row.get("ltp")
                        or row.get("actPrc")
                        or close_px
                    )
                except (ValueError, TypeError):
                    current_price = close_px

            if current_price == 0.0 and is_open:
                if net_qty > 0 and avg_buy_px > 0:
                    current_price = avg_buy_px
                elif net_qty < 0 and avg_sell_px > 0:
                    current_price = avg_sell_px

            # Calculate Unrealized MTM
            is_open = net_qty != 0
            if is_open:
                if net_qty > 0:
                    unrealized_pnl = net_qty * (current_price - avg_buy_px)
                elif net_qty < 0:
                    unrealized_pnl = abs(net_qty) * (avg_sell_px - current_price)
                else:
                    unrealized_pnl = 0.0
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

    def compute_paper_positions(
        self,
        user_id: Optional[int] = None,
        position_type: PositionType = PositionType.NET,
    ) -> List[Position]:
        """
        Synthesize trading positions from local paper orders and trade executions.
        Aggregates filled paper orders, computes weighted average execution prices,
        binds live quotes from PriceEngine, and calculates open MTM and realized PnL.
        """
        from app.orders.models.order import OrderStatus, OrderSide
        from app.orders.repositories.order_repository import order_repository

        try:
            orders = order_repository.find_orders(user_id=user_id, limit=500)
        except Exception as e:
            logger.warning(f"Error querying orders for paper positions: {str(e)}")
            return []

        # Filter strictly for FILLED paper orders (broker_order_id starts with PAPER_ or mode == PAPER)
        paper_filled = [
            o for o in orders
            if o.status == OrderStatus.FILLED
            and (str(o.broker_order_id or "").startswith("PAPER_") or getattr(o, "mode", "") == "PAPER")
        ]

        if not paper_filled:
            return []

        # Group by (instrument_token, exchange_segment, trading_symbol, product_type)
        grouped: Dict[Tuple[str, str, str, str], List[Any]] = {}
        for o in paper_filled:
            tok = str(o.instrument_token or "").strip()
            seg = str(o.exchange_segment or "nse_cm").strip().lower()
            sym = str(o.trading_symbol or "").strip()
            prod = str(o.product_type.value if hasattr(o.product_type, "value") else (o.product_type or "MIS")).strip().upper()
            grp_key = (tok, seg, sym, prod)
            grouped.setdefault(grp_key, []).append(o)

        positions: List[Position] = []
        retrieved_ts = datetime.now(timezone.utc).isoformat()
        now_epoch = time.time()

        for (token, segment, symbol, prod_str), ord_list in grouped.items():
            buy_qty = 0
            buy_amt = 0.0
            sell_qty = 0
            sell_amt = 0.0

            for o in ord_list:
                side_val = o.side.value if hasattr(o.side, "value") else str(o.side).upper()
                fill_qty = int(o.filled_quantity or 0)
                fill_prc = float(o.average_price or o.price or 0.0)

                if side_val in ("BUY", OrderSide.BUY.value):
                    buy_qty += fill_qty
                    buy_amt += fill_qty * fill_prc
                else:
                    sell_qty += fill_qty
                    sell_amt += fill_qty * fill_prc

            net_qty = buy_qty - sell_qty
            avg_buy = (buy_amt / buy_qty) if buy_qty > 0 else 0.0
            avg_sell = (sell_amt / sell_qty) if sell_qty > 0 else 0.0

            # Realized PnL on closed quantity
            closed_qty = min(buy_qty, sell_qty)
            realized_pnl = (avg_sell - avg_buy) * closed_qty if closed_qty > 0 else 0.0

            # Current price from live PriceEngine
            quote = self.price_engine.get_quote(token, segment)
            if quote and quote.ltp > 0:
                current_price = quote.ltp
            elif avg_buy > 0:
                current_price = avg_buy
            elif avg_sell > 0:
                current_price = avg_sell
            else:
                current_price = 0.0

            # Floating MTM on open quantity
            is_open = net_qty != 0
            if is_open:
                if net_qty > 0:
                    unrealized_pnl = (current_price - avg_buy) * net_qty
                else:
                    unrealized_pnl = (avg_sell - current_price) * abs(net_qty)
            else:
                unrealized_pnl = 0.0

            total_pnl = realized_pnl + unrealized_pnl

            # Product enum mapping
            if prod_str in ("CNC", "DELIVERY"):
                product_code = ProductCode.CNC
            elif prod_str in ("MIS", "INTRADAY"):
                product_code = ProductCode.MIS
            else:
                product_code = ProductCode.NRML

            pos = Position(
                instrument_token=token,
                exchange_segment=segment,
                trading_symbol=symbol,
                product=product_code,
                position_type=position_type,
                buy_quantity=buy_qty,
                buy_amount=buy_amt,
                average_buy_price=avg_buy,
                sell_quantity=sell_qty,
                sell_amount=sell_amt,
                average_sell_price=avg_sell,
                net_quantity=net_qty,
                multiplier=1,
                close_price=avg_buy if net_qty > 0 else avg_sell,
                current_price=current_price,
                realized_pnl=realized_pnl,
                unrealized_pnl=unrealized_pnl,
                total_pnl=total_pnl,
                is_open=is_open,
                source_timestamp=retrieved_ts,
                retrieved_timestamp=retrieved_ts,
                updated_at=now_epoch,
            )
            positions.append(pos)

        return positions

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
