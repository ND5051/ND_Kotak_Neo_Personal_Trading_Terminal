# Client Wiring Root Cause Investigation (`GET /api/broker/client-state`)

**Document Type:** Root Cause Analysis  
**Date:** 2026-11-12  
**Observed Output:**
```json
{
  "broker_authenticated": true,
  "execution_adapter_connected": false,
  "streaming_adapter_connected": false,
  "is_mock": true
}
```

---

## 1. Executive Summary

`sync_shared_broker_client()` **was** called by `/api/broker/login`, and there is **only one** `kotak_adapter` singleton in memory. However, `kotak_adapter.client` was **`None`** after login because [`app/broker/adapters/kotak_adapter.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/adapters/kotak_adapter.py#L14-L17) failed to import `NeoAPI` (`ModuleNotFoundError: No module named 'kotakneoapi'`).

The installed package in `.venv` is **`neo_api_client`**, not `kotakneoapi`. While [`kotak_order_adapter.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/adapters/kotak_order_adapter.py#L16-L22) falls back to `from neo_api_client import NeoAPI`, `kotak_adapter.py` (and `kotak_stream_adapter.py`) did **not**. Consequently, `kotak_adapter.login()` silently ran its mock fallback (`POST /api/broker/login` completed in `72.54ms`), left `kotak_adapter.client = None`, set `_authenticated = True`, and propagated `None` to all downstream adapters.

---

## 2. Detailed Answers to Investigation Questions

### 1. Why `sync_shared_broker_client()` is not updating `execution_adapter_connected`
- `sync_shared_broker_client(kotak_adapter.client)` **did** execute, but `kotak_adapter.client` was `None`.
- Setting `kotak_order_adapter.client = None` leaves `execution_adapter_connected` (`kotak_order_adapter.client is not None`) as **`false`**.

### 2. Why `streaming_adapter_connected` remains `false` after broker login
- For the exact same reason: `sync_shared_broker_client(None)` set `ws_supervisor.adapter.client = None`, so `ws_supervisor.adapter.client is not None` evaluated to **`false`**.
- `logs/terminal.log` (`12:50:36.457015Z`) confirms `KotakStreamAdapter` fell back to simulated mode: `"Kotak Neo SFeed connected successfully (simulated)"`.

### 3. Is `/api/broker/login` actually calling `sync_shared_broker_client()`?
- **Yes.** [`app/broker/routes.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/routes.py#L131-L134) calls `sync_shared_broker_client(kotak_adapter.client)` immediately after `kotak_adapter.login(credentials)`.

### 4. Is there more than one `kotak_adapter` singleton instance in memory?
- **No.** All modules share the single `kotak_adapter` singleton instance.

### 5. Exact Object IDs Observed in Runtime Inspection
Captured directly from `.venv\Scripts\python`:
- `kotak_adapter` (`app.broker.adapters.kotak_adapter`): **`2996359362080`**
- `kotak_adapter` (`app.broker.routes`): **`2996359362080`** *(identical)*
- `portfolio_service.adapter`: **`2996359362080`** *(identical)*
- `kotak_order_adapter`: **`2996359362416`**
- `ws_supervisor.adapter`: **`2996360075920`**

### 6. Exact `NeoAPI` Availability & Client State After Login
- `kotakneoapi` import: `ModuleNotFoundError("No module named 'kotakneoapi'")`
- `neo_api_client.NeoAPI`: `<class 'neo_api_client.neo_api.NeoAPI'>`
- `kotak_adapter.NeoAPI`: **`None`**
- `kotak_order_adapter.NeoAPI`: `<class 'neo_api_client.neo_api.NeoAPI'>`
- `kotak_adapter.client` after `/api/broker/login`: **`None`** (never instantiated)
- `kotak_order_adapter.client` after sync: **`None`**
- `ws_supervisor.adapter.client` after sync: **`None`**
- `portfolio_service.adapter.client` after sync: **`None`**

### 7. Why `client-state` Still Reports `is_mock = true`
1. `kotak_adapter.NeoAPI` was `None`, so `kotak_adapter.login()` skipped `NeoAPI(...)` instantiation and fell into `if self.client is None:` (lines 85–87), generating a simulated token (`kotak_token_<ts>`) while still setting `self._connected = True` and `self._authenticated = True` (`broker_authenticated: true`).
2. `kotak_order_adapter._is_mock()` returns `True` whenever `self.client is None`. Since `kotak_adapter.client` was `None`, `client-state` reported `is_mock: true`.

---

## 3. Critical Secondary SDK Compatibility Finding

Inspection of the installed `neo_api_client.NeoAPI` class in `.venv` revealed an additional mismatch in [`kotak_adapter.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/adapters/kotak_adapter.py#L78-L96):
- **Installed `NeoAPI.__init__` signature:**
  `(self, consumer_key=None, environment='prod', access_token=None, neo_fin_key=None, ...)`
  *(Does **not** accept `consumer_secret`.)*
- **Installed `NeoAPI` auth methods:**
  `totp_login(...)` and `totp_validate(...)`
  *(Does **not** have `.login()` or `.session_2fa()`.)*

Therefore, fixing the `NeoAPI` import alone without updating `kotak_adapter.login()` to use `totp_login` / `totp_validate` (and removing `consumer_secret` from `NeoAPI(...)`) would cause `TypeError` / `AttributeError` when connecting to the live Kotak Neo SDK.

---

## 4. Recommended Fix

1. Add the `from neo_api_client import NeoAPI` import fallback to both `app/broker/adapters/kotak_adapter.py` and `app/broker/adapters/kotak_stream_adapter.py`.
2. Update `KotakBrokerAdapter.login()` (and `restore_session()`) to instantiate `NeoAPI(consumer_key=consumer_key, environment="prod")` and authenticate via `client.totp_login(mobile_number=..., ucc=..., totp=...)` + `client.totp_validate(mpin=...)` when running against real `NeoAPI` (keeping mock/test behavior only when `self.client` is explicitly a test mock or `NeoAPI is None`).
3. Prohibit silent mock fallback in `KotakBrokerAdapter.login()` when `NeoAPI` is installed and live credentials are supplied (or fail explicitly if SDK login errors).

