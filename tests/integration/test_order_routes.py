"""
Integration tests for Order REST API Endpoints.
Phase 8: Order Execution Foundation.
Validates execution mode gating, live/paper order placement, modification,
cancellation, dry-run validation, and status tracking.
"""

import json
import pytest

from app import create_app
from app.orders.models.execution_mode import (
    execution_mode_manager,
    ExecutionMode,
)
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
    """Verify GET /api/orders/status is public and reflects ExecutionMode."""
    execution_mode_manager.set_mode(ExecutionMode.DISABLED)
    resp = client.get("/api/orders/status")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["status"] == "operational"
    assert data["execution_mode"] == "DISABLED"
    assert data["execution_enabled"] is False
    assert "LIMIT" in data["supported_order_types"]


def test_orders_place_refused_when_disabled(client, auth_headers):
    """Verify POST /api/orders/place returns 403 when execution mode is DISABLED."""
    execution_mode_manager.set_mode(ExecutionMode.DISABLED)
    resp = client.post(
        "/api/orders/place",
        data=json.dumps({
            "trading_symbol": "RELIANCE-EQ",
            "quantity": 10,
            "price": 2450.05,
            "side": "BUY",
        }),
        content_type="application/json",
        headers=auth_headers,
    )
    assert resp.status_code == 403
    err = resp.get_json()
    assert err["error_code"] == "EXECUTION_MODE_DISABLED"


def test_orders_execution_mode_switching_and_paper_placement(client, auth_headers):
    """Verify switching mode to PAPER and successfully placing a paper order."""
    # 1. Switch mode to PAPER
    mode_resp = client.post(
        "/api/orders/mode",
        data=json.dumps({"mode": "PAPER"}),
        content_type="application/json",
        headers=auth_headers,
    )
    assert mode_resp.status_code == 200
    assert mode_resp.get_json()["data"]["execution_mode"] == "PAPER"

    # 2. Place Order in PAPER mode
    place_resp = client.post(
        "/api/orders/place",
        data=json.dumps({
            "client_order_id": "int_test_paper_01",
            "trading_symbol": "RELIANCE",
            "exchange_segment": "nse_cm",
            "side": "BUY",
            "order_type": "LIMIT",
            "product_type": "MIS",
            "quantity": 5,
            "price": 2450.05,
            "available_cash": 100000.0,
        }),
        content_type="application/json",
        headers=auth_headers,
    )
    assert place_resp.status_code == 201
    place_data = place_resp.get_json()["data"]
    assert place_data["success"] is True
    assert place_data["mode"] == "PAPER"
    assert place_data["order"]["broker_order_id"].startswith("PAPER_")


def test_orders_modify_and_cancel_routes(client, auth_headers):
    """Verify modifying and cancelling an open order via REST API."""
    execution_mode_manager.set_mode(ExecutionMode.PAPER)

    # 1. Place order
    place_resp = client.post(
        "/api/orders/place",
        data=json.dumps({
            "client_order_id": "int_test_mod_canc_02",
            "trading_symbol": "TCS-EQ",
            "exchange_segment": "nse_cm",
            "side": "BUY",
            "order_type": "LIMIT",
            "product_type": "MIS",
            "quantity": 10,
            "price": 3500.00,
            "available_cash": 100000.0,
        }),
        content_type="application/json",
        headers=auth_headers,
    )
    assert place_resp.status_code == 201

    # 2. Modify order
    mod_resp = client.put(
        "/api/orders/int_test_mod_canc_02/modify",
        data=json.dumps({"price": 3510.05, "quantity": 10}),
        content_type="application/json",
        headers=auth_headers,
    )
    assert mod_resp.status_code == 200
    assert mod_resp.get_json()["data"]["order"]["price"] == 3510.05

    # 3. Cancel order
    canc_resp = client.delete(
        "/api/orders/int_test_mod_canc_02/cancel",
        headers=auth_headers,
    )
    assert canc_resp.status_code == 200
    assert canc_resp.get_json()["data"]["status"] == "CANCELLED"


def test_orders_cancel_all_emergency_kill_switch(client, auth_headers):
    """Verify emergency mass cancel all route."""
    execution_mode_manager.set_mode(ExecutionMode.PAPER)

    resp = client.post(
        "/api/orders/cancel-all",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["success"] is True


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
        "price": 2450.05,
        "available_cash": 50000.0,
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
    assert res_data["estimated_margin_required"] > 0
    assert len(res_data["validation_errors"]) == 0


def test_orders_validate_tick_error(client, auth_headers):
    """Verify POST /api/orders/validate flags tick size error."""
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


def test_orders_order_book_and_filters(client, auth_headers):
    """Verify GET /api/orders order book listing and filtering."""
    resp = client.get("/api/orders", headers=auth_headers)
    assert resp.status_code == 200
    res_data = resp.get_json()["data"]
    assert "total_count" in res_data
    assert "orders" in res_data


def test_orders_get_detail_and_timeline(client, auth_headers):
    """Verify GET /api/orders/<id> retrieves full order detail and transition history."""
    # Seed an order in repository
    order = Order(
        client_order_id="test_detail_client_id_01",
        broker_order_id="260930000169351",
        user_id=1,
        trading_symbol="RELIANCE",
        exchange_segment="nse_cm",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.MIS,
        quantity=10,
        price=2450.05,
        status=OrderStatus.PENDING_VALIDATION,
    )
    order_repository.save_order(order)
    order_state_machine.transition_to(order, OrderStatus.VALIDATED, reason="Pre-flight passed")

    resp = client.get(f"/api/orders/{order.client_order_id}", headers=auth_headers)
    assert resp.status_code == 200
    res_data = resp.get_json()["data"]
    assert res_data["order"]["client_order_id"] == order.client_order_id
    assert len(res_data["timeline"]) >= 1


def test_orders_trades_and_stats_endpoints(client, auth_headers):
    """Verify /api/orders/trades and /api/orders/stats endpoints."""
    # Seed an order and trade execution
    order = Order(
        client_order_id="test_trade_order_99",
        broker_order_id="260930000199999",
        user_id=1,
        trading_symbol="INFY",
        exchange_segment="nse_cm",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.MIS,
        quantity=5,
        price=1800.00,
        status=OrderStatus.FILLED,
    )
    order_repository.save_order(order)

    trade = TradeExecution(
        trade_id="trade_12345",
        client_order_id=order.client_order_id,
        broker_order_id=order.broker_order_id,
        trading_symbol="INFY",
        exchange_segment="nse_cm",
        fill_quantity=5,
        fill_price=1800.00,
        exchange_timestamp="2026-11-06T10:00:00Z",
    )
    order_repository.record_trade_execution(trade)

    trades_resp = client.get("/api/orders/trades", headers=auth_headers)
    assert trades_resp.status_code == 200
    trades_data = trades_resp.get_json()["data"]
    assert trades_data["count"] >= 1

    stats_resp = client.get("/api/orders/stats", headers=auth_headers)
    assert stats_resp.status_code == 200
    stats_data = stats_resp.get_json()["data"]
    assert stats_data["total_orders"] >= 1
