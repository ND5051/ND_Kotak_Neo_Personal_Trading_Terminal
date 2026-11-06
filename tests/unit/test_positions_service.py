"""
Unit tests for PositionsService.
Phase 6: Portfolio Foundation.
Validates polymorphic parsing, The Golden Rule (Absence of Data != 0), Realized PnL,
and dual timestamps.
"""

import pytest

from app.market_watch.services.price_engine import MarketWatchPriceEngine
from app.portfolio.models.position import Position, PositionType, ProductCode
from app.portfolio.services.positions_service import PositionsService


def test_positions_polymorphic_parsing_and_pnl():
    """Verify polymorphic positions parsing, Realized PnL, and Unrealized MTM."""
    pe = MarketWatchPriceEngine()
    svc = PositionsService(prices=pe)

    mock_positions_payload = {
        "result": [
            {
                "instrumentToken": "26000",
                "exchangeSegment": "nse_fo",
                "tradingSymbol": "NIFTY24DEC24500CE",
                "product": "NRML",
                "buyQty": 100,
                "buyAvgPrc": 120.00,
                "sellQty": 50,
                "sellAvgPrc": 130.00,
                "netQty": 50,  # Net Long 50
                "lastPrice": 135.00,
                "sourceTimestamp": "2026-11-06T06:15:00Z",
            },
            {
                "instrumentToken": "26001",
                "exchangeSegment": "nse_fo",
                "trdSym": "BANKNIFTY24DEC52000PE",
                "product": "MIS",
                "flBuyQty": 30,
                "buyAvgPrc": 200.00,
                "flSellQty": 60,
                "sellAvgPrc": 210.00,
                "netQty": -30,  # Net Short 30
                "actPrc": 190.00,
            },
        ]
    }

    positions = svc.parse_positions(mock_positions_payload, position_type=PositionType.NET)
    assert len(positions) == 2

    # 1. Long Position Verification
    p_long = positions[0]
    assert p_long.trading_symbol == "NIFTY24DEC24500CE"
    assert p_long.product == ProductCode.NRML
    assert p_long.net_quantity == 50
    assert p_long.is_open is True
    # Realized PnL: closed 50 * (130 - 120) = 500.00
    assert p_long.realized_pnl == 500.00
    # Unrealized MTM: open 50 * (135 - 120) = 750.00
    assert p_long.unrealized_pnl == 750.00
    # Total PnL: 500 + 750 = 1250.00
    assert p_long.total_pnl == 1250.00
    assert p_long.source_timestamp == "2026-11-06T06:15:00Z"
    assert p_long.retrieved_timestamp is not None

    # 2. Short Position Verification
    p_short = positions[1]
    assert p_short.trading_symbol == "BANKNIFTY24DEC52000PE"
    assert p_short.product == ProductCode.MIS
    assert p_short.net_quantity == -30
    assert p_short.is_open is True
    # Realized PnL: closed 30 * (210 - 200) = 300.00
    assert p_short.realized_pnl == 300.00
    # Unrealized MTM on Short: |net 30| * (sell 210 - ltp 190) = 600.00
    assert p_short.unrealized_pnl == 600.00
    # Total PnL: 300 + 600 = 900.00
    assert p_short.total_pnl == 900.00


def test_the_golden_rule_absence_of_data_is_none():
    """
    Verify The Golden Rule of State Reconciliation:
    Absence of symbol in API response must return None, NEVER 0!
    """
    svc = PositionsService()

    mock_payload = {
        "data": [
            {
                "tradingSymbol": "NIFTY24DEC24500CE",
                "netQty": 50,
            },
            {
                "tradingSymbol": "RELIANCE-EQ",
                "netQty": 0,  # Confirmed explicitly closed!
            },
        ]
    }

    # 1. Present open symbol returns net quantity
    assert svc.get_net_position_for_symbol(mock_payload, "NIFTY24DEC24500CE") == 50

    # 2. Whitespace-insensitive symbol match
    assert svc.get_net_position_for_symbol(mock_payload, "NIFTY 24DEC 24500 CE") == 50

    # 3. Explicitly confirmed closed symbol returns 0
    assert svc.get_net_position_for_symbol(mock_payload, "RELIANCE-EQ") == 0

    # 4. Missing symbol MUST return None, NEVER 0!
    assert svc.get_net_position_for_symbol(mock_payload, "TCS-EQ") is None

    # 5. Empty or error response MUST return None, NEVER 0!
    assert svc.get_net_position_for_symbol([], "NIFTY24DEC24500CE") is None
    assert svc.get_net_position_for_symbol({"error": "Service Unavailable"}, "NIFTY24DEC24500CE") is None
    assert svc.get_net_position_for_symbol(None, "NIFTY24DEC24500CE") is None
