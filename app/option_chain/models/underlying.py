"""
Option Chain Underlying Specifications and Filter Presets.
Phase 10: Option Chain Workbench.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class StrikeFilterPreset(str, Enum):
    """
    Standardized strike window presets for option chain ladder filtering.
    Determines the number of strikes displayed symmetrically above and below ATM.
    """

    ATM_5 = "ATM_5"       # ATM ±5 strikes (11 strikes total)
    ATM_10 = "ATM_10"     # ATM ±10 strikes (21 strikes total) - Default
    ATM_15 = "ATM_15"     # ATM ±15 strikes (31 strikes total)
    ATM_20 = "ATM_20"     # ATM ±20 strikes (41 strikes total)

    @classmethod
    def from_value(cls, val: str or int) -> "StrikeFilterPreset":
        """Parse string or integer count to preset enum."""
        if isinstance(val, int):
            if val <= 5:
                return cls.ATM_5
            elif val <= 10:
                return cls.ATM_10
            elif val <= 15:
                return cls.ATM_15
            else:
                return cls.ATM_20

        raw = str(val).strip().upper()
        if raw in ("5", "ATM_5", "ATM±5", "ATM+-5"):
            return cls.ATM_5
        elif raw in ("10", "ATM_10", "ATM±10", "ATM+-10"):
            return cls.ATM_10
        elif raw in ("15", "ATM_15", "ATM±15", "ATM+-15"):
            return cls.ATM_15
        elif raw in ("20", "ATM_20", "ATM±20", "ATM+-20"):
            return cls.ATM_20

        return cls.ATM_10

    @property
    def window_size(self) -> int:
        mapping = {
            StrikeFilterPreset.ATM_5: 5,
            StrikeFilterPreset.ATM_10: 10,
            StrikeFilterPreset.ATM_15: 15,
            StrikeFilterPreset.ATM_20: 20,
        }
        return mapping[self]


@dataclass(frozen=True)
class UnderlyingSpecification:
    """
    Static specifications and instrument linkage for an F&O underlying.
    Maps cash spot instruments to derivative contract configurations.
    """

    symbol: str                               # e.g., "NIFTY", "BANKNIFTY", "RELIANCE"
    display_name: str                         # e.g., "Nifty 50 Index", "Reliance Industries"
    exchange_segment: str                     # "nse_cm" (Spot Underlying)
    derivatives_segment: str                  # "nse_fo" or "bse_fo" (Options Contracts)
    spot_instrument_token: str                # Token used to query Spot LTP (e.g. "26000")
    spot_index_name: Optional[str]            # SFeed exact index subscription name (e.g. "Nifty 50")
    strike_step: float                        # Strike interval (e.g. 50.0, 100.0)
    lot_size: int                             # Exchange lot size (e.g. 25, 15)
    tick_size: float = 0.05                   # Minimum tick size (₹0.05)
    is_index: bool = True                     # True if cash index, False if equity stock

    def to_dict(self, spot_ltp: float = 0.0, is_favourite: bool = False) -> Dict:
        return {
            "symbol": self.symbol,
            "display_name": self.display_name,
            "exchange_segment": self.exchange_segment,
            "derivatives_segment": self.derivatives_segment,
            "spot_instrument_token": self.spot_instrument_token,
            "spot_index_name": self.spot_index_name,
            "strike_step": self.strike_step,
            "lot_size": self.lot_size,
            "tick_size": self.tick_size,
            "is_index": self.is_index,
            "spot_ltp": round(spot_ltp, 2),
            "is_favourite": is_favourite,
        }

