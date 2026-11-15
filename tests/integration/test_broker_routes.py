import json
from unittest.mock import MagicMock


def _mock_neo_api_cls():
    instance = MagicMock()
    instance.totp_login.return_value = {"data": {"token": "view_tok_123", "sid": "view_sid_123"}}
    instance.totp_validate.return_value = {
        "data": {
            "token": "trade_tok_123",
            "sid": "trade_sid_123",
            "ucc": "NEOUCC",
            "greetingName": "Broker Operator",
        }
    }
    return MagicMock(return_value=instance)


def test_broker_api_endpoints_flow(client, monkeypatch):
    """Integration test: Register local user, query capabilities/status, login broker, restore and logout."""
    monkeypatch.setattr("app.broker.adapters.kotak_adapter.NeoAPI", _mock_neo_api_cls())
    # 1. Register local operator
    client.post(
        "/api/auth/register",
        data=json.dumps({
            "username": "broker_op",
            "email": "broker_op@terminal.local",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )

    # 2. Login to get user session token
    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "broker_op",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    user_token = login_resp.get_json()["data"]["token"]
    auth_header = {"Authorization": f"Bearer {user_token}"}

    # 3. Query broker status (unauthenticated broker)
    status_resp = client.get("/api/broker/status")
    assert status_resp.status_code == 200
    status_data = status_resp.get_json()
    assert "status" in status_data["data"]

    # 4. Query broker capabilities
    cap_resp = client.get("/api/broker/capabilities")
    assert cap_resp.status_code == 200
    cap_data = cap_resp.get_json()["data"]
    assert "NSE" in cap_data["supported_exchanges"]

    # 5. Broker Login via API
    b_login_resp = client.post(
        "/api/broker/login",
        headers=auth_header,
        data=json.dumps({
            "consumer_key": "neo_cons_key_123",
            "mobile_number": "9876543210",
            "ucc": "NEOUCC",
            "mpin": "123456",
            "totp_secret": "JBSWY3DPEHPK3PXP",
        }),
        content_type="application/json",
    )
    assert b_login_resp.status_code == 200
    b_login_data = b_login_resp.get_json()
    assert b_login_data["data"]["status"] == "AUTHENTICATED"
    assert b_login_data["data"]["broker_session"]["broker_name"] == "KOTAK_NEO"

    # 6. Broker Restore via API
    restore_resp = client.post(
        "/api/broker/restore",
        headers=auth_header,
    )
    assert restore_resp.status_code == 200
    assert restore_resp.get_json()["data"]["restored"] is True

    # 7. Broker Logout via API
    b_logout_resp = client.post(
        "/api/broker/logout",
        headers=auth_header,
    )
    assert b_logout_resp.status_code == 200
    assert b_logout_resp.get_json()["data"]["status"] == "DISCONNECTED"

