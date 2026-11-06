"""
Integration tests for Order REST API Endpoints.
Phase 7: Order Domain Foundation.
Validates read-only order endpoints, dry-run validation, and execution prohibitions.
"""

import json
import pytest

from app import create_app
from app.orders.models.order import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
    TradeExecution,
    Validity,
)
from app.orders.repositories.order_repository import order_repository
from app.orders.services.order_state_machine import order_state_machine


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
            "username": "orders_user",
            "email": "orders@example.com",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )

    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "orders_user",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    token = login_resp.get_json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def test_orders_status_public_endpoint(client):
    """Verify GET /api/orders/status is public and execution_enabled is False."""
    resp = client.get("/api/orders/status")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["status"] == "active_phase_7"
    assert data["module"] == "order_domain_foundation"
    assert data["execution_enabled"] is False
    assert "LIMIT" in data["supported_order_types"]


def test_orders_validate_dry_run_endpoint(client, auth_headers):
    """Verify POST /api/orders/validate executes dry-run checks without order placement."""
    payload = {
        "instrument_token": "26000",
        "exchange_segment": "nse_cm",
        "trading_symbol": "RELIANCE",
        "side": "BUY",
        "order_type": "LIMIT",
        "product_type": "MIS",
        "quantity": 10,
        "price": 2450.00,
        "available_cash": 100000.00,
    }

    resp = client.post(
        "/api/orders/validate",
        data=json.dumps(payload),
        content_type="application/json",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    res_data = resp.get_json()["data"]
    assert res_data["valid"] is True
    assert res_data["syntax_valid"] is True
    assert res_data["risk_approved"] is True
    assert res_data["order"]["trading_symbol"] == "RELIANCE"
    assert len(res_data["validation_errors"]) == 0


def test_orders_validate_tick_error(client, auth_headers):
    """Verify POST /api/orders/validate returns validation errors on fractional tick."""
    payload = {
        "instrument_token": "26000",
        "exchange_segment": "nse_cm",
        "trading_symbol": "RELIANCE",
        "side": "BUY",
        "order_type": "LIMIT",
        "product_type": "MIS",
        "quantity": 10,
        "price": 2450.03,  # Invalid tick size
    }

    resp = client.post(
        "/api/orders/validate",
        data=json.dumps(payload),
        content_type="application/json",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    res_data = resp.get_json()["data"]
    assert res_data["valid"] is False
    assert res_data["syntax_valid"] is False
    assert any("multiple of tick size ₹0.05" in e for e in res_data["validation_errors"])


def test_orders_place_is_strictly_prohibited(client, auth_headers):
    """Verify POST /api/orders/place returns 405 Method Not Allowed."""
    resp = client.post(
        "/api/orders/place",
        data=json.dumps({"symbol": "RELIANCE", "qty": 10}),
        content_type="application/json",
        headers=auth_headers,
    )
    assert resp.status_code == 405
    err = resp.get_json()
    assert err["error_code"] == "EXECUTION_PROHIBITED_IN_PHASE_7"


def test_orders_order_book_and_filters(client, auth_headers):
    """Verify GET /api/orders returns filterable order book."""
    # Seed an order directly via repository
    test_order = Order(
        client_order_id="integration-ord-1",
        user_id=1,
        instrument_token="26000",
        exchange_segment="nse_cm",
        trading_symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.MIS,
        quantity=25,
        price=2400.00,
        status=OrderStatus.ACKNOWLEDGED,
    )
    order_repository.save_order(test_order)

    resp = client.get("/api/orders?status=open", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["total_count"] >= 1
    assert any(o["client_order_id"] == "integration-ord-1" for o in data["orders"])


def test_orders_get_detail_and_timeline(client, auth_headers):
    """Verify GET /api/orders/<client_order_id> returns order and transition timeline."""
    test_order = Order(
        client_order_id="timeline-ord-2",
        user_id=1,
        instrument_token="11536",
        exchange_segment="nse_cm",
        trading_symbol="TCS",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.CNC,
        quantity=5,
        price=3500.00,
        status=OrderStatus.PENDING_VALIDATION,
    )
    saved = order_repository.save_order(test_order)

    # Perform legal transition
    order_state_machine.transition(saved, OrderStatus.VALIDATED, reason="Syntax checks pass")

    resp = client.get("/api/orders/timeline-ord-2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["order"]["client_order_id"] == "timeline-ord-2"
    assert len(data["timeline"]) >= 1
    assert data["timeline"][0]["to_status"] == "VALIDATED"


def test_orders_trades_and_stats_endpoints(client, auth_headers):
    """Verify GET /api/orders/trades and GET /api/orders/stats endpoints."""
    # Seed order first
    test_order = Order(
        client_order_id="trade-order-3",
        user_id=1,
        instrument_token="26000",
        exchange_segment="nse_cm",
        trading_symbol="RELIANCE",
        quantity=10,
        price=2450.00,
        status=OrderStatus.FILLED,
    )
    order_repository.save_order(test_order)

    # Seed trade execution
    trade = TradeExecution(
        trade_id="TRD_INT_99",
        client_order_id="trade-order-3",
        broker_order_id="241106_BRK_99",
        fill_quantity=10,
        fill_price=2450.00,
        exchange_segment="nse_cm",
        trading_symbol="RELIANCE",
        exchange_timestamp="2026-11-06T10:00:00",
    )
    order_repository.record_trade_execution(trade)

    trades_resp = client.get("/api/orders/trades", headers=auth_headers)
    assert trades_resp.status_code == 200
    trades_data = trades_resp.get_json()["data"]
    assert trades_data["count"] >= 1

    stats_resp = client.get("/api/orders/stats", headers=auth_headers)
    assert stats_resp.status_code == 200
    stats_data = stats_resp.get_json()["data"]
    assert "total_orders" in stats_data
    assert "open_orders" in stats_data
