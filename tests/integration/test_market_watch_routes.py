"""
Integration tests for Market Watch REST API Endpoints.
Phase 5: Market Watch Foundation.
Validates search, watchlist CRUD, item pinning, and quote retrieval under real Flask app context.
"""

import json
import pytest

from app import create_app
from app.market_watch.services.price_engine import price_engine


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
            "username": "mw_test_user",
            "email": "mw_test@example.com",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )

    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "mw_test_user",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    token = login_resp.get_json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def test_market_watch_status_and_search(client):
    """Verify public status and autocomplete search endpoints."""
    # Status
    status_resp = client.get("/api/market-watch/status")
    assert status_resp.status_code == 200
    assert status_resp.get_json()["data"]["status"] == "active_phase_5"

    # Search
    search_resp = client.get("/api/market-watch/search?q=RELI")
    assert search_resp.status_code == 200
    res_data = search_resp.get_json()["data"]
    assert res_data["count"] >= 1
    symbols = [inst["trading_symbol"] for inst in res_data["instruments"]]
    assert "RELIANCE-EQ" in symbols

    # Short query fails with 400
    err_resp = client.get("/api/market-watch/search?q=A")
    assert err_resp.status_code == 400


def test_watchlist_rest_api_lifecycle(client, auth_headers):
    """Verify complete CRUD lifecycle of watchlists via REST API."""
    # 1. Fetch initial watchlists (triggers Default Watchlist auto-initialization)
    list_resp = client.get("/api/market-watch/watchlists", headers=auth_headers)
    assert list_resp.status_code == 200
    wls = list_resp.get_json()["data"]["watchlists"]
    assert len(wls) >= 1
    assert wls[0]["is_default"] is True
    assert len(wls[0]["items"]) == 4

    # 2. Create custom watchlist
    create_resp = client.post(
        "/api/market-watch/watchlists",
        json={"name": "Energy Movers"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    created_wl = create_resp.get_json()["data"]["watchlist"]
    wl_id = created_wl["id"]
    assert created_wl["name"] == "Energy Movers"

    # 3. Add item to watchlist
    add_resp = client.post(
        f"/api/market-watch/watchlists/{wl_id}/items",
        json={
            "instrument_token": "2885",
            "exchange_segment": "nse_cm",
            "trading_symbol": "RELIANCE-EQ",
            "display_name": "Reliance Industries Limited",
        },
        headers=auth_headers,
    )
    assert add_resp.status_code == 201
    item_id = add_resp.get_json()["data"]["item"]["id"]

    # 4. Simulate tick and verify quotes snapshot
    price_engine.ingest_tick({
        "instrument_token": "2885",
        "exchange_segment": "nse_cm",
        "trading_symbol": "RELIANCE-EQ",
        "ltp": 2550.0,
    })

    quotes_resp = client.get(
        "/api/market-watch/quotes?tokens=nse_cm:2885", headers=auth_headers
    )
    assert quotes_resp.status_code == 200
    q_data = quotes_resp.get_json()["data"]["quotes"]
    assert "nse_cm:2885" in q_data
    assert q_data["nse_cm:2885"]["ltp"] == 2550.0

    # 5. Remove item
    del_item_resp = client.delete(
        f"/api/market-watch/watchlists/{wl_id}/items/{item_id}",
        headers=auth_headers,
    )
    assert del_item_resp.status_code == 200
    assert del_item_resp.get_json()["data"]["removed"] is True

    # 6. Delete watchlist
    del_wl_resp = client.delete(
        f"/api/market-watch/watchlists/{wl_id}", headers=auth_headers
    )
    assert del_wl_resp.status_code == 200
    assert del_wl_resp.get_json()["data"]["deleted"] is True
