import json
import pytest

from app import create_app
from app.baskets.models.basket import BasketState, StrategyType
from app.baskets.repositories.basket_repository import basket_repository
from app.orders.models.execution_mode import ExecutionMode, execution_mode_manager


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
            "username": "baskets_user",
            "email": "baskets@example.com",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "baskets_user",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    token = login_resp.get_json()["data"]["token"]
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def test_baskets_status_public_endpoint(client):
    """Verify GET /api/baskets/status public endpoint."""
    resp = client.get("/api/baskets/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["data"]["status"] == "operational"
    assert "supported_strategies" in data["data"]
    assert "BULL_CALL_SPREAD" in data["data"]["supported_strategies"]
    assert data["data"]["default_execution_mode"] == "SEQUENTIAL"


def test_baskets_create_and_detail(client, auth_headers):
    """Verify POST /api/baskets and GET /api/baskets/<id>."""
    payload = {
        "client_basket_id": "int_test_bkt_01",
        "name": "Integration Test Spread",
        "strategy_type": "BULL_CALL_SPREAD",
        "legs": [
            {
                "trading_symbol": "NIFTY26NOV24500CE",
                "exchange_segment": "nse_fo",
                "side": "BUY",
                "order_type": "LIMIT",
                "product_type": "MIS",
                "quantity": 50,
                "price": 145.20,
            },
            {
                "trading_symbol": "NIFTY26NOV24700CE",
                "exchange_segment": "nse_fo",
                "side": "SELL",
                "order_type": "LIMIT",
                "product_type": "MIS",
                "quantity": 50,
                "price": 62.50,
            },
        ],
    }

    create_resp = client.post("/api/baskets", data=json.dumps(payload), headers=auth_headers)
    assert create_resp.status_code == 201
    create_data = create_resp.get_json()["data"]
    assert create_data["client_basket_id"] == "int_test_bkt_01"
    assert create_data["status"] == "DRAFT"
    assert create_data["total_legs"] == 2

    # Get Detail
    bkt_id = create_data["client_basket_id"]
    get_resp = client.get(f"/api/baskets/{bkt_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    detail_data = get_resp.get_json()["data"]
    assert detail_data["client_basket_id"] == "int_test_bkt_01"
    assert len(detail_data["legs"]) == 2
    assert "events" in detail_data


def test_baskets_validate_dry_run(client, auth_headers):
    """Verify POST /api/baskets/validate endpoint."""
    payload = {
        "client_basket_id": "int_test_bkt_val_02",
        "strategy_type": "BULL_CALL_SPREAD",
        "available_margin": 200000.0,
        "legs": [
            {
                "trading_symbol": "NIFTY26NOV24500CE",
                "exchange_segment": "nse_fo",
                "side": "BUY",
                "quantity": 50,
                "price": 100.0,
            },
            {
                "trading_symbol": "NIFTY26NOV24700CE",
                "exchange_segment": "nse_fo",
                "side": "SELL",
                "quantity": 50,
                "price": 40.0,
            },
        ],
    }

    resp = client.post("/api/baskets/validate", data=json.dumps(payload), headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["valid"] is True
    assert data["strategy_syntax_passed"] is True
    assert data["risk_checks_passed"] is True
    assert "margin_snapshot" in data


def test_baskets_execute_refused_when_disabled(client, auth_headers):
    """Verify POST /api/baskets/<id>/execute is refused with 403 when DISABLED."""
    execution_mode_manager.set_mode(ExecutionMode.DISABLED)

    payload = {
        "client_basket_id": "int_test_bkt_exec_dis",
        "strategy_type": "CUSTOM",
        "legs": [
            {"trading_symbol": "INFY-EQ", "exchange_segment": "nse_cm", "side": "BUY", "quantity": 10, "price": 1500.0}
        ],
    }
    create_resp = client.post("/api/baskets", data=json.dumps(payload), headers=auth_headers)
    bkt_id = create_resp.get_json()["data"]["client_basket_id"]

    exec_resp = client.post(f"/api/baskets/{bkt_id}/execute", headers=auth_headers)
    assert exec_resp.status_code == 403
    assert exec_resp.get_json()["error_code"] == "EXECUTION_MODE_DISABLED"


def test_baskets_execute_success_in_paper_mode(client, auth_headers):
    """Verify execution succeeds in PAPER mode."""
    execution_mode_manager.set_mode(ExecutionMode.PAPER)

    payload = {
        "client_basket_id": "int_test_bkt_exec_paper",
        "strategy_type": "CUSTOM",
        "legs": [
            {"trading_symbol": "TCS-EQ", "exchange_segment": "nse_cm", "side": "BUY", "quantity": 5, "price": 3500.0}
        ],
    }
    create_resp = client.post("/api/baskets", data=json.dumps(payload), headers=auth_headers)
    bkt_id = create_resp.get_json()["data"]["client_basket_id"]

    exec_resp = client.post(f"/api/baskets/{bkt_id}/execute", headers=auth_headers)
    assert exec_resp.status_code == 200
    data = exec_resp.get_json()["data"]
    assert data["success"] is True
    assert data["execution_mode"] == "PAPER"
    assert data["status"] == "EXECUTED"


def test_baskets_cancel_endpoint(client, auth_headers):
    """Verify POST /api/baskets/<id>/cancel transitions basket to CANCELLED."""
    payload = {
        "client_basket_id": "int_test_bkt_cancel_01",
        "strategy_type": "CUSTOM",
        "legs": [
            {"trading_symbol": "INFY-EQ", "exchange_segment": "nse_cm", "side": "BUY", "quantity": 10, "price": 1500.0}
        ],
    }
    create_resp = client.post("/api/baskets", data=json.dumps(payload), headers=auth_headers)
    bkt_id = create_resp.get_json()["data"]["client_basket_id"]

    cancel_resp = client.post(f"/api/baskets/{bkt_id}/cancel", headers=auth_headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.get_json()["data"]["status"] == "CANCELLED"
