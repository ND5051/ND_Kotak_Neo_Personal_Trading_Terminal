import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.broker.adapters import kotak_adapter as ka_mod
from app.broker.adapters import kotak_stream_adapter as ksa_mod
from app.broker.adapters.kotak_adapter import KotakBrokerAdapter
from app.broker.adapters.kotak_stream_adapter import KotakStreamAdapter
from app.broker.cache.broker_cache import broker_cache
from app.broker.services.broker_client_sync import sync_shared_broker_client
from app.core.exceptions import BrokerException


@pytest.fixture(autouse=True)
def cleanup():
    broker_cache.clear()
    sync_shared_broker_client(None)
    yield
    broker_cache.clear()
    sync_shared_broker_client(None)


def test_neo_api_client_imported_in_adapters():
    """Verify both adapters import neo_api_client.NeoAPI instead of falling back to None."""
    from neo_api_client import NeoAPI as InstalledNeoAPI

    assert ka_mod.NeoAPI is InstalledNeoAPI
    assert ksa_mod.NeoAPI is InstalledNeoAPI


def test_kotak_adapter_uses_totp_login_and_validate_without_consumer_secret(monkeypatch):
    """Verify KotakBrokerAdapter instantiates NeoAPI(consumer_key, environment) and runs totp_login -> totp_validate."""
    created_kwargs = {}
    sdk_instance = MagicMock()
    sdk_instance.totp_login.return_value = {"data": {"token": "view_tok", "sid": "view_sid"}}
    sdk_instance.totp_validate.return_value = {
        "data": {
            "token": "trade_tok_xyz",
            "sid": "trade_sid_xyz",
            "ucc": "SDKUCC1",
            "greetingName": "SDK User",
        }
    }

    def fake_neo_api(**kwargs):
        created_kwargs.update(kwargs)
        return sdk_instance

    monkeypatch.setattr("app.broker.adapters.kotak_adapter.NeoAPI", fake_neo_api)

    adapter = KotakBrokerAdapter()
    result = adapter.login(
        {
            "consumer_key": "ck_live_123",
            "consumer_secret": "ignored_legacy_secret",
            "mobile_number": "+919876543210",
            "ucc": "SDKUCC1",
            "mpin": "123456",
            "totp_secret": "JBSWY3DPEHPK3PXP",
        }
    )

    assert created_kwargs == {"consumer_key": "ck_live_123", "environment": "prod"}
    assert "consumer_secret" not in created_kwargs
    sdk_instance.totp_login.assert_called_once()
    sdk_instance.totp_validate.assert_called_once_with(mpin="123456")
    assert adapter.client is sdk_instance
    assert adapter.is_connected() is True
    assert result["session_token"] == "trade_tok_xyz"
    assert result["refresh_token"] == "trade_sid_xyz"
    assert result["profile"]["ucc"] == "SDKUCC1"
    assert result["profile"]["client_name"] == "SDK User"


def test_kotak_adapter_fails_loudly_on_totp_login_error(monkeypatch):
    """Verify SDK totp_login error raises BrokerException and does NOT enter mock mode."""
    sdk_instance = MagicMock()
    sdk_instance.totp_login.return_value = {
        "error": [{"code": "401", "message": "Invalid TOTP"}]
    }
    monkeypatch.setattr("app.broker.adapters.kotak_adapter.NeoAPI", MagicMock(return_value=sdk_instance))

    adapter = KotakBrokerAdapter()
    with pytest.raises(BrokerException, match="Invalid TOTP"):
        adapter.login(
            {
                "consumer_key": "ck_123",
                "mobile_number": "+919876543210",
                "ucc": "UCC1",
                "mpin": "123456",
                "totp": "000000",
            }
        )

    assert adapter.client is None
    assert adapter.is_connected() is False
    assert broker_cache.get_status() == "DISCONNECTED"


