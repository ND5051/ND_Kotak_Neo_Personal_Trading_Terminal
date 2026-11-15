import json
from unittest.mock import MagicMock, patch
import pytest

from app import create_app
from app.broker.adapters.kotak_stream_adapter import KotakStreamAdapter
from app.broker.services.subscription_manager import SubscriptionManager
from app.market_watch.services.price_engine import MarketWatchPriceEngine


@pytest.fixture
def test_app():
    app = create_app()
    app.config["TESTING"] = True
    yield app


@pytest.fixture
def test_client(test_app):
    return test_app.test_client()


def test_sfeed_tick_ingestion_updates_price_engine():
    """Verify SFeed packets update PriceEngine cache and last tick telemetry."""
    pe = MarketWatchPriceEngine()
    adapter = KotakStreamAdapter()
    adapter.set_message_handler(pe.ingest_tick)

    # Scrip tick from neo_api_client SFeedScrip
    scrip_payload = {
        "instrument_token": "11536",
        "last_traded_price": 2550.75,
        "volume_traded_today": 1250000,
        "net_change_percent": 1.25,
        "high": 2560.0,
        "low": 2520.0,
        "open": 2530.0,
        "close": 2519.25,
        "buy": [{"price": 2550.5, "quantity": 100}],
        "sell": [{"price": 2551.0, "quantity": 150}],
    }

    adapter.ingest_raw_tick(scrip_payload)

    quote = pe.get_quote("11536", "nse_cm")
    assert quote is not None
    assert quote.ltp == 2550.75
    assert quote.volume == 1250000
    assert quote.percent_change == 1.25
    assert pe.get_last_tick_symbol() == "11536"
    assert pe.get_last_tick_timestamp() is not None


def test_sfeed_index_tick_updates_price_engine():
    """Verify SFeedIndex packets update PriceEngine cache for Nifty and SENSEX."""
    pe = MarketWatchPriceEngine()
    adapter = KotakStreamAdapter()
    adapter.set_message_handler(pe.ingest_tick)

    # Index tick for Nifty 50
    index_payload = {
        "name": "Nifty 50",
        "last_traded_price": 24350.20,
        "change": 120.50,
        "net_change_percent": 0.50,
        "high": 24400.0,
        "low": 24200.0,
        "open": 24250.0,
        "close": 24229.70,
    }

    adapter.ingest_raw_tick(index_payload)

    quote = pe.get_quote("26000", "nse_cm")
    assert quote is not None
    assert quote.ltp == 24350.20
    assert quote.net_change == 120.50
    assert quote.percent_change == 0.50
    assert quote.trading_symbol == "Nifty 50"


def test_route_subscription_tokens_identifies_indices():
    """Verify route_subscription_tokens segregates index names correctly."""
    adapter = KotakStreamAdapter()
    tokens = [
        {"token_id": "26000", "exchange_segment": "nse_cm"},
        {"token_id": "26001", "exchange_segment": "nse_cm"},
        {"token_id": "1", "exchange_segment": "bse_cm"},
        {"token_id": "11536", "exchange_segment": "nse_cm"},
    ]

    routed = adapter.route_subscription_tokens(tokens)
    assert "Nifty 50" in routed["index_tokens"]
    assert "Nifty Bank" in routed["index_tokens"]
    assert "SENSEX" in routed["index_tokens"]
    assert len(routed["regular_tokens"]) == 1
    assert routed["regular_tokens"][0]["token_id"] == "11536"


def test_stream_status_endpoint(test_client):
    """Verify GET /api/market-watch/stream-status returns telemetry payload."""
    resp = test_client.get("/api/market-watch/stream-status")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "websocket_connected" in data
    assert "subscriptions_count" in data
    assert "quotes_cached" in data
    assert "last_tick_timestamp" in data
    assert "last_tick_symbol" in data


def test_quotes_endpoint_returns_all_when_unfiltered(test_client):
    """Verify GET /api/market-watch/quotes returns all cached quotes when tokens omitted."""
    from app.market_watch.services.price_engine import price_engine
    price_engine.ingest_tick({
        "instrument_token": "99999",
        "exchange_segment": "nse_cm",
        "last_traded_price": 100.5,
    })

    resp = test_client.get("/api/market-watch/quotes")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert isinstance(data, dict)
    quotes = data.get("quotes", {})
    assert "nse_cm:99999" in quotes
    assert quotes["nse_cm:99999"]["ltp"] == 100.5
