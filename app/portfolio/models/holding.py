"""
Holdings Domain Model.
Phase 6: Portfolio Foundation.
Represents Demat equity holdings with custody, acquisition cost, and day PnL tracking.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Dict, Optional


@dataclass
class Holding:
    """
    Demat account holding record with acquisition valuation, current market value,
    and broker/exchange timestamps.
    """

    instrument_token: str
    exchange_segment: str
    trading_symbol: str
    isin: str
    total_quantity: int
    settled_quantity: int
    t1_quantity: int
    pledged_quantity: int
    average_price: float
    invested_value: float
    current_price: float
    current_value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    close_price: float
    day_pnl: float
    day_pnl_percent: float
    collateral_eligible: bool = True
    source_timestamp: Optional[str] = None
    retrieved_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert holding model to serialized dictionary with rounded numerical values."""
        return {
            "instrument_token": self.instrument_token,
            "exchange_segment": self.exchange_segment,
            "trading_symbol": self.trading_symbol,
            "isin": self.isin,
            "total_quantity": self.total_quantity,
            "settled_quantity": self.settled_quantity,
            "t1_quantity": self.t1_quantity,
            "pledged_quantity": self.pledged_quantity,
            "average_price": round(self.average_price, 2),
            "invested_value": round(self.invested_value, 2),
            "current_price": round(self.current_price, 2),
            "current_value": round(self.current_value, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "unrealized_pnl_percent": round(self.unrealized_pnl_percent, 2),
            "close_price": round(self.close_price, 2),
            "day_pnl": round(self.day_pnl, 2),
            "day_pnl_percent": round(self.day_pnl_percent, 2),
            "collateral_eligible": self.collateral_eligible,
            "source_timestamp": self.source_timestamp,
            "retrieved_timestamp": self.retrieved_timestamp,
            "updated_at": round(self.updated_at, 3),
        }
