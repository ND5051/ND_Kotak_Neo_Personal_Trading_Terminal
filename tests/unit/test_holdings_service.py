"""
Unit tests for HoldingsService.
Phase 6: Portfolio Foundation.
Validates holdings parsing, custody accounting, live price binding, and dual timestamps.
"""

import pytest

from app.market_watch.models.instrument import MarketQuote
from app.market_watch.services.price_engine import MarketWatchPriceEngine
from app.portfolio.models.holding import Holding
from app.portfolio.services.holdings_service import HoldingsService


def test_holdings_parsing_and_valuation():
    """Verify parsing of Demat holdings with custody quantities and day PnL."""
    pe = MarketWatchPriceEngine()
    svc = HoldingsService(prices=pe)

    mock_holdings_payload = {
        "data": [
            {
                "instrumentToken": "2885",
                "exchangeSegment": "nse_cm",
                "tradingSymbol": "RELIANCE-EQ",
                "isin": "INE002A01018",
                "totalQty": 50,
                "settledQty": 40,
                "t1Qty": 10,
                "pledgedQty": 0,
                "averagePrice": 2400.00,
                "closePrice": 2500.00,
                "lastPrice": 2550.00,
                "sourceTimestamp": "2026-11-06T06:00:00Z",
            }
        ]
    }

    holdings = svc.parse_holdings(mock_holdings_payload)
    assert len(holdings) == 1
    h = holdings[0]

    assert h.instrument_token == "2885"
    assert h.trading_symbol == "RELIANCE-EQ"
    assert h.total_quantity == 50
    assert h.settled_quantity == 40
    assert h.t1_quantity == 10
    assert h.pledged_quantity == 0
    assert h.average_price == 2400.00
    assert h.invested_value == 120000.00  # 50 * 2400
    assert h.current_price == 2550.00
    assert h.current_value == 127500.00   # 50 * 2550
    assert h.unrealized_pnl == 7500.00     # 127500 - 120000
    assert h.unrealized_pnl_percent == 6.25
    assert h.day_pnl == 2500.00           # 50 * (2550 - 2500)
    assert h.day_pnl_percent == 2.00

    # Verify Timestamps
    assert h.source_timestamp == "2026-11-06T06:00:00Z"
    assert h.retrieved_timestamp is not None
    assert "T" in h.retrieved_timestamp


def test_holdings_live_price_engine_binding():
    """Verify that live price updates in PriceEngine override fallback broker prices."""
    pe = MarketWatchPriceEngine()
    svc = HoldingsService(prices=pe)

    # Ingest tick into price engine for TCS
    pe.ingest_tick({
        "instrument_token": "11536",
        "exchange_segment": "nse_cm",
        "trading_symbol": "TCS-EQ",
        "ltp": 4200.00,
    })

    mock_payload = [
        {
            "instrumentToken": "11536",
            "exchangeSegment": "nse_cm",
            "tradingSymbol": "TCS-EQ",
            "totalQty": 20,
            "averagePrice": 4000.00,
            "lastPrice": 4100.00,  # Stale broker payload price
        }
    ]

    holdings = svc.parse_holdings(mock_payload)
    assert len(holdings) == 1
    h = holdings[0]

    # Live price from PriceEngine (4200.00) overrides stale 4100.00
    assert h.current_price == 4200.00
    assert h.current_value == 84000.00  # 20 * 4200
    assert h.unrealized_pnl == 4000.00   # 84000 - 80000
