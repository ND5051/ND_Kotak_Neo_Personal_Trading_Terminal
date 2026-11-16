"""
Underlying Instrument Catalog and Favourite Underlyings Service.
Phase 10: Option Chain Workbench.
Enhanced with dynamic F&O universe indexing from Scrip Master (220+ instruments).
"""

import glob
import os
import threading
from typing import Dict, List, Optional, Set

import pandas as pd

from app.market_watch.services.price_engine import price_engine
from app.option_chain.models.underlying import UnderlyingSpecification


class UnderlyingService:
    """
    Catalog and preference manager for F&O underlying assets.
    Tracks spot price instrument tokens, strike intervals, lot sizes,
    and user-pinned favourite underlyings.
    """

    # 3 Core Liquid Benchmark Indices + Curated Key F&O Underlyings
    DEFAULT_UNDERLYINGS: Dict[str, UnderlyingSpecification] = {
        "NIFTY": UnderlyingSpecification(
            symbol="NIFTY",
            display_name="Nifty 50 Index",
            exchange_segment="nse_cm",
            derivatives_segment="nse_fo",
            spot_instrument_token="26000",
            spot_index_name="Nifty 50",
            strike_step=50.0,
            lot_size=65,
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
        "IDEA": UnderlyingSpecification(
            symbol="IDEA",
            display_name="Vodafone Idea Ltd",
            exchange_segment="nse_cm",
            derivatives_segment="nse_fo",
            spot_instrument_token="14366",
            spot_index_name=None,
            strike_step=1.0,
            lot_size=36125,
            tick_size=0.05,
            is_index=False,
        ),
        "SBIN": UnderlyingSpecification(
            symbol="SBIN",
            display_name="State Bank of India",
            exchange_segment="nse_cm",
            derivatives_segment="nse_fo",
            spot_instrument_token="3045",
            spot_index_name=None,
            strike_step=20.0,
            lot_size=750,
            tick_size=0.05,
            is_index=False,
        ),
    }

    def __init__(self, pe=None) -> None:
        self.price_engine = pe or price_engine
        self._underlyings: Dict[str, UnderlyingSpecification] = dict(self.DEFAULT_UNDERLYINGS)
        self._fno_catalog: Optional[Dict[str, UnderlyingSpecification]] = None
        self._user_favourites: Dict[int, Set[str]] = {}
        self._lock = threading.RLock()

    def _ensure_fno_catalog(self) -> None:
        """Lazily index all 220+ F&O underlyings from nse_fo.csv and nse_cm.csv."""
        if self._fno_catalog is not None:
            return
        with self._lock:
            if self._fno_catalog is not None:
                return
            catalog: Dict[str, UnderlyingSpecification] = {}
            try:
                fo_files = sorted(glob.glob("data/scrip_master/**/nse_fo.csv", recursive=True))
                cm_files = sorted(glob.glob("data/scrip_master/**/nse_cm.csv", recursive=True))
                if fo_files:
                    cm_map: Dict[str, tuple] = {}
                    if cm_files:
                        try:
                            cm_df = pd.read_csv(cm_files[-1], usecols=["pSymbol", "pTrdSymbol", "pDesc"], low_memory=False)
                            for _, row in cm_df.iterrows():
                                trd = str(row["pTrdSymbol"])
                                if trd.endswith("-EQ"):
                                    cm_map[trd[:-3]] = (str(row["pSymbol"]), str(row["pDesc"]))
                        except Exception:
                            pass

                    fo_df = pd.read_csv(
                        fo_files[-1],
                        usecols=["pSymbolName", "lLotSize", "dTickSize ", "pInstType", "dStrikePrice;"],
                        low_memory=False,
                    )
                    opt_df = fo_df[fo_df["pInstType"].isin(["OPTSTK", "OPTIDX", "FUTSTK", "FUTIDX"])]
                    for sym, grp in opt_df.groupby("pSymbolName"):
                        row = grp.iloc[0]
                        spot_tok, desc = cm_map.get(sym, ("", sym))
                        is_idx = bool(row["pInstType"] in ["OPTIDX", "FUTIDX"])

                        # Strike step derivation from strikes in paise
                        step = 50.0 if is_idx else 1.0
                        try:
                            strikes = sorted(grp["dStrikePrice;"].dropna().unique())
                            if len(strikes) >= 2:
                                diffs = [round((strikes[i + 1] - strikes[i]) / 100.0, 2) for i in range(min(5, len(strikes) - 1))]
                                pos_diffs = [d for d in diffs if d > 0]
                                if pos_diffs:
                                    step = min(pos_diffs)
                        except Exception:
                            pass

                        lot_sz = int(row.get("lLotSize") or 1)
                        catalog[sym] = UnderlyingSpecification(
                            symbol=sym,
                            display_name=desc if desc != sym else f"{sym} Ltd",
                            exchange_segment="nse_cm",
                            derivatives_segment="nse_fo",
                            spot_instrument_token=spot_tok,
                            spot_index_name=sym if is_idx else None,
                            strike_step=float(step),
                            lot_size=lot_sz,
                            tick_size=0.05,
                            is_index=is_idx,
                        )
            except Exception:
                pass
            self._fno_catalog = catalog

    def get_underlying(self, symbol: str) -> Optional[UnderlyingSpecification]:
        """Lookup specification for an underlying symbol (supporting indices and all 220+ F&O stocks)."""
        sym = symbol.strip().upper()
        with self._lock:
            spec = self._underlyings.get(sym)
            if spec:
                return spec
            self._ensure_fno_catalog()
            if self._fno_catalog and sym in self._fno_catalog:
                return self._fno_catalog[sym]
            return None

    def list_underlyings(self, user_id: int = 1) -> List[Dict]:
        """
        List core benchmark indices and curated key underlyings enriched with real-time Spot LTP.
        """
        with self._lock:
            user_favs = self._user_favourites.get(user_id, {"NIFTY", "BANKNIFTY", "SENSEX"})
            res = []
            for sym, spec in self._underlyings.items():
                spot_ltp = self.get_spot_ltp(sym)
                is_fav = sym in user_favs
                res.append(spec.to_dict(spot_ltp=spot_ltp, is_favourite=is_fav))
            return res

    def search_underlyings(self, query: str = "", user_id: int = 1, limit: int = 25) -> List[Dict]:
        """
        Search underlyings matching query across core indices and 220+ F&O stocks.
        Returns curated matches enriched with favourite flag and spot LTP.
        """
        q = (query or "").strip().upper()
        self._ensure_fno_catalog()
        with self._lock:
            user_favs = self._user_favourites.get(user_id, {"NIFTY", "BANKNIFTY", "SENSEX"})

            all_specs: Dict[str, UnderlyingSpecification] = dict(self._fno_catalog or {})
            all_specs.update(self._underlyings)

            if not q:
                result_symbols = ["NIFTY", "BANKNIFTY", "SENSEX"]
                for fav in sorted(user_favs):
                    if fav not in result_symbols and fav in all_specs:
                        result_symbols.append(fav)
                for pop in ["RELIANCE", "TCS", "INFY", "HDFCBANK", "IDEA", "SBIN"]:
                    if pop not in result_symbols and pop in all_specs:
                        result_symbols.append(pop)
            else:
                exact_or_prefix = []
                substring = []
                for sym, spec in all_specs.items():
                    if sym == q:
                        exact_or_prefix.insert(0, sym)
                    elif sym.startswith(q):
                        exact_or_prefix.append(sym)
                    elif q in sym or q in spec.display_name.upper():
                        substring.append(sym)
                result_symbols = (exact_or_prefix + substring)[:limit]

            res = []
            for sym in result_symbols:
                spec = all_specs.get(sym)
                if spec:
                    spot_ltp = self.get_spot_ltp(sym)
                    is_fav = sym in user_favs
                    res.append(spec.to_dict(spot_ltp=spot_ltp, is_favourite=is_fav))
            return res

    def get_favourites(self, user_id: int = 1) -> List[Dict]:
        """Retrieve user's pinned favourite underlyings with Spot LTP."""
        with self._lock:
            user_favs = self._user_favourites.get(user_id, {"NIFTY", "BANKNIFTY", "SENSEX"})
            res = []
            for sym in user_favs:
                spec = self.get_underlying(sym)
                if spec:
                    spot_ltp = self.get_spot_ltp(sym)
                    res.append(spec.to_dict(spot_ltp=spot_ltp, is_favourite=True))
            return res

    def toggle_favourite(self, user_id: int, symbol: str, is_favourite: bool) -> bool:
        """Pin or unpin an underlying symbol for user."""
        sym = symbol.strip().upper()
        with self._lock:
            spec = self.get_underlying(sym)
            if not spec:
                return False

            if user_id not in self._user_favourites:
                self._user_favourites[user_id] = {"NIFTY", "BANKNIFTY", "SENSEX"}

            if is_favourite:
                self._user_favourites[user_id].add(sym)
            else:
                self._user_favourites[user_id].discard(sym)
            return True

    def get_spot_ltp(self, symbol: str) -> float:
        """
        Retrieve live spot price from Phase 5 Price Engine, or return reference benchmark.
        """
        spec = self.get_underlying(symbol.strip().upper())
        if not spec:
            return 0.0

        # Query PriceEngine touchline
        try:
            touchline = self.price_engine.get_quote(token=spec.spot_instrument_token, segment=spec.exchange_segment)
            if touchline and touchline.ltp > 0:
                return touchline.ltp
        except Exception:
            pass

        # Reference fallback prices for test / development environments
        fallbacks = {
            "NIFTY": 25219.00,
            "BANKNIFTY": 51280.00,
            "SENSEX": 81914.52,
            "RELIANCE": 1344.80,
            "TCS": 2405.00,
            "INFY": 1139.90,
            "HDFCBANK": 1720.00,
            "IDEA": 8.50,
            "SBIN": 1090.50,
        }
        return fallbacks.get(spec.symbol, 100.0)


# Global singleton instance
underlying_service = UnderlyingService()
