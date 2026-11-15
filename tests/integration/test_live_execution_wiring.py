import json
from unittest.mock import MagicMock

from app.broker.adapters.kotak_adapter import kotak_adapter
from app.broker.adapters.kotak_order_adapter import kotak_order_adapter
from app.broker.services.broker_client_sync import sync_shared_broker_client
from app.broker.services.websocket_supervisor import ws_supervisor
from app.orders.models.execution_mode import ExecutionMode, execution_mode_manager
from app.orders.repositories.order_repository import order_repository
from app.portfolio.services.portfolio_service import portfolio_service


def test_live_mode_safety_guard_and_shared_client_wiring(client):
    """
    Verify P1 fix:
    1. GET /api/broker/client-state reports disconnected/mock state initially.
    2. LIVE mode order placement with disconnected/mock adapter returns HTTP 503
       and creates ZERO orders, broker_order_ids, or TradeExecution records.
    3. Shared client sync wires the exact same client instance across
       kotak_adapter, kotak_order_adapter, portfolio_service.adapter, and ws_supervisor.adapter.
    4. Broker logout clears shared client across all adapters.
    """
    prev_mode = execution_mode_manager.get_mode()
    sync_shared_broker_client(None)

    try:
        # 1. Register & login operator
        client.post(
            "/api/auth/register",
            data=json.dumps({
                "username": "live_wiring_op",
                "email": "livewiring@terminal.local",
                "password": "Password123!",
            }),
            content_type="application/json",
        )
        login_resp = client.post(
            "/api/auth/login",
            data=json.dumps({
                "username": "live_wiring_op",
                "password": "Password123!",
            }),
            content_type="application/json",
        )
        token = login_resp.get_json()["data"]["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Verify initial /api/broker/client-state
        cs_resp = client.get("/api/broker/client-state")
        assert cs_resp.status_code == 200
        cs_data = cs_resp.get_json()["data"]
        assert cs_data["broker_authenticated"] is False
        assert cs_data["execution_adapter_connected"] is False
        assert cs_data["streaming_adapter_connected"] is False
        assert cs_data["is_mock"] is True

        # 3. Switch to LIVE mode & verify Safety Guard blocks order with HTTP 503
        mode_resp = client.post(
            "/api/orders/mode",
            headers=headers,
            data=json.dumps({"mode": "LIVE", "reason": "Testing LIVE safety guard"}),
            content_type="application/json",
        )
        assert mode_resp.status_code == 200

        pre_trades_count = len(order_repository.get_trades(limit=100))

        place_resp = client.post(
            "/api/orders/place",
            headers=headers,
            data=json.dumps({
                "client_order_id": "live_guard_test_001",
                "trading_symbol": "HDFCBANK-EQ",
                "exchange_segment": "nse_cm",
                "side": "BUY",
                "order_type": "LIMIT",
                "product_type": "CNC",
                "quantity": 1,
                "price": 1600.0,
            }),
            content_type="application/json",
        )
        assert place_resp.status_code == 503
        place_json = place_resp.get_json()
        assert place_json["error_code"] == "BROKER_CLIENT_NOT_CONNECTED"

        # Confirm zero phantom order or TradeExecution records were created
        assert order_repository.find_by_client_order_id("live_guard_test_001") is None
        assert len(order_repository.get_trades(limit=100)) == pre_trades_count

        # 4. Verify shared client propagation across all adapters
        fake_sdk_client = MagicMock()
        fake_sdk_client.__is_mock__ = False
        sync_shared_broker_client(fake_sdk_client)

        assert kotak_adapter.client is fake_sdk_client
        assert kotak_order_adapter.client is fake_sdk_client
        assert portfolio_service.adapter is kotak_adapter
        assert portfolio_service.adapter.client is fake_sdk_client
        assert ws_supervisor.adapter.client is fake_sdk_client

        cs_connected = client.get("/api/broker/client-state").get_json()["data"]
        assert cs_connected["execution_adapter_connected"] is True
        assert cs_connected["streaming_adapter_connected"] is True
        assert cs_connected["is_mock"] is False

        # 5. Verify broker logout clears shared client across all adapters
        logout_resp = client.post("/api/broker/logout", headers=headers)
        assert logout_resp.status_code == 200
        assert kotak_adapter.client is None
        assert kotak_order_adapter.client is None
        assert ws_supervisor.adapter.client is None

    finally:
        sync_shared_broker_client(None)
        execution_mode_manager.set_mode(prev_mode, actor="test_cleanup")

