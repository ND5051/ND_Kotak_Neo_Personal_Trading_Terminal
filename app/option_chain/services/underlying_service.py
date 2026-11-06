"""
Underlying Instrument Catalog and Favourite Underlyings Service.
Phase 10: Option Chain Workbench.
"""

import threading
from typing import Dict, List, Optional, Set

from app.market_watch.services.price_engine import price_engine
from app.option_chain.models.underlying import UnderlyingSpecification


class UnderlyingService:
    """
    Catalog and preference manager for F&O underlying assets.
    Tracks spot price instrument tokens, strike intervals, lot sizes,
    and user-pinned favourite underlyings.
    """

    # Default configured benchmark indices and key F&O underlyings
    DEFAULT_UNDERLYINGS: Dict[str, UnderlyingSpecification] = {
        "NIFTY": UnderlyingSpecification(
            symbol="NIFTY",
            display_name="Nifty 50 Index",
            exchange_segment="nse_cm",
            derivatives_segment="nse_fo",
            spot_instrument_token="26000",
            spot_index_name="Nifty 50",
            strike_step=50.0,
            lot_size=25,
            tick_size=0.05,
            is_index=True,
        ),
        "BANKNIFTY": UnderlyingSpecification(
            symbol="BANKNIFTY",
            display_name="Bank Nifty Index",
            exchange_segment="nse_cm",
            derivatives_segment="nse_fo",
            spot_instrument_token="26001",
            spot_index_name="Nifty Bank",
            strike_step=100.0,
            lot_size=15,
            tick_size=0.05,
            is_index=True,
        ),
        "FINNIFTY": UnderlyingSpecification(
            symbol="FINNIFTY",
            display_name="Nifty Financial Services",
            exchange_segment="nse_cm",
            derivatives_segment="nse_fo",
            spot_instrument_token="26037",
            spot_index_name="Nifty Fin Service",
            strike_step=50.0,
            lot_size=25,
            tick_size=0.05,
            is_index=True,
        ),
        "MIDCPNIFTY": UnderlyingSpecification(
            symbol="MIDCPNIFTY",
            display_name="Nifty Midcap Select",
            exchange_segment="nse_cm",
            derivatives_segment="nse_fo",
            spot_instrument_token="26074",
            spot_index_name="NIFTY MID SELECT",
            strike_step=25.0,
            lot_size=50,
            tick_size=0.05,
            is_index=True,
        ),
        "SENSEX": UnderlyingSpecification(
            symbol="SENSEX",
            display_name="BSE Sensex 30 Index",
            exchange_segment="bse_cm",
            derivatives_segment="bse_fo",
            spot_instrument_token="1",
            spot_index_name="SENSEX",
            strike_step=100.0,
            lot_size=10,
            tick_size=0.05,
            is_index=True,
        ),
        "RELIANCE": UnderlyingSpecification(
            symbol="RELIANCE",
            display_name="Reliance Industries Ltd",
            exchange_segment="nse_cm",
            derivatives_segment="nse_fo",
            spot_instrument_token="2885",
            spot_index_name=None,
            strike_step=20.0,
            lot_size=250,
            tick_size=0.05,
            is_index=False,
        ),
        "TCS": UnderlyingSpecification(
            symbol="TCS",
            display_name="Tata Consultancy Services Ltd",
            exchange_segment="nse_cm",
            derivatives_segment="nse_fo",
            spot_instrument_token="11536",
            spot_index_name=None,
            strike_step=50.0,
            lot_size=175,
            tick_size=0.05,
            is_index=False,
        ),
        "INFY": UnderlyingSpecification(
            symbol="INFY",
            display_name="Infosys Ltd",
            exchange_segment="nse_cm",
            derivatives_segment="nse_fo",
            spot_instrument_token="1594",
            spot_index_name=None,
            strike_step=20.0,
            lot_size=400,
            tick_size=0.05,
            is_index=False,
        ),
        "HDFCBANK": UnderlyingSpecification(
            symbol="HDFCBANK",
            display_name="HDFC Bank Ltd",
            exchange_segment="nse_cm",
            derivatives_segment="nse_fo",
            spot_instrument_token="1333",
            spot_index_name=None,
            strike_step=20.0,
            lot_size=550,
            tick_size=0.05,
            is_index=False,
        ),
    }

    def __init__(self, pe=None) -> None:
        self.price_engine = pe or price_engine
        self._underlyings: Dict[str, UnderlyingSpecification] = dict(self.DEFAULT_UNDERLYINGS)
        # In-memory user favourites set (user_id -> set of symbols)
        self._user_favourites: Dict[int, Set[str]] = {}
        self._lock = threading.RLock()

    def get_underlying(self, symbol: str) -> Optional[UnderlyingSpecification]:
        """Lookup specification for a symbol."""
        with self._lock:
            return self._underlyings.get(symbol.strip().upper())

    def list_underlyings(self, user_id: int = 1) -> List[Dict]:
        """
        List all supported underlyings enriched with real-time Spot LTP and favourite flag.
        """
        with self._lock:
            user_favs = self._user_favourites.get(user_id, {"NIFTY", "BANKNIFTY"})
            res = []
            for sym, spec in self._underlyings.items():
                spot_ltp = self.get_spot_ltp(sym)
                is_fav = sym in user_favs
                res.append(spec.to_dict(spot_ltp=spot_ltp, is_favourite=is_fav))
            return res

    def get_favourites(self, user_id: int = 1) -> List[Dict]:
        """Retrieve user's pinned favourite underlyings with Spot LTP."""
        with self._lock:
            user_favs = self._user_favourites.get(user_id, {"NIFTY", "BANKNIFTY"})
            res = []
            for sym in user_favs:
                spec = self._underlyings.get(sym)
                if spec:
                    spot_ltp = self.get_spot_ltp(sym)
                    res.append(spec.to_dict(spot_ltp=spot_ltp, is_favourite=True))
            return res

    def toggle_favourite(self, user_id: int, symbol: str, is_favourite: bool) -> bool:
        """Pin or unpin an underlying symbol for user."""
        sym = symbol.strip().upper()
        with self._lock:
            if sym not in self._underlyings:
                return False

            if user_id not in self._user_favourites:
                self._user_favourites[user_id] = {"NIFTY", "BANKNIFTY"}

            if is_favourite:
                self._user_favourites[user_id].add(sym)
            else:
                self._user_favourites[user_id].discard(sym)
            return True

    def get_spot_ltp(self, symbol: str) -> float:
        """
        Retrieve live spot price from Phase 5 Price Engine, or return reference benchmark.
        """
        spec = self._underlyings.get(symbol.strip().upper())
        if not spec:
            return 0.0

        # Query PriceEngine touchline
        try:
            touchline = self.price_engine.get_touchline(spec.exchange_segment, spec.spot_instrument_token)
            if touchline and touchline.ltp > 0:
                return touchline.ltp
        except Exception:
            pass

        # Reference fallback prices for test / development environments
        fallbacks = {
            "NIFTY": 24512.40,
            "BANKNIFTY": 51280.00,
            "FINNIFTY": 23450.00,
            "MIDCPNIFTY": 12600.00,
            "SENSEX": 80420.00,
            "RELIANCE": 2540.00,
            "TCS": 3520.00,
            "INFY": 1580.00,
            "HDFCBANK": 1680.00,
        }
        return fallbacks.get(spec.symbol, 100.0)


# Global singleton instance
underlying_service = UnderlyingService()

