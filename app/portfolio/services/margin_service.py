"""
Margin Service.
Phase 6: Portfolio Foundation.
Parses account limits, collateral haircuts, and calculates Margin Utilization %.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, Optional

from app.core.audit import AuditCategory, audit_logger
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import MARGINS_UPDATED
from app.logging.logger import get_logger
from app.portfolio.models.margin import MarginSummary

logger = get_logger("app.portfolio.services.margin_service")


class MarginService:
    """
    Normalizes account balances and trading margins from Kotak Neo endpoints.
    """

    def parse_margins(
        self, raw_response: Any, source_timestamp: Optional[str] = None
    ) -> MarginSummary:
        """
        Parse Kotak Neo limits/margin response into normalized MarginSummary domain object.
        """
        data = self._extract_data(raw_response)
        retrieved_ts = datetime.now(timezone.utc).isoformat()
        now_epoch = time.time()

        def safe_float(val: Any, default: float = 0.0) -> float:
            if val is None:
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        avail_cash = safe_float(
            data.get("avlCash")
            or data.get("availableCash")
            or data.get("cashBalance")
            or data.get("net")
            or 0.0
        )
        collateral = safe_float(
            data.get("collateral")
            or data.get("collateralAmount")
            or data.get("pledgeAmount")
            or 0.0
        )
        tot_avail = safe_float(
            data.get("totCash")
            or data.get("totalMarginAvailable")
            or (avail_cash + collateral)
        )
        if tot_avail == 0.0 and (avail_cash > 0 or collateral > 0):
            tot_avail = avail_cash + collateral

        span = safe_float(data.get("spanMargin") or data.get("span") or 0.0)
        exposure = safe_float(data.get("exposureMargin") or data.get("exposure") or 0.0)
        opt_premium = safe_float(data.get("premiumPrsnt") or data.get("premium") or 0.0)
        tot_used = safe_float(
            data.get("ordMrgn")
            or data.get("marginUsed")
            or data.get("utilized")
            or (span + exposure + opt_premium)
        )

        unrealized_loss = safe_float(data.get("unrealizedMtmLoss") or data.get("loss") or 0.0)
        realized_credit = safe_float(data.get("realizedPnlCredit") or data.get("profit") or 0.0)
        peak_margin = safe_float(data.get("peakMargin") or tot_used)

        util_pct = (
            (tot_used / tot_avail * 100.0) if tot_avail > 0 else 0.0
        )

        src_ts = (
            source_timestamp
            or data.get("timestamp")
            or data.get("sourceTimestamp")
        )

        summary = MarginSummary(
            available_cash=avail_cash,
            collateral_value=collateral,
            total_margin_available=tot_avail,
            span_margin_used=span,
            exposure_margin_used=exposure,
            option_premium_used=opt_premium,
            total_margin_used=tot_used,
            margin_utilization_percent=util_pct,
            unrealized_mtm_loss=unrealized_loss,
            realized_pnl_credit=realized_credit,
            peak_margin=peak_margin,
            currency="INR",
            source_timestamp=src_ts,
            retrieved_timestamp=retrieved_ts,
            updated_at=now_epoch,
        )

        publish(
            MARGINS_UPDATED,
            {
                "available_cash": avail_cash,
                "margin_used": tot_used,
                "utilization_pct": util_pct,
                "timestamp": retrieved_ts,
            },
        )

        audit_logger.record(
            category=AuditCategory.BROKER,
            action="MARGIN_SYNC",
            actor="margin_service",
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={
                "available_cash": avail_cash,
                "total_margin_used": tot_used,
                "utilization_pct": util_pct,
            },
        )

        return summary

    def _extract_data(self, payload: Any) -> Dict[str, Any]:
        """Safely extract data mapping from nested Kotak responses."""
        if isinstance(payload, dict):
            if "data" in payload and isinstance(payload["data"], dict):
                return payload["data"]
            if "result" in payload and isinstance(payload["result"], dict):
                return payload["result"]
            return payload
        return {}


# Global Singleton Margin Service
margin_service = MarginService()
