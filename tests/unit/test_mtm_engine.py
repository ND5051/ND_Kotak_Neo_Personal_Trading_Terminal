"""
Unit tests for MTMEngine.
Phase 6: Portfolio Foundation.
Validates real-time MTM recalculation on incoming ticks and event publishing.
"""

import pytest

from app.events.event_bus import event_bus
from app.events.event_types import MTM_UPDATED
from app.market_watch.services.price_engine import MarketWatchPriceEngine
from app.portfolio.models.position import Position, PositionType, ProductCode
from app.portfolio.services.mtm_engine import MTMEngine


def test_mtm_engine_realtime_tick_processing():
    """Verify that incoming ticks update open position MTM and preserve realized PnL."""
    pe = MarketWatchPriceEngine()
    engine = MTMEngine(prices=pe)

    # Long Position: bought 50 @ 100, closed 20 @ 110 (realized 200), net open 30
    pos_long = Position(
        instrument_token="26000",
        exchange_segment="nse_fo",
        trading_symbol="NIFTY24DEC24500CE",
        product=ProductCode.NRML,
        position_type=PositionType.NET,
        buy_quantity=50,
        buy_amount=5000.0,
        average_buy_price=100.0,
        sell_quantity=20,
        sell_amount=2200.0,
        average_sell_price=110.0,
        net_quantity=30,
        current_price=100.0,
        realized_pnl=200.0,
        unrealized_pnl=0.0,
        total_pnl=200.0,
        is_open=True,
    )

    # Short Position: net short 20 @ 200
    pos_short = Position(
        instrument_token="26001",
        exchange_segment="nse_fo",
        trading_symbol="BANKNIFTY24DEC52000PE",
        product=ProductCode.MIS,
        position_type=PositionType.NET,
        buy_quantity=0,
        buy_amount=0.0,
        average_buy_price=0.0,
        sell_quantity=20,
        sell_amount=4000.0,
        average_sell_price=200.0,
        net_quantity=-20,
        current_price=200.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        total_pnl=0.0,
        is_open=True,
    )

    engine.set_positions([pos_long, pos_short])
    assert engine.get_open_positions_count() == 2
    assert engine.get_total_realized_pnl() == 200.0
    assert engine.get_total_unrealized_mtm() == 0.0

    # Capture event dispatch
    received_events = []
    def handler(evt):
        received_events.append(evt)
    event_bus.subscribe(MTM_UPDATED, handler)

    try:
        # Tick 1: Long position rises from 100 to 110
        # MTM on Long = 30 * (110 - 100) = 300.00
        engine.on_tick_received("26000", "nse_fo", 110.0)
        assert pos_long.unrealized_pnl == 300.0
        assert pos_long.total_pnl == 500.0  # 200 realized + 300 unrealized
        assert engine.get_total_unrealized_mtm() == 300.0
        assert len(received_events) >= 1

        # Tick 2: Short position falls favorably from 200 to 190
        # MTM on Short = 20 * (200 - 190) = 200.00
        engine.on_tick_received("26001", "nse_fo", 190.0)
        assert pos_short.unrealized_pnl == 200.0
        assert pos_short.total_pnl == 200.0

        # Total MTM = 300 (Long) + 200 (Short) = 500.00
        assert engine.get_total_unrealized_mtm() == 500.0

        # Non-tracked token tick returns None and does not affect portfolio
        assert engine.on_tick_received("99999", "nse_fo", 50.0) is None

    finally:
        event_bus.unsubscribe(MTM_UPDATED, handler)
