"""
Option Chain Strategy Template Builder.
Phase 10: Option Chain Workbench.
Converts option chain interactive strike selections and one-click template macros
into Phase 9 compliant Multi-Leg Basket and BasketLeg payloads.
"""

from typing import Any, Dict, List, Optional
import uuid

from app.baskets.models.basket import BasketExecutionMode, BasketFailurePolicy, StrategyType
from app.orders.models.order import OrderSide, OrderType, ProductType


class OptionStrategyBuilderService:
    """
    Constructs Phase 9 compliant Basket structures from Option Chain interactive inputs.
    Eliminates manual contract symbol entry and enforces structural invariants before submission.
    """

    @staticmethod
    def build_custom_leg(
        trading_symbol: str,
        side: str,
        quantity: int,
        price: float = 0.0,
        exchange_segment: str = "nse_fo",
        instrument_token: str = "",
        product_type: str = "MIS",
        order_type: str = "LIMIT",
        depends_on_leg_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Construct an individual BasketLeg dictionary."""
        return {
            "leg_id": str(uuid.uuid4()),
            "trading_symbol": trading_symbol,
            "exchange_segment": exchange_segment,
            "instrument_token": str(instrument_token),
            "side": side.upper(),
            "order_type": order_type.upper(),
            "product_type": product_type.upper(),
            "quantity": quantity,
            "price": round(float(price), 2),
            "trigger_price": 0.0,
            "validity": "DAY",
            "depends_on_leg_index": depends_on_leg_index,
        }

    @classmethod
    def build_bull_call_spread(
        cls,
        underlying: str,
        expiry_token: str,
        buy_strike: float,
        sell_strike: float,
        lot_size: int,
        lots: int = 1,
        buy_price: float = 100.0,
        sell_price: float = 40.0,
        product_type: str = "MIS",
    ) -> Dict[str, Any]:
        """Construct Bull Call Spread: Buy Lower Call + Sell Higher Call."""
        qty = lot_size * lots
        leg0_sym = f"{underlying}{expiry_token}{int(buy_strike)}CE"
        leg1_sym = f"{underlying}{expiry_token}{int(sell_strike)}CE"

        legs = [
            cls.build_custom_leg(leg0_sym, "BUY", qty, buy_price, product_type=product_type),
            cls.build_custom_leg(leg1_sym, "SELL", qty, sell_price, product_type=product_type),
        ]

        return {
            "client_basket_id": f"BCS_{underlying}_{uuid.uuid4().hex[:8]}",
            "name": f"{underlying} Bull Call Spread {int(buy_strike)}/{int(sell_strike)}",
            "strategy_type": StrategyType.BULL_CALL_SPREAD.value,
            "strategy_version": "BULL_CALL_SPREAD_V1",
            "basket_execution_mode": BasketExecutionMode.SEQUENTIAL.value,
            "failure_policy": BasketFailurePolicy.ABORT_REMAINING.value,
            "legs": legs,
        }

    @classmethod
    def build_bear_put_spread(
        cls,
        underlying: str,
        expiry_token: str,
        buy_strike: float,
        sell_strike: float,
        lot_size: int,
        lots: int = 1,
        buy_price: float = 100.0,
        sell_price: float = 40.0,
        product_type: str = "MIS",
    ) -> Dict[str, Any]:
        """Construct Bear Put Spread: Buy Higher Put + Sell Lower Put."""
        qty = lot_size * lots
        leg0_sym = f"{underlying}{expiry_token}{int(buy_strike)}PE"
        leg1_sym = f"{underlying}{expiry_token}{int(sell_strike)}PE"

        legs = [
            cls.build_custom_leg(leg0_sym, "BUY", qty, buy_price, product_type=product_type),
            cls.build_custom_leg(leg1_sym, "SELL", qty, sell_price, product_type=product_type),
        ]

        return {
            "client_basket_id": f"BPS_{underlying}_{uuid.uuid4().hex[:8]}",
            "name": f"{underlying} Bear Put Spread {int(buy_strike)}/{int(sell_strike)}",
            "strategy_type": StrategyType.BEAR_PUT_SPREAD.value,
            "strategy_version": "BEAR_PUT_SPREAD_V1",
            "basket_execution_mode": BasketExecutionMode.SEQUENTIAL.value,
            "failure_policy": BasketFailurePolicy.ABORT_REMAINING.value,
            "legs": legs,
        }

    @classmethod
    def build_straddle(
        cls,
        underlying: str,
        expiry_token: str,
        strike: float,
        lot_size: int,
        is_short: bool = False,
        lots: int = 1,
        call_price: float = 100.0,
        put_price: float = 100.0,
        product_type: str = "MIS",
    ) -> Dict[str, Any]:
        """Construct Long or Short Straddle: Buy/Sell ATM Call + Put."""
        qty = lot_size * lots
        side = "SELL" if is_short else "BUY"
        strat = StrategyType.SHORT_STRADDLE if is_short else StrategyType.LONG_STRADDLE

        legs = [
            cls.build_custom_leg(f"{underlying}{expiry_token}{int(strike)}CE", side, qty, call_price, product_type=product_type),
            cls.build_custom_leg(f"{underlying}{expiry_token}{int(strike)}PE", side, qty, put_price, product_type=product_type),
        ]

        return {
            "client_basket_id": f"STRAD_{underlying}_{uuid.uuid4().hex[:8]}",
            "name": f"{underlying} {'Short' if is_short else 'Long'} Straddle {int(strike)}",
            "strategy_type": strat.value,
            "strategy_version": "STRADDLE_V1",
            "basket_execution_mode": BasketExecutionMode.SEQUENTIAL.value,
            "failure_policy": BasketFailurePolicy.ABORT_REMAINING.value,
            "legs": legs,
        }

    @classmethod
    def build_iron_condor(
        cls,
        underlying: str,
        expiry_token: str,
        put_buy_strike: float,
        put_sell_strike: float,
        call_sell_strike: float,
        call_buy_strike: float,
        lot_size: int,
        lots: int = 1,
        put_buy_price: float = 15.0,
        put_sell_price: float = 50.0,
        call_sell_price: float = 50.0,
        call_buy_price: float = 15.0,
        product_type: str = "MIS",
    ) -> Dict[str, Any]:
        """
        Construct 4-Leg Iron Condor:
        Leg 0: Buy Put Wing (Root)
        Leg 1: Sell Put Body (Depends on Leg 0)
        Leg 2: Buy Call Wing (Root)
        Leg 3: Sell Call Body (Depends on Leg 2)
        """
        qty = lot_size * lots

        legs = [
            cls.build_custom_leg(f"{underlying}{expiry_token}{int(put_buy_strike)}PE", "BUY", qty, put_buy_price, product_type=product_type, depends_on_leg_index=None),
            cls.build_custom_leg(f"{underlying}{expiry_token}{int(put_sell_strike)}PE", "SELL", qty, put_sell_price, product_type=product_type, depends_on_leg_index=0),
            cls.build_custom_leg(f"{underlying}{expiry_token}{int(call_buy_strike)}CE", "BUY", qty, call_buy_price, product_type=product_type, depends_on_leg_index=None),
            cls.build_custom_leg(f"{underlying}{expiry_token}{int(call_sell_strike)}CE", "SELL", qty, call_sell_price, product_type=product_type, depends_on_leg_index=2),
        ]

        return {
            "client_basket_id": f"IC_{underlying}_{uuid.uuid4().hex[:8]}",
            "name": f"{underlying} Iron Condor {int(put_buy_strike)}/{int(put_sell_strike)}/{int(call_sell_strike)}/{int(call_buy_strike)}",
            "strategy_type": StrategyType.IRON_CONDOR.value,
            "strategy_version": "IRON_CONDOR_V1",
            "basket_execution_mode": BasketExecutionMode.DEPENDENCY.value,
            "failure_policy": BasketFailurePolicy.ABORT_REMAINING.value,
            "legs": legs,
        }


# Global singleton instance
option_strategy_builder = OptionStrategyBuilderService()

