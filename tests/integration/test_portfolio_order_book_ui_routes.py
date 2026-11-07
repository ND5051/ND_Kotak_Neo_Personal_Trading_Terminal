"""
Integration tests for Phase 11C: Portfolio & Order Book UI.
Verifies Holdings screen, Positions screen with live MTM, Order Book with FSM filters,
Trade Book, Expanded Funds Ledger, Order Timeline modal, Position Quick Actions,
and Portfolio Refresh Controls.
"""

import json
import pytest


@pytest.fixture
def auth_headers(client):
    """Register and log in test user to obtain valid authorization headers."""
    client.post(
        "/api/auth/register",
        data=json.dumps({
            "username": "portfolio_ui_user",
            "email": "portfolio_ui@example.com",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "portfolio_ui_user",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    token = login_resp.get_json()["data"]["token"]
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def test_terminal_loads_phase11c_components(client):
    """Verify /terminal loads Holdings, Positions, Order Book, Trade Book, Funds, and Timeline modal."""
    response = client.get("/terminal")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # 1. Holdings View & Controls
    assert "holdings-container" in html
    assert "holdings-total-invested" in html
    assert "holdings-current-val" in html
    assert "holdings-total-pnl" in html
    assert "holdings-day-pnl" in html
    assert "holdings-table" in html
    assert "refresh-holdings-btn" in html
    assert "holdings-last-refreshed" in html

    # 2. Positions View & Controls
    assert "positions-container" in html
    assert "pos-realized-pnl" in html
    assert "pos-unrealized-mtm" in html
    assert "pos-net-pnl" in html
    assert "pos-exposure-margin" in html
    assert "positions-table" in html
    assert "pos-product-filter" in html
    assert "refresh-positions-btn" in html
    assert "positions-last-refreshed" in html
    assert "btn-square-off-all" in html
    assert "square-off-all-modal" in html
    assert "reverse-position-modal" in html
    assert "high-exposure-exit-modal" in html
    assert "high-exp-val" in html
    assert "high-exp-proceed-btn" in html

    # 3. Order Book & Filter Tabs
    assert "order-book-container" in html
    assert "orders-table" in html
    assert "order-status-tabs" in html
    assert "order-search-input" in html
    assert "refresh-orders-btn" in html
    assert "btn-cancel-all-orders" in html

    # 4. Trade Book View
    assert "trade-book-container" in html
    assert "trades-table" in html
    assert "trade-total-count" in html
    assert "trade-total-turnover" in html
    assert "refresh-trades-btn" in html

    # 5. Expanded Funds View & Margin Ledger
    assert "funds-expanded-container" in html
    assert "funds-avail-cash" in html
    assert "funds-collateral" in html
    assert "funds-mtm-credit" in html
    assert "funds-total-avail" in html
    assert "funds-span-margin" in html
    assert "funds-exposure-margin" in html
    assert "funds-premium-blocked" in html
    assert "funds-total-used" in html
    assert "funds-utilization-bar" in html
    assert "funds-utilization-pct" in html
    assert "refresh-funds-expanded-btn" in html

    # 6. Order Timeline & FSM Transition Modal
    assert "order-timeline-modal" in html
    assert "timeline-stepper" in html
    assert "step-node-draft" in html
    assert "step-node-validated" in html
    assert "step-node-submitted" in html
    assert "step-node-pending" in html
    assert "step-node-terminal" in html
    assert "timeline-event-list" in html

    # 7. Front-End Assets
    assert "portfolio.css" in html
    assert "portfolio.js" in html
    assert "order_book.js" in html


def test_phase11c_static_assets_served(client):
    """Verify CSS and JS assets for Phase 11C are served with 200 OK."""
    resp_css = client.get("/static/css/portfolio.css")
    assert resp_css.status_code == 200
    assert "portfolio-container" in resp_css.data.decode("utf-8")

    resp_pjs = client.get("/static/js/portfolio.js")
    assert resp_pjs.status_code == 200
    assert "PortfolioController" in resp_pjs.data.decode("utf-8")

    resp_ojs = client.get("/static/js/order_book.js")
    assert resp_ojs.status_code == 200
    assert "OrderBookController" in resp_ojs.data.decode("utf-8")


def test_portfolio_endpoints_integration(client, auth_headers):
    """Verify Portfolio REST endpoints return valid schemas and timestamps."""
    # 1. Holdings
    resp_h = client.get("/api/portfolio/holdings", headers=auth_headers)
    assert resp_h.status_code == 200
    data_h = resp_h.get_json()["data"]
    assert "count" in data_h
    assert isinstance(data_h["holdings"], list)

    # 2. Positions
    resp_p = client.get("/api/portfolio/positions?type=net&status=all", headers=auth_headers)
    assert resp_p.status_code == 200
    data_p = resp_p.get_json()["data"]
    assert data_p["position_type"] == "NET"
    assert "total_count" in data_p
    assert "open_count" in data_p
    assert "closed_count" in data_p
    assert isinstance(data_p["positions"], list)

    # 3. Margins
    resp_m = client.get("/api/portfolio/margins", headers=auth_headers)
    assert resp_m.status_code == 200
    data_m = resp_m.get_json()["data"]["margins"]
    assert "available_cash" in data_m
    assert "total_margin_used" in data_m

    # 4. PnL & Timestamps
    resp_pnl = client.get("/api/portfolio/pnl", headers=auth_headers)
    assert resp_pnl.status_code == 200
    data_pnl = resp_pnl.get_json()["data"]
    assert "realized_pnl" in data_pnl
    assert "unrealized_mtm" in data_pnl
    assert "retrieved_timestamp" in data_pnl
    assert "source_timestamp" in data_pnl

    # 5. Refresh Trigger
    resp_ref = client.post("/api/portfolio/refresh", headers=auth_headers)
    assert resp_ref.status_code == 200
    data_ref = resp_ref.get_json()["data"]
    assert data_ref["refreshed"] is True
    assert "summary" in data_ref


def test_orders_and_timeline_integration(client, auth_headers):
    """Verify order book, trade execution, and visual FSM timeline endpoints."""
    # 1. Query Order Book
    resp_orders = client.get("/api/orders", headers=auth_headers)
    assert resp_orders.status_code == 200
    data_o = resp_orders.get_json()["data"]
    assert "total_count" in data_o
    assert "open_count" in data_o
    assert isinstance(data_o["orders"], list)

    # 2. Query Trade Book
    resp_trades = client.get("/api/orders/trades", headers=auth_headers)
    assert resp_trades.status_code == 200
    data_t = resp_trades.get_json()["data"]
    assert "count" in data_t
    assert isinstance(data_t["trades"], list)

    # 3. Place Order in PAPER mode
    client.post("/api/orders/mode", data=json.dumps({"mode": "PAPER"}), headers=auth_headers)

    place_payload = {
        "trading_symbol": "RELIANCE",
        "exchange_segment": "nse_cm",
        "instrument_token": "2885",
        "side": "BUY",
        "order_type": "LIMIT",
        "product_type": "CNC",
        "quantity": 10,
        "price": 2850.0,
        "trigger_price": 0.0,
        "validity": "DAY",
        "available_cash": 100000.0,
    }
    place_resp = client.post("/api/orders/place", data=json.dumps(place_payload), headers=auth_headers)
    assert place_resp.status_code == 201
    order_data = place_resp.get_json()["data"]
    client_order_id = order_data["order"]["client_order_id"]

    # 4. Fetch Order Detail & Timeline Transitions
    detail_resp = client.get(f"/api/orders/{client_order_id}", headers=auth_headers)
    assert detail_resp.status_code == 200
    detail_data = detail_resp.get_json()["data"]
    assert "order" in detail_data
    assert "timeline" in detail_data
    assert detail_data["order"]["client_order_id"] == client_order_id
    assert isinstance(detail_data["timeline"], list)

    # 5. Mass Cancel All
    cancel_all_resp = client.post("/api/orders/cancel-all", headers=auth_headers)
    assert cancel_all_resp.status_code == 200
