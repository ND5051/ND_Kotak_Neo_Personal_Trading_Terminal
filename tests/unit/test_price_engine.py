"""
Unit tests for MarketWatchPriceEngine and Touchline Quote Cache.
Phase 5: Market Watch Foundation.
Validates price dividers (100.0, 10000.0), spot index handling ('change' field, exact strings),
and quote caching.
"""

import pytest

from app.market_watch.services.price_engine import MarketWatchPriceEngine


def test_price_engine_touchline_scaling():
    """Verify standard SFeed touchline tick parsing and integer price divider (100.0)."""
    pe = MarketWatchPriceEngine()

    raw_tick = {
        "instrument_token": "2885",
        "exchange_segment": "nse_cm",
        "trading_symbol": "RELIANCE-EQ",
        "ltp": 254050,      # Raw integer: 2540.50
        "open": 250000,     # Raw integer: 2500.00
        "high": 255500,     # Raw integer: 2555.00
        "low": 249500,      # Raw integer: 2495.00
        "close": 251000,    # Raw integer: 2510.00
        "volume": 1250000,
        "net_change": 3050, # Raw integer: 30.50
        "percent_change": 1.21,
        "buy_price": 254000,
        "sell_price": 254100,
        "buy_qty": 500,
        "sell_qty": 350,
    }

    quote = pe.ingest_tick(raw_tick)
    assert quote is not None
    assert quote.instrument_token == "2885"
    assert quote.exchange_segment == "nse_cm"
    assert quote.trading_symbol == "RELIANCE-EQ"
    assert quote.ltp == 2540.50
    assert quote.open == 2500.00
    assert quote.high == 2555.00
    assert quote.low == 2495.00
    assert quote.close == 2510.00
    assert quote.net_change == 30.50
    assert quote.percent_change == 1.21
    assert quote.bid == 2540.00
    assert quote.ask == 2541.00
    assert quote.bid_qty == 500
    assert quote.ask_qty == 350


def test_price_engine_currency_scaling():
    """Verify currency segment (cde_fo) 4-decimal scaling (divider 10000.0)."""
    pe = MarketWatchPriceEngine()

    raw_tick = {
        "instrument_token": "7001",
        "exchange_segment": "cde_fo",
        "trading_symbol": "USDINR24DECFUT",
        "ltp": 834525,  # 83.4525
        "close": 834000,
    }

    quote = pe.ingest_tick(raw_tick)
    assert quote is not None
    assert quote.ltp == 83.4525


def test_price_engine_spot_index_handling():
    """
    Verify Kotak Neo SFeedIndex parsing:
    1. Subscribed using exact string (e.g. 'Nifty 50', 'SENSEX').
    2. Change field is named 'change' (not 'net_change').
    """
    pe = MarketWatchPriceEngine()

    # Index tick for Nifty 50
    nifty_tick = {
        "index_name": "Nifty 50",
        "ltp": 2435050,     # 24350.50
        "open": 2420000,
        "high": 2440000,
        "low": 2415000,
        "close": 2420000,
        "change": 15050,    # Notice attribute is 'change'
        "percent_change": 0.62,
    }

    quote = pe.ingest_tick(nifty_tick)
    assert quote is not None
    assert quote.instrument_token == "26000"
    assert quote.exchange_segment == "nse_cm"
    assert quote.trading_symbol == "Nifty 50"
    assert quote.ltp == 24350.50
    assert quote.net_change == 150.50
    assert quote.percent_change == 0.62

    # Verify Sensex
    sensex_tick = {
        "index_name": "SENSEX",
        "ltp": 7950000,     # 79500.00
        "close": 7900000,
        "change": 50000,    # 500.00
        "percent_change": 0.63,
    }
    s_quote = pe.ingest_tick(sensex_tick)
    assert s_quote is not None
    assert s_quote.instrument_token == "1"
    assert s_quote.exchange_segment == "bse_cm"
    assert s_quote.ltp == 79500.00
    assert s_quote.net_change == 500.00


def test_price_engine_batch_lookup():
    """Verify batch retrieval returns formatted dictionary map."""
    pe = MarketWatchPriceEngine()

    pe.ingest_tick({
        "instrument_token": "26000",
        "exchange_segment": "nse_cm",
        "trading_symbol": "Nifty 50",
        "ltp": 24000.0,
    })
    pe.ingest_tick({
        "instrument_token": "11536",
        "exchange_segment": "nse_cm",
        "trading_symbol": "TCS-EQ",
        "ltp": 4150.0,
    })

    batch = pe.get_quotes_batch([("26000", "nse_cm"), ("11536", "nse_cm")])
    assert "nse_cm:26000" in batch
    assert "nse_cm:11536" in batch
    assert batch["nse_cm:26000"]["ltp"] == 24000.0
    assert batch["nse_cm:11536"]["ltp"] == 4150.0
