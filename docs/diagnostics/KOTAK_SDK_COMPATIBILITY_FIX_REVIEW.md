# Kotak Neo SDK Compatibility Fix Review (`neo_api_client`)

**Document Type:** Engineering Fix & Verification Review  
**Date:** 2026-11-12  
**Status:** Implemented & Verified  

---

## 1. Installed `neo_api_client` Package Inspection

Inspected in `.venv` (`neo_api_client.__file__`: `.venv\Lib\site-packages\neo_api_client\__init__.py`):

- **Installed Package:** `neo_api_client` (package `kotakneoapi` is **not** installed)
- **Public `NeoAPI` Methods:**
  `cancel_order`, `create_order_feed`, `create_websocket`, `expiries`, `help`, `historical_data`, `holdings`, `limits`, `logout`, `margin_required`, `modify_order`, `option_chain`, `order_history`, `order_report`, `place_order`, `positions`, `quotes`, `scrip_master`, `search_scrip`, `subscribe`, `subscribe_to_orderfeed`, `totp_login`, `totp_validate`, `trade_report`, `un_subscribe`, `whatsmyip`
- **WebSocket Feed Module:** `neo_api_client.websocket.feed` (`SFeedWebSocket`, `WsToken`)
  - `SFeedWebSocket` async methods: `connect()`, `close()`, `subscribe_scrips(list[WsToken])`, `subscribe_index(list[WsToken])`, `subscribe_depth(list[WsToken])`, `unsubscribe_scrips(list[WsToken])`

---

## 2. Actual `NeoAPI` Constructor

Verified via `inspect.signature(NeoAPI.__init__)`:

```python
NeoAPI(
    consumer_key: str | None = None,
    environment: str = "prod",
    access_token: str | None = None,
    neo_fin_key: str | None = None,
    transport: httpx.BaseTransport | None = None,
    limits: httpx.Limits | None = None,
    http2: bool = True,
    timeout: float | None = None,
) -> None
```

- **Key Difference from Legacy Adapter:** `NeoAPI.__init__` does **not** accept `consumer_secret`.

---

## 3. Actual Authentication Sequence

Verified via `inspect.getsource(NeoAPI.totp_login)`, `inspect.getsource(NeoAPI.totp_validate)`, and `TotpAPI.totp_validate`:

1. **Client Initialization:**
   ```python
   client = NeoAPI(consumer_key=consumer_key, environment="prod")
   ```
2. **Step 1 — TOTP Login (View Token):**
   ```python
   login_resp = client.totp_login(
       mobile_number=mobile_number,
       ucc=ucc,
       totp=totp_code,
   )
   ```
   - Returns `{"data": {"token": "<view_token>", "sid": "<sid>", ...}}` on success, or `{"error": [...]}` / `{"Error": "..."}` on failure.
3. **Step 2 — MPIN Validation (Trade Token):**
   ```python
   validate_resp = client.totp_validate(mpin=mpin)
   ```
   - Returns `{"data": {"token": "<edit_token>", "sid": "<edit_sid>", "rid": "<rid>", "ucc": "...", "greetingName": "...", "baseUrl": "...", "dataCenter": "...", ...}}` on success.
   - Populates `client.configuration.edit_token`, `client.configuration.edit_sid`, `client.configuration.edit_rid`, `client.configuration.base_url`, `client.configuration.sfeed_websocket_url`, `client.configuration.ucc`.
4. **SFeed WebSocket Creation & Connection:**
   ```python
   ws = client.create_websocket()  # returns SFeedWebSocket using edit_token + edit_sid
   await ws.connect()
   ```

---

## 4. Files Updated

1. [`app/broker/adapters/kotak_adapter.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/adapters/kotak_adapter.py)
   - Imports `from neo_api_client import NeoAPI` first (with `kotakneoapi` fallback).
   - Instantiates `NeoAPI(consumer_key=consumer_key, environment=environment)` without `consumer_secret`.
   - Executes `totp_login(mobile_number=..., ucc=..., totp=...)` followed by `totp_validate(mpin=...)`.
   - Extracts `session_token` from `validate_resp["data"]["token"]` / `client.configuration.edit_token` and `refresh_token` from `validate_resp["data"]["sid"]` / `client.configuration.edit_sid`.
   - Captures profile metadata (`ucc`, `greetingName`, `kId`) from `totp_validate` response (`neo_api_client.NeoAPI` has no `.profile()` method).
   - Removed silent mock fallback: when `self.client` is not an explicit mock (`__is_mock__ = True`), missing SDK or missing credentials or SDK errors fail loudly (`ValidationException` / `BrokerException`), reset `self.client = None`, and never enter mock mode.
   - Updated `restore_session()` to re-instantiate `NeoAPI(consumer_key=ck, environment="prod", access_token=session_token)` without `consumer_secret` and set `configuration.edit_token` / `configuration.edit_sid`.

2. [`app/broker/adapters/kotak_stream_adapter.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code - Nitin Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/adapters/kotak_stream_adapter.py)
   - Imports `NeoAPI`, `SFeedWebSocket`, and `WsToken` from `neo_api_client`.
   - Removed silent mock fallback when `self.client is None`: `connect()` now raises `BrokerException("Authenticated NeoAPI client is required for SFeed WebSocket connection")`. Simulated mode is only permitted for an explicit mock client (`__is_mock__ = True`).
   - Calls `ws_instance = self.client.create_websocket()` and `await ws_instance.connect()`.
   - Converts subscription/unsubscription token payloads to `WsToken(exchange_segment, token)` when connected to a real `SFeedWebSocket`.

3. **Test Suite Updates & SDK Compatibility Tests**
   - Added [`tests/unit/test_kotak_sdk_compatibility.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/tests/unit/test_kotak_sdk_compatibility.py) (7 tests covering SDK import, constructor signature, `totp_login`/`totp_validate` sequence, loud failure on TOTP/MPIN errors, no silent stream mock fallback, `create_websocket()` + `connect()`, and `/api/broker/client-state` verification).
   - Updated [`tests/unit/test_broker_adapter.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/tests/unit/test_broker_adapter.py), [`tests/unit/test_broker_health.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/tests/unit/test_broker_health.py), [`tests/unit/test_broker_session.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/tests/unit/test_broker_session.py), [`tests/unit/test_websocket_supervisor.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/tests/unit/test_websocket_supervisor.py), [`tests/integration/test_broker_routes.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/tests/integration/test_broker_routes.py), [`tests/integration/test_stream_integration.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/tests/integration/test_stream_integration.py), and [`tests/integration/test_terminal_auth.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/tests/integration/test_terminal_auth.py) to supply explicit `NeoAPI` / mock clients.

---

## 5. Verification Results

- **`GET /api/broker/client-state` after SDK login** (verified by `test_client_state_after_sdk_login_reports_non_mock_connected`):
  ```json
  {
    "broker_authenticated": true,
    "execution_adapter_connected": true,
    "streaming_adapter_connected": true,
    "is_mock": false
  }
  ```
- **Test Runs:**
  - `test_kotak_sdk_compatibility.py`, `test_broker_adapter.py`, `test_broker_health.py`, `test_broker_session.py`, `test_broker_routes.py`, `test_live_execution_wiring.py`: **21 passed** (`4.30s`).
  - `test_terminal_auth.py` (standalone): **2 passed** (`0.51s`).
  - Note: Tests that spin up an OS `asyncio` event loop thread (`test_websocket_supervisor.py`, `test_stream_integration.py`) were excluded from the sandboxed run because Windows `socketpair()` creation in `asyncio.new_event_loop()` blocks inside the restricted sandbox environment.

