import re
from typing import Any, Dict, List, Optional, Tuple

from app.baskets.models.basket import Basket, BasketLeg, StrategyType
from app.orders.models.order import OrderSide, OrderType, ProductType
from app.orders.services.order_validation_service import order_validation_service


class StrategyValidationService:
    """
    Multi-Leg Option Strategy and Basket Structural Validation Engine.
    Enforces exchange lot sizes, strike ladder invariants, expiry parity,
    and mathematical symmetry across supported option structures.
    """

    # Major index lot sizes (standard benchmark contracts)
    BENCHMARK_LOT_SIZES: Dict[str, int] = {
        "NIFTY": 25,
        "BANKNIFTY": 15,
        "FINNIFTY": 25,
        "MIDCPNIFTY": 50,
    }

    # Regex for standard Indian derivative option contracts (e.g. NIFTY26NOV24500CE, RELIANCE26NOV2500PE)
    OPTION_SYMBOL_PATTERN = re.compile(r"^([A-Z]+?)(\d{2}[A-Z]{3}|\d{2}[0-9OND]\d{2}|\d{5})?(\d+)(CE|PE)$")

    @classmethod
    def parse_option_symbol(cls, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Parse trading symbol to extract underlying, expiry token, strike price, and option type.
        """
        sym = symbol.strip().upper()
        match = cls.OPTION_SYMBOL_PATTERN.match(sym)
        if not match:
            return None

        underlying = match.group(1)
        expiry_token = match.group(2) or ""
        strike = float(match.group(3))
        option_type = match.group(4)

        return {
            "underlying": underlying,
            "expiry_token": expiry_token,
            "strike": strike,
            "option_type": option_type,
        }

    def validate_basket(self, basket: Basket) -> Tuple[bool, List[str]]:
        """
        Execute comprehensive structural validation on a Basket.
        Returns (is_valid, error_list).
        """
        errors: List[str] = []

        if not basket.legs:
            return False, ["Basket must contain at least one order leg."]

        if len(basket.legs) > 10:
            return False, [f"Basket leg count ({len(basket.legs)}) exceeds maximum limit of 10 legs."]

        # 1. Individual Leg Sanity & Tick Modulo
        for idx, leg in enumerate(basket.legs):
            leg_errs = self._validate_single_leg(leg, idx)
            errors.extend(leg_errs)

        if errors:
            return False, errors

        # 2. Strategy-Specific Multi-Leg Invariants
        strat = basket.strategy_type
        strat_str = strat.value if hasattr(strat, "value") else str(strat)
        if strat == StrategyType.CUSTOM or strat_str == "CUSTOM":
            return True, []

        strat_validator = getattr(self, f"_validate_{strat_str.lower()}", None)
        if strat_validator:
            strat_errs = strat_validator(basket.legs)
            errors.extend(strat_errs)
        else:
            errors.append(f"No validation routine configured for strategy {strat_str}")

        return len(errors) == 0, errors

    def _validate_single_leg(self, leg: BasketLeg, idx: int) -> List[str]:
        errs: List[str] = []
        if leg.quantity <= 0:
            errs.append(f"Leg {idx} ({leg.trading_symbol}): Quantity must be > 0 (got {leg.quantity}).")
        if leg.price < 0:
            errs.append(f"Leg {idx} ({leg.trading_symbol}): Price cannot be negative.")
        if leg.trigger_price < 0:
            errs.append(f"Leg {idx} ({leg.trading_symbol}): Trigger price cannot be negative.")

        # Tick modulo check
        if leg.price > 0 and not order_validation_service.validate_tick_size(leg.price, 0.05):
            errs.append(f"Leg {idx} ({leg.trading_symbol}): Price {leg.price:.2f} must be multiple of ₹0.05 tick.")
        if leg.trigger_price > 0 and not order_validation_service.validate_tick_size(leg.trigger_price, 0.05):
            errs.append(f"Leg {idx} ({leg.trading_symbol}): Trigger price {leg.trigger_price:.2f} must be multiple of ₹0.05 tick.")

        return errs

    def _validate_universal_invariants(
        self, legs: List[BasketLeg], allow_mixed_product: bool = False
    ) -> Tuple[Optional[List[Dict[str, Any]]], List[str]]:
        """
        Verify underlying consistency, expiry consistency, lot multiples, and product parity.
        """
        errs: List[str] = []
        parsed_legs: List[Dict[str, Any]] = []

        # Product Type Parity
        if not allow_mixed_product:
            first_prod = legs[0].product_type
            for idx, leg in enumerate(legs[1:], start=1):
                if leg.product_type != first_prod:
                    errs.append(
                        f"Product type mismatch: Leg 0 is {first_prod}, but Leg {idx} is {leg.product_type}."
                    )

        # Parse and check option structures
        first_underlying: Optional[str] = None
        first_expiry: Optional[str] = None

        for idx, leg in enumerate(legs):
            parsed = self.parse_option_symbol(leg.trading_symbol)
            if not parsed:
                errs.append(f"Leg {idx}: '{leg.trading_symbol}' is not a recognized standard option contract.")
                continue

            parsed["leg"] = leg
            parsed["index"] = idx
            parsed_legs.append(parsed)

            # Underlying Parity
            if first_underlying is None:
                first_underlying = parsed["underlying"]
            elif parsed["underlying"] != first_underlying:
                errs.append(
                    f"Underlying mismatch: Leg 0 is on {first_underlying}, but Leg {idx} is on {parsed['underlying']}."
                )

            # Expiry Parity
            if first_expiry is None:
                first_expiry = parsed["expiry_token"]
            elif parsed["expiry_token"] != first_expiry:
                errs.append(
                    f"Expiry mismatch: Leg 0 expires on {first_expiry}, but Leg {idx} expires on {parsed['expiry_token']}."
                )

            # Lot size multiples
            expected_lot = self.BENCHMARK_LOT_SIZES.get(parsed["underlying"])
            if expected_lot and leg.quantity % expected_lot != 0:
                errs.append(
                    f"Leg {idx} ({leg.trading_symbol}): Quantity {leg.quantity} must be a multiple of lot size {expected_lot}."
                )

        return parsed_legs, errs

    # 1. Bull Call Spread
    def _validate_bull_call_spread(self, legs: List[BasketLeg]) -> List[str]:
        if len(legs) != 2:
            return [f"BULL_CALL_SPREAD requires exactly 2 legs (got {len(legs)})."]

        parsed, errs = self._validate_universal_invariants(legs)
        if errs:
            return errs

        p0, p1 = parsed[0], parsed[1]
        if p0["option_type"] != "CE" or p1["option_type"] != "CE":
            return ["BULL_CALL_SPREAD requires both legs to be Call (CE) options."]

        buy_leg = p0 if p0["leg"].side == OrderSide.BUY else (p1 if p1["leg"].side == OrderSide.BUY else None)
        sell_leg = p0 if p0["leg"].side == OrderSide.SELL else (p1 if p1["leg"].side == OrderSide.SELL else None)

        if not buy_leg or not sell_leg:
            return ["BULL_CALL_SPREAD requires exactly one BUY leg and one SELL leg."]

        if buy_leg["leg"].quantity != sell_leg["leg"].quantity:
            return ["BULL_CALL_SPREAD requires identical quantity on both legs."]

        if buy_leg["strike"] >= sell_leg["strike"]:
            return [
                f"BULL_CALL_SPREAD strike violation: Buy Call strike ({buy_leg['strike']}) must be lower than Sell Call strike ({sell_leg['strike']})."
            ]

        return []

    # 2. Bear Put Spread
    def _validate_bear_put_spread(self, legs: List[BasketLeg]) -> List[str]:
        if len(legs) != 2:
            return [f"BEAR_PUT_SPREAD requires exactly 2 legs (got {len(legs)})."]

        parsed, errs = self._validate_universal_invariants(legs)
        if errs:
            return errs

        p0, p1 = parsed[0], parsed[1]
        if p0["option_type"] != "PE" or p1["option_type"] != "PE":
            return ["BEAR_PUT_SPREAD requires both legs to be Put (PE) options."]

        buy_leg = p0 if p0["leg"].side == OrderSide.BUY else (p1 if p1["leg"].side == OrderSide.BUY else None)
        sell_leg = p0 if p0["leg"].side == OrderSide.SELL else (p1 if p1["leg"].side == OrderSide.SELL else None)

        if not buy_leg or not sell_leg:
            return ["BEAR_PUT_SPREAD requires exactly one BUY leg and one SELL leg."]

        if buy_leg["leg"].quantity != sell_leg["leg"].quantity:
            return ["BEAR_PUT_SPREAD requires identical quantity on both legs."]

        if buy_leg["strike"] <= sell_leg["strike"]:
            return [
                f"BEAR_PUT_SPREAD strike violation: Buy Put strike ({buy_leg['strike']}) must be higher than Sell Put strike ({sell_leg['strike']})."
            ]

        return []

    # 3. Long Straddle
    def _validate_long_straddle(self, legs: List[BasketLeg]) -> List[str]:
        return self._validate_straddle(legs, expected_side=OrderSide.BUY, name="LONG_STRADDLE")

    # 4. Short Straddle
    def _validate_short_straddle(self, legs: List[BasketLeg]) -> List[str]:
        return self._validate_straddle(legs, expected_side=OrderSide.SELL, name="SHORT_STRADDLE")

    def _validate_straddle(self, legs: List[BasketLeg], expected_side: OrderSide, name: str) -> List[str]:
        if len(legs) != 2:
            return [f"{name} requires exactly 2 legs (got {len(legs)})."]

        parsed, errs = self._validate_universal_invariants(legs)
        if errs:
            return errs

        p0, p1 = parsed[0], parsed[1]
        opt_types = {p0["option_type"], p1["option_type"]}
        if opt_types != {"CE", "PE"}:
            return [f"{name} requires exactly one Call (CE) and one Put (PE)."]

        if p0["leg"].side != expected_side or p1["leg"].side != expected_side:
            return [f"{name} requires both legs to be {expected_side.value}."]

        if p0["strike"] != p1["strike"]:
            return [f"{name} requires identical strike prices (got {p0['strike']} and {p1['strike']})."]

        if p0["leg"].quantity != p1["leg"].quantity:
            return [f"{name} requires identical quantity on both legs."]

        return []

    # 5. Long Strangle
    def _validate_long_strangle(self, legs: List[BasketLeg]) -> List[str]:
        return self._validate_strangle(legs, expected_side=OrderSide.BUY, name="LONG_STRANGLE")

    # 6. Short Strangle
    def _validate_short_strangle(self, legs: List[BasketLeg]) -> List[str]:
        return self._validate_strangle(legs, expected_side=OrderSide.SELL, name="SHORT_STRANGLE")

    def _validate_strangle(self, legs: List[BasketLeg], expected_side: OrderSide, name: str) -> List[str]:
        if len(legs) != 2:
            return [f"{name} requires exactly 2 legs (got {len(legs)})."]

        parsed, errs = self._validate_universal_invariants(legs)
        if errs:
            return errs

        p0, p1 = parsed[0], parsed[1]
        opt_types = {p0["option_type"], p1["option_type"]}
        if opt_types != {"CE", "PE"}:
            return [f"{name} requires exactly one Call (CE) and one Put (PE)."]

        if p0["leg"].side != expected_side or p1["leg"].side != expected_side:
            return [f"{name} requires both legs to be {expected_side.value}."]

        call_leg = p0 if p0["option_type"] == "CE" else p1
        put_leg = p0 if p0["option_type"] == "PE" else p1

        if call_leg["strike"] <= put_leg["strike"]:
            return [
                f"{name} strike violation: Call strike ({call_leg['strike']}) must be strictly greater than Put strike ({put_leg['strike']})."
            ]

        if call_leg["leg"].quantity != put_leg["leg"].quantity:
            return [f"{name} requires identical quantity on both legs."]

        return []

    # 7. Iron Condor
    def _validate_iron_condor(self, legs: List[BasketLeg]) -> List[str]:
        if len(legs) != 4:
            return [f"IRON_CONDOR requires exactly 4 legs (got {len(legs)})."]

        parsed, errs = self._validate_universal_invariants(legs)
        if errs:
            return errs

        # Categorize
        puts = [p for p in parsed if p["option_type"] == "PE"]
        calls = [p for p in parsed if p["option_type"] == "CE"]

        if len(puts) != 2 or len(calls) != 2:
            return [f"IRON_CONDOR requires exactly 2 Puts and 2 Calls (got {len(puts)} Puts and {len(calls)} Calls)."]

        # Sort puts and calls by strike
        puts.sort(key=lambda x: x["strike"])
        calls.sort(key=lambda x: x["strike"])

        k1_put_buy = puts[0]
        k2_put_sell = puts[1]
        k3_call_sell = calls[0]
        k4_call_buy = calls[1]

        # Sides verification
        if k1_put_buy["leg"].side != OrderSide.BUY or k2_put_sell["leg"].side != OrderSide.SELL:
            return ["IRON_CONDOR Put side violation: lowest Put must be BUY (Wing), higher Put must be SELL (Body)."]
        if k3_call_sell["leg"].side != OrderSide.SELL or k4_call_buy["leg"].side != OrderSide.BUY:
            return ["IRON_CONDOR Call side violation: lower Call must be SELL (Body), highest Call must be BUY (Wing)."]

        # Strike ladder invariant: K1 < K2 < K3 < K4
        if not (k1_put_buy["strike"] < k2_put_sell["strike"] < k3_call_sell["strike"] < k4_call_buy["strike"]):
            return [
                f"IRON_CONDOR strike ladder violation: Expected K1 < K2 < K3 < K4, got {k1_put_buy['strike']} < {k2_put_sell['strike']} < {k3_call_sell['strike']} < {k4_call_buy['strike']}."
            ]

        # Symmetry: (K2 - K1) == (K4 - K3)
        put_spread = k2_put_sell["strike"] - k1_put_buy["strike"]
        call_spread = k4_call_buy["strike"] - k3_call_sell["strike"]
        if round(put_spread, 2) != round(call_spread, 2):
            return [
                f"IRON_CONDOR wing asymmetry: Put wing width ({put_spread}) does not match Call wing width ({call_spread})."
            ]

        # Quantity parity across all 4 legs
        qtys = [p["leg"].quantity for p in parsed]
        if len(set(qtys)) != 1:
            return ["IRON_CONDOR requires identical quantity across all 4 legs."]

        return []

    # 8. Iron Butterfly
    def _validate_iron_butterfly(self, legs: List[BasketLeg]) -> List[str]:
        if len(legs) != 4:
            return [f"IRON_BUTTERFLY requires exactly 4 legs (got {len(legs)})."]

        parsed, errs = self._validate_universal_invariants(legs)
        if errs:
            return errs

        puts = [p for p in parsed if p["option_type"] == "PE"]
        calls = [p for p in parsed if p["option_type"] == "CE"]

        if len(puts) != 2 or len(calls) != 2:
            return ["IRON_BUTTERFLY requires exactly 2 Puts and 2 Calls."]

        puts.sort(key=lambda x: x["strike"])
        calls.sort(key=lambda x: x["strike"])

        k1_put_buy = puts[0]
        k2_put_sell = puts[1]
        k2_call_sell = calls[0]
        k3_call_buy = calls[1]

        if k1_put_buy["leg"].side != OrderSide.BUY or k2_put_sell["leg"].side != OrderSide.SELL:
            return ["IRON_BUTTERFLY Put side violation: outer Put must be BUY, body Put must be SELL."]
        if k2_call_sell["leg"].side != OrderSide.SELL or k3_call_buy["leg"].side != OrderSide.BUY:
            return ["IRON_BUTTERFLY Call side violation: body Call must be SELL, outer Call must be BUY."]

        if k2_put_sell["strike"] != k2_call_sell["strike"]:
            return [
                f"IRON_BUTTERFLY body strike violation: Short Put ({k2_put_sell['strike']}) must equal Short Call ({k2_call_sell['strike']})."
            ]

        if not (k1_put_buy["strike"] < k2_put_sell["strike"] < k3_call_buy["strike"]):
            return ["IRON_BUTTERFLY strike violation: Expected Buy Put < Body Strike < Buy Call."]

        # Symmetry
        put_width = k2_put_sell["strike"] - k1_put_buy["strike"]
        call_width = k3_call_buy["strike"] - k2_call_sell["strike"]
        if round(put_width, 2) != round(call_width, 2):
            return [f"IRON_BUTTERFLY wing asymmetry: Put wing ({put_width}) != Call wing ({call_width})."]

        qtys = [p["leg"].quantity for p in parsed]
        if len(set(qtys)) != 1:
            return ["IRON_BUTTERFLY requires identical quantity across all 4 legs."]

        return []

    # 9. Covered Call
    def _validate_covered_call(self, legs: List[BasketLeg]) -> List[str]:
        if len(legs) != 2:
            return ["COVERED_CALL requires exactly 2 legs (1 Equity Cash and 1 Short Call)."]

        # Allow mixed products (CNC equity + NRML/MIS option)
        eq_leg = next((l for l in legs if l.exchange_segment.endswith("_cm")), None)
        opt_leg = next((l for l in legs if l.exchange_segment.endswith("_fo")), None)

        if not eq_leg or not opt_leg:
            return ["COVERED_CALL requires one Equity Cash leg and one Derivative Option leg."]

        if eq_leg.side != OrderSide.BUY:
            return ["COVERED_CALL requires Equity leg to be BUY (or long Demat holding)."]
        if opt_leg.side != OrderSide.SELL:
            return ["COVERED_CALL requires Option leg to be SELL (Short Call)."]

        parsed_opt = self.parse_option_symbol(opt_leg.trading_symbol)
        if not parsed_opt or parsed_opt["option_type"] != "CE":
            return ["COVERED_CALL option leg must be a Call (CE)."]

        clean_eq = eq_leg.trading_symbol.replace("-EQ", "").upper()
        if clean_eq != parsed_opt["underlying"]:
            return [f"COVERED_CALL symbol mismatch: Equity is {clean_eq}, Option is {parsed_opt['underlying']}."]

        expected_lot = self.BENCHMARK_LOT_SIZES.get(parsed_opt["underlying"])
        if expected_lot and (eq_leg.quantity != opt_leg.quantity or eq_leg.quantity % expected_lot != 0):
            return [f"COVERED_CALL quantity must match contract lot size ({expected_lot})."]

        return []

    # 10. Protective Put
    def _validate_protective_put(self, legs: List[BasketLeg]) -> List[str]:
        if len(legs) != 2:
            return ["PROTECTIVE_PUT requires exactly 2 legs (1 Equity Cash and 1 Long Put)."]

        eq_leg = next((l for l in legs if l.exchange_segment.endswith("_cm")), None)
        opt_leg = next((l for l in legs if l.exchange_segment.endswith("_fo")), None)

        if not eq_leg or not opt_leg:
            return ["PROTECTIVE_PUT requires one Equity Cash leg and one Derivative Option leg."]

        if eq_leg.side != OrderSide.BUY or opt_leg.side != OrderSide.BUY:
            return ["PROTECTIVE_PUT requires both Equity leg and Put leg to be BUY."]

        parsed_opt = self.parse_option_symbol(opt_leg.trading_symbol)
        if not parsed_opt or parsed_opt["option_type"] != "PE":
            return ["PROTECTIVE_PUT option leg must be a Put (PE)."]

        clean_eq = eq_leg.trading_symbol.replace("-EQ", "").upper()
        if clean_eq != parsed_opt["underlying"]:
            return [f"PROTECTIVE_PUT symbol mismatch: Equity is {clean_eq}, Option is {parsed_opt['underlying']}."]

        return []


# Global singleton
strategy_validation_service = StrategyValidationService()
