"""
Positions Domain Model.
Phase 6: Portfolio Foundation.
Represents Day and Net trading positions across cash and derivatives segments.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import time
from typing import Any, Dict, Optional


class PositionType(str, Enum):
    """Lifecycle classification of position."""
    DAY = "DAY"         # Current session intraday executions
    NET = "NET"         # Cumulative carry-forward plus intraday open commitments


class ProductCode(str, Enum):
    """Trading product type code."""
    CNC = "CNC"         # Cash and Carry (Equity delivery)
    MIS = "MIS"         # Margin Intraday Square-off
    NRML = "NRML"       # Normal overnight derivatives (Futures & Options)


@dataclass
class Position:
    """
    Open or closed trading position with realized PnL, floating MTM, and dual timestamps.
    """

    instrument_token: str
    exchange_segment: str
    trading_symbol: str
    product: ProductCode
    position_type: PositionType
    buy_quantity: int
    buy_amount: float
    average_buy_price: float
    sell_quantity: int
    sell_amount: float
    average_sell_price: float
    net_quantity: int
    multiplier: int = 1
    close_price: float = 0.0
    current_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_pnl: float = 0.0
    is_open: bool = False
    source_timestamp: Optional[str] = None
    retrieved_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert position model to serialized dictionary with rounded numerical values."""
        return {
            "instrument_token": self.instrument_token,
            "exchange_segment": self.exchange_segment,
            "trading_symbol": self.trading_symbol,
            "product": self.product.value,
            "position_type": self.position_type.value,
            "buy_quantity": self.buy_quantity,
            "buy_amount": round(self.buy_amount, 2),
            "average_buy_price": round(self.average_buy_price, 2),
            "sell_quantity": self.sell_quantity,
            "sell_amount": round(self.sell_amount, 2),
            "average_sell_price": round(self.average_sell_price, 2),
            "net_quantity": self.net_quantity,
            "multiplier": self.multiplier,
            "close_price": round(self.close_price, 2),
            "current_price": round(self.current_price, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "total_pnl": round(self.total_pnl, 2),
            "is_open": self.is_open,
            "source_timestamp": self.source_timestamp,
            "retrieved_timestamp": self.retrieved_timestamp,
            "updated_at": round(self.updated_at, 3),
        }
