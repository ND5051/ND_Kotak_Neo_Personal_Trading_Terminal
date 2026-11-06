"""
Margin Domain Model.
Phase 6: Portfolio Foundation.
Represents cash limits, collateral values, margin utilization, and risk buffers.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Dict, Optional


@dataclass
class MarginSummary:
    """
    Broker account margin and collateral metrics with live utilization percentage.
    """

    available_cash: float
    collateral_value: float
    total_margin_available: float
    span_margin_used: float = 0.0
    exposure_margin_used: float = 0.0
    option_premium_used: float = 0.0
    total_margin_used: float = 0.0
    margin_utilization_percent: float = 0.0
    unrealized_mtm_loss: float = 0.0
    realized_pnl_credit: float = 0.0
    peak_margin: float = 0.0
    currency: str = "INR"
    source_timestamp: Optional[str] = None
    retrieved_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert margin model to serialized dictionary with rounded numerical values."""
        return {
            "available_cash": round(self.available_cash, 2),
            "collateral_value": round(self.collateral_value, 2),
            "total_margin_available": round(self.total_margin_available, 2),
            "span_margin_used": round(self.span_margin_used, 2),
            "exposure_margin_used": round(self.exposure_margin_used, 2),
            "option_premium_used": round(self.option_premium_used, 2),
            "total_margin_used": round(self.total_margin_used, 2),
            "margin_utilization_percent": round(self.margin_utilization_percent, 2),
            "unrealized_mtm_loss": round(self.unrealized_mtm_loss, 2),
            "realized_pnl_credit": round(self.realized_pnl_credit, 2),
            "peak_margin": round(self.peak_margin, 2),
            "currency": self.currency,
            "source_timestamp": self.source_timestamp,
            "retrieved_timestamp": self.retrieved_timestamp,
            "updated_at": round(self.updated_at, 3),
        }
