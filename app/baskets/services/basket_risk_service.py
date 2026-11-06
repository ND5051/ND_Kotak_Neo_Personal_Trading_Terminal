from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.baskets.models.basket import Basket, BasketState, StrategyType
from app.baskets.repositories.basket_repository import (
    BasketRepositoryInterface,
    basket_repository,
)
from app.core.exceptions import BasketRiskException
from app.orders.models.order import OrderSide


class BasketRiskService:
    """
    Multi-Leg Pre-Trade Capital and Exposure Risk Gatekeeper.
    Evaluates aggregate margin sufficiency (+10% safety buffer),
    gross notional ceilings, account daily drawdown floor, and open basket quotas.
    """

    MAX_GROSS_BASKET_VALUE = 2000000.0   # ₹20 Lakh gross notional ceiling
    MAX_DAILY_DRAWDOWN_LIMIT = -20000.0   # ₹20,000 account drawdown floor
    MAX_OPEN_BASKETS = 5                 # Maximum concurrent executing/reconciling baskets
    MARGIN_SAFETY_BUFFER = 1.10          # +10% upfront buffer

    def __init__(self, repository: Optional[BasketRepositoryInterface] = None) -> None:
        self.repository = repository or basket_repository

    def assess_basket_risk(
        self,
        basket: Basket,
        available_margin: float = 500000.0,
        current_daily_pnl: float = 0.0,
    ) -> Tuple[bool, Dict[str, Any], List[str]]:
        """
        Assess pre-trade risk constraints across all basket legs.
        Returns (passed, margin_snapshot, error_list).
        """
        errors: List[str] = []

        # 1. Gross Basket Notional Value Ceiling
        gross_value = sum(leg.quantity * (leg.price if leg.price > 0 else 100.0) for leg in basket.legs)
        if gross_value > self.MAX_GROSS_BASKET_VALUE:
            errors.append(
                f"Gross basket notional value (₹{gross_value:,.2f}) exceeds single basket ceiling of ₹{self.MAX_GROSS_BASKET_VALUE:,.2f}."
            )

        # 2. Daily Drawdown Floor Check
        if current_daily_pnl <= self.MAX_DAILY_DRAWDOWN_LIMIT:
            errors.append(
                f"Account daily drawdown (-₹{abs(current_daily_pnl):,.2f}) breaches maximum loss floor of -₹{abs(self.MAX_DAILY_DRAWDOWN_LIMIT):,.2f}. Basket execution blocked."
            )

        # 3. Concurrent Open Basket Limit
        active_baskets = self.repository.find_baskets(
            user_id=basket.user_id,
            status=BasketState.EXECUTING,
            limit=50,
        )
        reconciling_baskets = self.repository.find_baskets(
            user_id=basket.user_id,
            status=BasketState.RECONCILING,
            limit=50,
        )
        total_open = len(active_baskets) + len(reconciling_baskets)
        if total_open >= self.MAX_OPEN_BASKETS:
            errors.append(
                f"Active open basket limit ({self.MAX_OPEN_BASKETS}) reached. Currently active: {total_open}."
            )

        # 4. Aggregate Margin Sufficiency (+10% safety buffer)
        estimated_margin = self._estimate_strategy_margin(basket)
        buffered_margin = estimated_margin * self.MARGIN_SAFETY_BUFFER

        if buffered_margin > available_margin:
            errors.append(
                f"Insufficient margin: Required ₹{buffered_margin:,.2f} (including +10% buffer) exceeds available margin ₹{available_margin:,.2f}."
            )

        # Build margin snapshot
        margin_snapshot = {
            "gross_notional_value": round(gross_value, 2),
            "estimated_margin": round(estimated_margin, 2),
            "buffered_margin": round(buffered_margin, 2),
            "available_margin": round(available_margin, 2),
            "margin_headroom": round(available_margin - buffered_margin, 2),
            "current_daily_pnl": round(current_daily_pnl, 2),
            "open_baskets_count": total_open,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        basket.estimated_margin = estimated_margin
        basket.margin_snapshot = margin_snapshot
        basket.validation_timestamp = margin_snapshot["timestamp"]

        return len(errors) == 0, margin_snapshot, errors

    def _estimate_strategy_margin(self, basket: Basket) -> float:
        """
        Estimate upfront margin based on strategy definition.
        Debit strategies require net premium.
        Credit spreads / Iron Condors require wing spread width.
        Naked shorts require full margin.
        """
        strat = basket.strategy_type
        if not basket.legs:
            return 0.0

        # Spreads: Iron Condor or Butterfly
        if strat in (StrategyType.IRON_CONDOR, StrategyType.IRON_BUTTERFLY):
            # Wing spread width * quantity
            put_legs = [l for l in basket.legs if "PE" in l.trading_symbol]
            if len(put_legs) == 2:
                strikes = sorted([self._extract_strike(l.trading_symbol) for l in put_legs])
                wing_width = strikes[1] - strikes[0]
                qty = put_legs[0].quantity
                return wing_width * qty

        # Debit spreads: Bull Call or Bear Put
        if strat in (StrategyType.BULL_CALL_SPREAD, StrategyType.BEAR_PUT_SPREAD):
            buy_leg = next((l for l in basket.legs if l.side == OrderSide.BUY), None)
            sell_leg = next((l for l in basket.legs if l.side == OrderSide.SELL), None)
            if buy_leg and sell_leg:
                net_debit = max(0.0, buy_leg.price - sell_leg.price)
                return net_debit * buy_leg.quantity

        # Long options: Net premium
        if strat in (StrategyType.LONG_STRADDLE, StrategyType.LONG_STRANGLE, StrategyType.PROTECTIVE_PUT):
            return sum(l.quantity * l.price for l in basket.legs if l.side == OrderSide.BUY)

        # Naked short: standard ₹1.5L per lot estimate
        if strat in (StrategyType.SHORT_STRADDLE, StrategyType.SHORT_STRANGLE):
            total_short_qty = sum(l.quantity for l in basket.legs if l.side == OrderSide.SELL)
            return (total_short_qty / 25.0) * 150000.0

        # Default fallback: gross notional / 5 (approx 20% margin)
        return sum(l.quantity * (l.price if l.price > 0 else 100.0) for l in basket.legs) * 0.20

    @staticmethod
    def _extract_strike(symbol: str) -> float:
        import re
        match = re.search(r"(\d+)(CE|PE)$", symbol.upper())
        return float(match.group(1)) if match else 0.0


# Global singleton
basket_risk_service = BasketRiskService()

