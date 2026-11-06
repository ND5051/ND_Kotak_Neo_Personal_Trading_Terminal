"""
Portfolio Summary Domain Model.
Phase 6: Portfolio Foundation.
Aggregates overall equity holdings, open trading commitments, margin limits, and live PnL.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Dict, Optional


@dataclass
class PortfolioSummary:
    """
    Unified portfolio overview aggregating holdings, open positions, MTM, and margin usage.
    """

    # Holdings Overview
    total_invested_value: float = 0.0
    current_holdings_value: float = 0.0
    holdings_unrealized_pnl: float = 0.0
    holdings_unrealized_pnl_pct: float = 0.0
    holdings_day_pnl: float = 0.0

    # Positions & Trading PnL
    realized_pnl: float = 0.0
    unrealized_mtm: float = 0.0
    total_trading_pnl: float = 0.0
    total_portfolio_pnl: float = 0.0

    # Margins & Risk
    available_cash: float = 0.0
    total_margin_available: float = 0.0
    total_margin_used: float = 0.0
    margin_utilization_percent: float = 0.0

    # Counts
    open_positions_count: int = 0
    total_holdings_count: int = 0

    source_timestamp: Optional[str] = None
    retrieved_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert portfolio summary model to serialized dictionary with rounded numerical values."""
        return {
            "total_invested_value": round(self.total_invested_value, 2),
            "current_holdings_value": round(self.current_holdings_value, 2),
            "holdings_unrealized_pnl": round(self.holdings_unrealized_pnl, 2),
            "holdings_unrealized_pnl_pct": round(self.holdings_unrealized_pnl_pct, 2),
            "holdings_day_pnl": round(self.holdings_day_pnl, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_mtm": round(self.unrealized_mtm, 2),
            "total_trading_pnl": round(self.total_trading_pnl, 2),
            "total_portfolio_pnl": round(self.total_portfolio_pnl, 2),
            "available_cash": round(self.available_cash, 2),
            "total_margin_available": round(self.total_margin_available, 2),
            "total_margin_used": round(self.total_margin_used, 2),
            "margin_utilization_percent": round(self.margin_utilization_percent, 2),
            "open_positions_count": self.open_positions_count,
            "total_holdings_count": self.total_holdings_count,
            "source_timestamp": self.source_timestamp,
            "retrieved_timestamp": self.retrieved_timestamp,
            "updated_at": round(self.updated_at, 3),
        }
