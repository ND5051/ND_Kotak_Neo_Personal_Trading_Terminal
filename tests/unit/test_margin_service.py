"""
Unit tests for MarginService.
Phase 6: Portfolio Foundation.
Validates margin parsing, collateral accounting, margin utilization %, and dual timestamps.
"""

import pytest

from app.portfolio.models.margin import MarginSummary
from app.portfolio.services.margin_service import MarginService


def test_margin_service_parsing_and_utilization():
    """Verify parsing of cash limits and margin utilization percentage calculation."""
    svc = MarginService()

    mock_margins_payload = {
        "data": {
            "avlCash": 100000.00,
            "collateral": 150000.00,
            "totCash": 250000.00,
            "spanMargin": 35000.00,
            "exposureMargin": 15000.00,
            "premiumPrsnt": 5000.00,
            "ordMrgn": 55000.00,
            "unrealizedMtmLoss": 1200.00,
            "realizedPnlCredit": 3500.00,
            "sourceTimestamp": "2026-11-06T06:30:00Z",
        }
    }

    margins = svc.parse_margins(mock_margins_payload)

    assert margins.available_cash == 100000.00
    assert margins.collateral_value == 150000.00
    assert margins.total_margin_available == 250000.00
    assert margins.span_margin_used == 35000.00
    assert margins.exposure_margin_used == 15000.00
    assert margins.option_premium_used == 5000.00
    assert margins.total_margin_used == 55000.00
    # Utilization %: 55000 / 250000 * 100 = 22.0%
    assert margins.margin_utilization_percent == 22.00
    assert margins.unrealized_mtm_loss == 1200.00
    assert margins.realized_pnl_credit == 3500.00

    # Verify Timestamps
    assert margins.source_timestamp == "2026-11-06T06:30:00Z"
    assert margins.retrieved_timestamp is not None
    assert "T" in margins.retrieved_timestamp
