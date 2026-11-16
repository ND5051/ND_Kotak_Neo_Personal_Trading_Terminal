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


def test_kotak_neo_live_wire_positions_parsing():
    """
    Verify exact Kotak Neo wire positions schema matching real broker terminal:
    - CNC Equity cash delivery (NIFTYBEES)
    - Closed F&O options positions with buyAmt / sellAmt and zero net qty
    """
    svc = PositionsService()

    kotak_wire_payload = {
        "stat": "Ok",
        "stCode": 200,
        "data": [
            {
                "actId": "12345",
                "prod": "CNC",
                "exSeg": "nse_cm",
                "trdSym": "NIFTYBEES-EQ",
                "sym": "NIFTYBEES",
                "tok": "10599",
                "qty": "1",
                "buyAmt": "287.43",
                "sellAmt": "0.00",
                "flBuyQty": "1",
                "flSellQty": "0",
                "posFlg": "true",
                "sqrFlg": "Y",
                "lotSz": "1",
                "lp": "287.61",
            },
            {
                "actId": "12345",
                "prod": "NRML",
                "exSeg": "nse_fo",
                "trdSym": "NIFTY26NOV24400PE",
                "sym": "NIFTY",
                "tok": "55123",
                "qty": "0",
                "buyAmt": "796.25",
                "sellAmt": "1040.00",
                "flBuyQty": "65",
                "flSellQty": "65",
                "posFlg": "false",
                "sqrFlg": "N",
                "lotSz": "65",
                "lp": "16.00",
            },
            {
                "actId": "12345",
                "prod": "NRML",
                "exSeg": "nse_fo",
                "trdSym": "NIFTY26NOV26150CE",
                "sym": "NIFTY",
                "tok": "55124",
                "qty": "0",
                "buyAmt": "765.25",
                "sellAmt": "1087.00",
                "flBuyQty": "65",
                "flSellQty": "65",
                "posFlg": "false",
                "sqrFlg": "N",
                "lotSz": "65",
                "lp": "16.70",
            },
        ],
    }

    positions = svc.parse_positions(kotak_wire_payload, position_type=PositionType.NET)
    assert len(positions) == 3

    # 1. NIFTYBEES (Cash Delivery CNC)
    bees = positions[0]
    assert bees.trading_symbol == "NIFTYBEES-EQ"
    assert bees.product == ProductCode.CNC
    assert bees.exchange_segment == "nse_cm"
    assert bees.instrument_token == "10599"
    assert bees.net_quantity == 1
    assert bees.is_open is True
    assert round(bees.average_buy_price, 2) == 287.43
    assert bees.realized_pnl == 0.0
    assert round(bees.unrealized_pnl, 2) == 0.18
    assert round(bees.total_pnl, 2) == 0.18

    # 2. Closed NIFTY 24400 PE
    pe = positions[1]
    assert pe.trading_symbol == "NIFTY26NOV24400PE"
    assert pe.product == ProductCode.NRML
    assert pe.exchange_segment == "nse_fo"
    assert pe.net_quantity == 0
    assert pe.is_open is False
    assert round(pe.average_buy_price, 2) == 12.25
    assert round(pe.average_sell_price, 2) == 16.00
    assert round(pe.realized_pnl, 2) == 243.75
    assert pe.unrealized_pnl == 0.0
    assert round(pe.total_pnl, 2) == 243.75

    # 3. Closed NIFTY 26150 CE
    ce = positions[2]
    assert ce.trading_symbol == "NIFTY26NOV26150CE"
    assert ce.net_quantity == 0
    assert ce.is_open is False
    assert round(ce.realized_pnl, 2) == 321.75
    assert ce.unrealized_pnl == 0.0

    # Total Realized PnL: 243.75 + 321.75 = 565.50
    total_realized = sum(p.realized_pnl for p in positions)
    assert round(total_realized, 2) == 565.50

