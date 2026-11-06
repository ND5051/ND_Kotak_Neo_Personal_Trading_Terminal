"""
Integration Tests for Option Chain Workbench REST Controller.
Phase 10: Option Chain Workbench.
"""

import json
import pytest

from app import create_app


@pytest.fixture
def app_instance():
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
            "username": "chain_trader",
            "email": "chain_trader@example.com",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )

    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "chain_trader",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    token = login_resp.get_json()["data"]["token"]
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def test_option_chain_underlyings_route(client, auth_headers):
    """Verify GET /api/option-chain/underlyings endpoint."""
    resp = client.get("/api/option-chain/underlyings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "underlyings" in data
    symbols = [u["symbol"] for u in data["underlyings"]]
    assert "NIFTY" in symbols
    assert "BANKNIFTY" in symbols
    assert data["total"] >= 5


def test_option_chain_expiries_route(client, auth_headers):
    """Verify GET /api/option-chain/expiries endpoint."""
    resp = client.get("/api/option-chain/expiries?symbol=NIFTY", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["symbol"] == "NIFTY"
    assert len(data["expiries"]) > 0
    assert "expiry_date" in data["expiries"][0]
    assert "days_to_expiry" in data["expiries"][0]


def test_option_chain_matrix_route_with_presets(client, auth_headers):
    """Verify GET /api/option-chain with ATM ±5 and ATM ±10 presets."""
    # 1. Preset ATM_5 (5 down + 1 ATM + 5 up = 11 strikes)
    resp5 = client.get("/api/option-chain?symbol=NIFTY&preset=ATM_5", headers=auth_headers)
    assert resp5.status_code == 200
    data5 = resp5.get_json()["data"]
    assert data5["underlying_symbol"] == "NIFTY"
    assert data5["preset"] == "ATM_5"
    assert len(data5["strikes"]) == 11
    assert data5["pcr_oi"] >= 0.0
    assert "oi_source_timestamp" in data5
    assert "retrieved_timestamp" in data5

    # Verify ATM row is tagged
    atm_rows = [s for s in data5["strikes"] if s["is_atm"]]
    assert len(atm_rows) == 1
    assert atm_rows[0]["call_quote"]["moneyness"] == "ATM"
    assert atm_rows[0]["put_quote"]["moneyness"] == "ATM"

    # 2. Preset ATM_10 (10 down + 1 ATM + 10 up = 21 strikes)
    resp10 = client.get("/api/option-chain?symbol=NIFTY&preset=ATM_10", headers=auth_headers)
    assert resp10.status_code == 200
    data10 = resp10.get_json()["data"]
    assert len(data10["strikes"]) == 21


def test_option_chain_pcr_endpoint(client, auth_headers):
    """Verify GET /api/option-chain/pcr summary endpoint."""
    resp = client.get("/api/option-chain/pcr?symbol=NIFTY", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["underlying_symbol"] == "NIFTY"
    assert "pcr_oi" in data
    assert "pcr_volume" in data
    assert "total_call_oi" in data
    assert "total_put_oi" in data
    assert "oi_source_timestamp" in data


def test_option_chain_favourites_endpoints(client, auth_headers):
    """Verify GET and POST /api/option-chain/favourites."""
    # 1. Query initial favourites
    get_resp = client.get("/api/option-chain/favourites", headers=auth_headers)
    assert get_resp.status_code == 200
    favs = get_resp.get_json()["data"]["favourites"]
    assert len(favs) >= 2

    # 2. Pin RELIANCE
    post_resp = client.post(
        "/api/option-chain/favourites",
        data=json.dumps({"symbol": "RELIANCE", "is_favourite": True}),
        headers=auth_headers,
    )
    assert post_resp.status_code == 200
    assert post_resp.get_json()["data"]["is_favourite"] is True

    # 3. Verify RELIANCE is now in favourites
    get_resp2 = client.get("/api/option-chain/favourites", headers=auth_headers)
    symbols = [f["symbol"] for f in get_resp2.get_json()["data"]["favourites"]]
    assert "RELIANCE" in symbols


def test_option_chain_build_strategy_endpoint(client, auth_headers):
    """Verify POST /api/option-chain/build-strategy bridge to Phase 9 Basket Builder."""
    payload = {
        "strategy_type": "BULL_CALL_SPREAD",
        "underlying": "NIFTY",
        "expiry_token": "26NOV",
        "buy_strike": 24500.0,
        "sell_strike": 24700.0,
        "lot_size": 25,
        "lots": 1,
    }
    resp = client.post("/api/option-chain/build-strategy", data=json.dumps(payload), headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["strategy_type"] == "BULL_CALL_SPREAD"
    assert len(data["legs"]) == 2
    assert "client_basket_id" in data


def test_option_chain_watchlist_add_endpoint(client, auth_headers):
    """Verify POST /api/option-chain/watchlist/add bridge to Phase 5 Watchlist."""
    payload = {
        "trading_symbol": "NIFTY26NOV24500CE",
        "exchange_segment": "nse_fo",
        "instrument_token": "45210",
    }
    resp = client.post("/api/option-chain/watchlist/add", data=json.dumps(payload), headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["trading_symbol"] == "NIFTY26NOV24500CE"
