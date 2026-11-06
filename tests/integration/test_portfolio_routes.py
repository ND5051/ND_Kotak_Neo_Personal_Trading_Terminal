"""
Integration tests for Portfolio REST API Endpoints.
Phase 6: Portfolio Foundation.
Validates /summary, /holdings, /positions, /margins, /pnl, /refresh, and dual timestamps.
"""

import json
import pytest

from app import create_app
from app.market_watch.services.price_engine import price_engine
from app.portfolio.models.holding import Holding
from app.portfolio.models.margin import MarginSummary
from app.portfolio.models.position import Position, PositionType, ProductCode
from app.portfolio.services.portfolio_service import portfolio_service


@pytest.fixture
def app_instance():
    """Create test application."""
    app = create_app("testing")
    return app


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


@pytest.fixture
def auth_headers(client):
    """Register and log in test user to obtain valid authorization headers."""
    client.post(
        "/api/auth/register",
        data=json.dumps({
            "username": "portfolio_user",
            "email": "portfolio@example.com",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )

    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "portfolio_user",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    token = login_resp.get_json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_portfolio_data():
    """Seed working portfolio data into PortfolioService and MTMEngine."""
    h = Holding(
        instrument_token="2885",
        exchange_segment="nse_cm",
        trading_symbol="RELIANCE-EQ",
        isin="INE002A01018",
        total_quantity=50,
        settled_quantity=50,
        t1_quantity=0,
        pledged_quantity=0,
        average_price=2400.0,
        invested_value=120000.0,
        current_price=2500.0,
        current_value=125000.0,
        unrealized_pnl=5000.0,
        unrealized_pnl_percent=4.17,
        close_price=2480.0,
        day_pnl=1000.0,
        day_pnl_percent=0.81,
        source_timestamp="2026-11-06T06:00:00Z",
    )
    p = Position(
        instrument_token="26000",
        exchange_segment="nse_fo",
        trading_symbol="NIFTY24DEC24500CE",
        product=ProductCode.NRML,
        position_type=PositionType.NET,
        buy_quantity=50,
        buy_amount=6000.0,
        average_buy_price=120.0,
        sell_quantity=0,
        sell_amount=0.0,
        average_sell_price=0.0,
        net_quantity=50,
        current_price=130.0,
        realized_pnl=0.0,
        unrealized_pnl=500.0,
        total_pnl=500.0,
        is_open=True,
        source_timestamp="2026-11-06T06:15:00Z",
    )
    m = MarginSummary(
        available_cash=100000.0,
        collateral_value=50000.0,
        total_margin_available=150000.0,
        total_margin_used=30000.0,
        margin_utilization_percent=20.0,
        source_timestamp="2026-11-06T06:30:00Z",
    )

    portfolio_service.cache.set("portfolio:holdings", [h], ttl_seconds=300.0)
    portfolio_service.cache.set("portfolio:positions:net", [p], ttl_seconds=300.0)
    portfolio_service.cache.set("portfolio:margins", m, ttl_seconds=300.0)
    portfolio_service.mtm_engine.set_positions([p])


def test_portfolio_public_status(client):
    """Verify unauthenticated status endpoint."""
    resp = client.get("/api/portfolio/status")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "active_phase_6"


def test_portfolio_summary_and_timestamps(client, auth_headers, mock_portfolio_data):
    """Verify /summary endpoint and presence of dual timestamps."""
    resp = client.get("/api/portfolio/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]["summary"]

    assert data["total_invested_value"] == 120000.0
    assert data["current_holdings_value"] == 125000.0
    assert data["holdings_unrealized_pnl"] == 5000.0
    assert data["unrealized_mtm"] == 500.0
    assert data["total_trading_pnl"] == 500.0
    assert data["total_portfolio_pnl"] == 5500.0  # 5000 holdings + 500 trading
    assert data["available_cash"] == 100000.0
    assert data["margin_utilization_percent"] == 20.0
    assert data["open_positions_count"] == 1
    assert data["total_holdings_count"] == 1

    # Dual Timestamps
    assert data["source_timestamp"] == "2026-11-06T06:30:00Z"
    assert data["retrieved_timestamp"] is not None
    assert "T" in data["retrieved_timestamp"]


def test_portfolio_holdings_route(client, auth_headers, mock_portfolio_data):
    """Verify /holdings endpoint returns normalized holdings."""
    resp = client.get("/api/portfolio/holdings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["count"] == 1
    h = data["holdings"][0]
    assert h["trading_symbol"] == "RELIANCE-EQ"
    assert h["invested_value"] == 120000.0
    assert h["source_timestamp"] == "2026-11-06T06:00:00Z"
    assert h["retrieved_timestamp"] is not None


def test_portfolio_positions_route(client, auth_headers, mock_portfolio_data):
    """Verify /positions endpoint with filter options."""
    resp = client.get("/api/portfolio/positions?type=net&status=open", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["open_count"] == 1
    p = data["positions"][0]
    assert p["trading_symbol"] == "NIFTY24DEC24500CE"
    assert p["net_quantity"] == 50
    assert p["source_timestamp"] == "2026-11-06T06:15:00Z"
    assert p["retrieved_timestamp"] is not None


def test_portfolio_margins_route(client, auth_headers, mock_portfolio_data):
    """Verify /margins endpoint."""
    resp = client.get("/api/portfolio/margins", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]["margins"]
    assert data["available_cash"] == 100000.0
    assert data["margin_utilization_percent"] == 20.0
    assert data["source_timestamp"] == "2026-11-06T06:30:00Z"


def test_portfolio_pnl_route(client, auth_headers, mock_portfolio_data):
    """Verify /pnl breakdown endpoint."""
    resp = client.get("/api/portfolio/pnl", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["unrealized_mtm"] == 500.0
    assert data["holdings_unrealized_pnl"] == 5000.0
    assert data["total_portfolio_pnl"] == 5500.0


def test_portfolio_refresh_route(client, auth_headers, mock_portfolio_data):
    """Verify POST /refresh endpoint forces cache invalidation."""
    resp = client.post("/api/portfolio/refresh", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["refreshed"] is True
    assert "summary" in data