def test_kotak_adapter_fails_loudly_on_totp_validate_error(monkeypatch):
    """Verify SDK totp_validate error raises BrokerException and does NOT enter mock mode."""
    sdk_instance = MagicMock()
    sdk_instance.totp_login.return_value = {"data": {"token": "view_tok", "sid": "view_sid"}}
    sdk_instance.totp_validate.return_value = {
        "error": [{"code": "401", "message": "Invalid MPIN"}]
    }
    monkeypatch.setattr("app.broker.adapters.kotak_adapter.NeoAPI", MagicMock(return_value=sdk_instance))

    adapter = KotakBrokerAdapter()
    with pytest.raises(BrokerException, match="Invalid MPIN"):
        adapter.login(
            {
                "consumer_key": "ck_123",
                "mobile_number": "+919876543210",
                "ucc": "UCC1",
                "mpin": "999999",
                "totp": "123456",
            }
        )

    assert adapter.client is None
    assert adapter.is_connected() is False


def _run_coro(coro):
    """Drive a coroutine to completion without creating an OS socketpair event loop."""
    try:
        while True:
            coro.send(None)
    except StopIteration as stop:
        return stop.value


def test_stream_adapter_no_silent_mock_fallback_when_client_none():
    """Verify KotakStreamAdapter.connect() fails loudly when client is None."""
    stream_adapter = KotakStreamAdapter(client=None)
    with pytest.raises(BrokerException, match="Authenticated NeoAPI client is required"):
        _run_coro(stream_adapter.connect({"session_token": "tok_123"}))
    assert stream_adapter.is_connected() is False


def test_stream_adapter_connects_via_create_websocket_and_async_connect():
    """Verify KotakStreamAdapter calls create_websocket() and awaits ws.connect()."""
    ws_mock = MagicMock()
    ws_mock.connect = AsyncMock(return_value=None)
    sdk_client = MagicMock()
    sdk_client.__is_mock__ = False
    sdk_client.create_websocket.return_value = ws_mock

    stream_adapter = KotakStreamAdapter(client=sdk_client)
    connected = _run_coro(stream_adapter.connect({"session_token": "tok_123"}))

    assert connected is True
    assert stream_adapter.is_connected() is True
    sdk_client.create_websocket.assert_called_once()
    ws_mock.connect.assert_awaited_once()


def test_client_state_after_sdk_login_reports_non_mock_connected(client, monkeypatch):
    """Verify GET /api/broker/client-state reports all connected=true and is_mock=false after SDK login."""
    sdk_instance = MagicMock()
    sdk_instance.__is_mock__ = False
    sdk_instance.totp_login.return_value = {"data": {"token": "view_tok", "sid": "view_sid"}}
    sdk_instance.totp_validate.return_value = {
        "data": {"token": "trade_tok", "sid": "trade_sid", "ucc": "LIVEUCC"}
    }
    monkeypatch.setattr("app.broker.adapters.kotak_adapter.NeoAPI", MagicMock(return_value=sdk_instance))

    client.post(
        "/api/auth/register",
        data=json.dumps({"username": "sdk_op", "email": "sdk_op@terminal.local", "password": "Password123!"}),
        content_type="application/json",
    )
    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({"username": "sdk_op", "password": "Password123!"}),
        content_type="application/json",
    )
    token = login_resp.get_json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    b_resp = client.post(
        "/api/broker/login",
        headers=headers,
        data=json.dumps(
            {
                "consumer_key": "ck_live",
                "mobile_number": "+919876543210",
                "ucc": "LIVEUCC",
                "mpin": "123456",
                "totp_secret": "JBSWY3DPEHPK3PXP",
            }
        ),
        content_type="application/json",
    )
    assert b_resp.status_code == 200

    cs_resp = client.get("/api/broker/client-state")
    assert cs_resp.status_code == 200
    cs_data = cs_resp.get_json()["data"]
    assert cs_data == {
        "broker_authenticated": True,
        "execution_adapter_connected": True,
        "streaming_adapter_connected": True,
        "is_mock": False,
    }

