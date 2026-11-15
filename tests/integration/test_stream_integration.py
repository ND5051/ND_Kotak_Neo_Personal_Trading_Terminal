import json
from unittest.mock import AsyncMock, MagicMock


def _mock_neo_api_cls():
    ws_mock = MagicMock()
    ws_mock.connect = AsyncMock(return_value=None)
    ws_mock.close = AsyncMock(return_value=None)
    ws_mock.subscribe_scrips = AsyncMock(return_value=None)
    ws_mock.subscribe_index = AsyncMock(return_value=None)

    instance = MagicMock()
    instance.totp_login.return_value = {"data": {"token": "view_tok_123", "sid": "view_sid_123"}}
    instance.totp_validate.return_value = {
        "data": {"token": "trade_tok_123", "sid": "trade_sid_123", "ucc": "STREAMUCC"}
    }
    instance.create_websocket.return_value = ws_mock
    return MagicMock(return_value=instance)


def test_stream_routes_and_diagnostics(client, monkeypatch):
    """Integration test: Register, login, broker login, start/stop stream, and inspect metrics."""
    monkeypatch.setattr("app.broker.adapters.kotak_adapter.NeoAPI", _mock_neo_api_cls())
    # 1. Register operator
    client.post(
        "/api/auth/register",
        data=json.dumps({
            "username": "stream_trader",
            "email": "stream@terminal.local",
            "password": "Password123!",
        }),
        content_type="application/json",
    )

    # 2. Login operator
    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "stream_trader",
            "password": "Password123!",
        }),
        content_type="application/json",
    )
    user_token = login_resp.get_json()["data"]["token"]
    headers = {"Authorization": f"Bearer {user_token}"}

    # 3. Query initial stream metrics endpoint
    metrics_resp = client.get("/api/broker/stream/metrics")
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.get_json()["data"]
    assert "state" in metrics_data
    assert "metrics" in metrics_data
    assert "connection_count" in metrics_data["metrics"]
    assert "reconnect_count" in metrics_data["metrics"]
    assert "heartbeat_miss_count" in metrics_data["metrics"]
    assert "avg_reconnect_time_ms" in metrics_data["metrics"]
    assert "last_connected_time" in metrics_data["metrics"]
    assert "circuit_breaker" in metrics_data

    # 4. Broker Login
    client.post(
        "/api/broker/login",
        headers=headers,
        data=json.dumps({
            "consumer_key": "stream_key_123",
            "mobile_number": "9876543210",
            "ucc": "STREAMUCC",
            "mpin": "123456",
            "totp_secret": "JBSWY3DPEHPK3PXP",
        }),
        content_type="application/json",
    )

    # 5. Start Streaming
    start_resp = client.post("/api/broker/stream/start", headers=headers)
    assert start_resp.status_code == 200
    assert start_resp.get_json()["data"]["started"] is True

    # 6. Query broker status to verify enriched streaming telemetry
    status_resp = client.get("/api/broker/status")
    assert status_resp.status_code == 200
    status_data = status_resp.get_json()["data"]
    assert "streaming" in status_data
    assert "metrics" in status_data["streaming"]

    # 7. Stop Streaming
    stop_resp = client.post("/api/broker/stream/stop", headers=headers)
    assert stop_resp.status_code == 200
    assert stop_resp.get_json()["data"]["stopped"] is True
