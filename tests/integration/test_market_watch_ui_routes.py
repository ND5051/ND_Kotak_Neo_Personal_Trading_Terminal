"""
Integration tests for Phase 11B: Market Watch & Order Ticket UI.
Verifies Watchlist grid, Scrip Search modal, 5-Level Depth popover,
Order Ticket (docked/floating), dry-run pre-flight validation, and ExecutionMode integration.
"""

import json
import pytest


@pytest.fixture
def auth_headers(client):
    """Register and log in test user to obtain valid authorization headers."""
    client.post(
        "/api/auth/register",
        data=json.dumps({
            "username": "mw_ui_user",
            "email": "mw_ui@example.com",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "mw_ui_user",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    token = login_resp.get_json()["data"]["token"]
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def test_terminal_loads_phase11b_components(client):
    """Verify /terminal loads Market Watch Grid, Search Palette, Depth Popover, and Order Ticket."""
    response = client.get("/terminal")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # 1. Market Watch Container & Tabs
    assert "market-watch-container" in html
    assert "mw-search-trigger" in html
    assert "mw-quota-badge" in html
    assert "mw-tabs-bar" in html
    assert "mw-scrip-list" in html

    # 2. Scrip Search Palette Modal
    assert "scrip-search-modal" in html
    assert "scrip-search-input" in html
    assert "segment-filter-bar" in html

    # 3. 5-Level Market Depth DOM Popover
    assert "market-depth-modal" in html
    assert "depth-ladder-container" in html
    assert "depth-pressure-track" in html
    assert "depth-buy-btn" in html
    assert "depth-sell-btn" in html

    # 4. Professional Order Ticket (Docked & Floating)
    assert "order-ticket-container" in html
    assert "ticket-header" in html
    assert "ticket-dock-toggle" in html
    assert "ticket-qty-input" in html
    assert "ticket-price-input" in html
    assert "ticket-trigger-input" in html
    assert "ticket-margin-strip" in html
    assert "ticket-mode-banner" in html
    assert "ticket-submit-btn" in html

    # 5. Asset Inclusions
    assert "market_watch.css" in html
    assert "market_watch.js" in html
    assert "order_ticket.js" in html


def test_phase11b_static_assets_served(client):
    """Verify all Phase 11B CSS and JavaScript static assets return HTTP 200."""
    # CSS
    css_resp = client.get("/static/css/market_watch.css")
    assert css_resp.status_code == 200
    css = css_resp.data.decode("utf-8")
    assert ".market-watch-container" in css
    assert ".scrip-hover-actions" in css
    assert ".order-ticket-container.docked" in css
    assert ".order-ticket-container.floating" in css
    assert ".depth-pressure-fill" in css

    # Market Watch JS
    mw_js_resp = client.get("/static/js/market_watch.js")
    assert mw_js_resp.status_code == 200
    mw_js = mw_js_resp.data.decode("utf-8")
    assert "class MarketWatchController" in mw_js
    assert "switchWatchlist" in mw_js
    assert "executeSearch" in mw_js
    assert "openMarketDepth" in mw_js

    # Order Ticket JS
    ot_js_resp = client.get("/static/js/order_ticket.js")
    assert ot_js_resp.status_code == 200
    ot_js = ot_js_resp.data.decode("utf-8")
    assert "class OrderTicketController" in ot_js
    assert "openTicket" in ot_js
    assert "setSide" in ot_js
    assert "runValidationAndMarginPreview" in ot_js
    assert "submitOrder" in ot_js


def test_watchlist_api_lifecycle_integration(client, auth_headers):
    """Verify backend Watchlist API supports user watchlists query and item operations."""
    # 1. Fetch watchlists
    resp = client.get("/api/market-watch/watchlists", headers=auth_headers)
    assert resp.status_code == 200
    watchlists = resp.get_json()["data"]["watchlists"]
    assert len(watchlists) > 0
    default_wl = watchlists[0]
    wl_id = default_wl["id"]

    # 2. Add an item
    add_resp = client.post(
        f"/api/market-watch/watchlists/{wl_id}/items",
        data=json.dumps({
            "instrument_token": "45299",
            "exchange_segment": "nse_fo",
            "trading_symbol": "NIFTY28NOV24500CE",
            "display_name": "NIFTY 28NOV 24500 CE"
        }),
        headers=auth_headers,
    )
    assert add_resp.status_code in [201, 400]  # 400 if duplicate, 201 if created


def test_scrip_search_api_integration(client):
    """Verify backend Scrip Master search endpoint returns structured instrument items."""
    resp = client.get("/api/market-watch/search?q=NIFTY&segment=nse_cm")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "instruments" in data
    assert isinstance(data["instruments"], list)


def test_order_preflight_validation_dry_run_endpoint(client, auth_headers):
    """Verify /api/orders/validate dry-run endpoint evaluates tick size and lot multipliers."""
    # Valid order payload
    valid_payload = {
        "instrument_token": "45210",
        "trading_symbol": "NIFTY28NOV24500CE",
        "exchange_segment": "nse_fo",
        "side": "BUY",
        "order_type": "LIMIT",
        "product_type": "MIS",
        "quantity": 25,
        "price": 142.50,
        "trigger_price": 0.0,
        "available_cash": 100000.0,
        "dry_run": True,
    }
    resp = client.post("/api/orders/validate", data=json.dumps(valid_payload), headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["valid"] is True

    # Invalid tick size modulo
    invalid_payload = dict(valid_payload)
    invalid_payload["price"] = 142.53  # Not multiple of 0.05
    err_resp = client.post("/api/orders/validate", data=json.dumps(invalid_payload), headers=auth_headers)
    assert err_resp.status_code == 200
    err_data = err_resp.get_json()["data"]
    assert err_data["valid"] is False
    assert len(err_data["validation_errors"]) > 0


def test_order_execution_mode_paper_placement(client, auth_headers):
    """Verify order placement executes in PAPER mode and is refused in DISABLED mode."""
    # 1. Ensure mode is PAPER
    client.post("/api/orders/mode", data=json.dumps({"mode": "PAPER"}), headers=auth_headers)

    order_payload = {
        "client_order_id": "test_phase11b_cli_01",
        "instrument_token": "2885",
        "trading_symbol": "RELIANCE",
        "exchange_segment": "nse_cm",
        "order_side": "BUY",
        "order_type": "LIMIT",
        "product_type": "CNC",
        "quantity": 10,
        "price": 2900.0,
        "available_cash": 100000.0,
    }
    place_resp = client.post("/api/orders/place", data=json.dumps(order_payload), headers=auth_headers)
    assert place_resp.status_code == 201
    assert place_resp.get_json()["data"]["mode"] == "PAPER"

    # 2. Switch to DISABLED and verify placement is refused
    client.post("/api/orders/mode", data=json.dumps({"mode": "DISABLED"}), headers=auth_headers)
    order_payload["client_order_id"] = "test_phase11b_cli_02"
    refused_resp = client.post("/api/orders/place", data=json.dumps(order_payload), headers=auth_headers)
    assert refused_resp.status_code == 403
    assert refused_resp.get_json()["error_code"] == "EXECUTION_MODE_DISABLED"
