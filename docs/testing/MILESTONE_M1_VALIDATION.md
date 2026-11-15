# Milestone M1 Validation & Quality Assurance Manual
## End-to-End Operational Verification Guide

**Document Version:** 1.0.0  
**Target Milestone:** Milestone M1 (Phases 1, 2 & 3 Integrated Baseline)  
**System:** Kotak Neo Personal Trading Terminal  
**Audience:** QA Engineers, System Architects, Security Auditors, Operators  
**Execution Environment:** Windows PowerShell / Bash / Python 3.14 Virtualenv (`.venv`)  

---

## Table of Contents
1. [Milestone M1 Scope & Objectives](#1-milestone-m1-scope--objectives)
2. [Environment Setup & Preconditions](#2-environment-setup--preconditions)
3. [Test Suite 1: Authentication](#3-test-suite-1-authentication)
4. [Test Suite 2: Session Management](#4-test-suite-2-session-management)
5. [Test Suite 3: Encryption & Data Protection](#5-test-suite-3-encryption--data-protection)
6. [Test Suite 4: Auditing & Request Tracing](#6-test-suite-4-auditing--request-tracing)
7. [Test Suite 5: Broker Connectivity & Diagnostics](#7-test-suite-5-broker-connectivity--diagnostics)
8. [Test Suite 6: Session Recovery & Resilience](#8-test-suite-6-session-recovery--resilience)
9. [Consolidated Pass/Fail Execution Checklist](#9-consolidated-passfail-execution-checklist)
10. [Troubleshooting & Remediation](#10-troubleshooting--remediation)

---

## 1. Milestone M1 Scope & Objectives

Milestone M1 represents the integrated, non-trading architectural foundation:
- **Phase 1**: Clean architecture skeleton, centralized logging, event bus, app factory, SQLite persistence.
- **Phase 2**: Local user identity, salted password hashing, operator sessions, request correlation tracing, symmetric encryption, and audit framework.
- **Phase 3**: Kotak Neo broker adapter interface, token encryption at rest, broker session persistence, capability discovery, state health monitoring, and session recovery.

> [!IMPORTANT]
> **Strict Non-Trading Boundary**:  
> In Milestone M1, **NO** order placement, order modification, order cancellation, market watch feeds, holdings, positions, option chains, or WebSocket tick streaming should be present or callable.

---

## 2. Environment Setup & Preconditions

Before executing manual procedures, verify the following prerequisites:

### 2.1 Activate Virtual Environment
```powershell
# In repository root:
.\.venv\Scripts\Activate.ps1
python --version
# Expected: Python 3.14.x
```

### 2.2 Verify Environment Configuration
Ensure `.env` exists and contains valid testing parameters:
```powershell
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
```
Required `.env` keys:
- `SECRET_KEY=test-manual-validation-secret-key-12345`
- `ENCRYPTION_KEY=test-manual-validation-encryption-key-67890`
- `DATABASE_URL=sqlite:///data/kotak_terminal.db`
- `LOG_LEVEL=INFO`
- `KOTAK_BROKER_ENABLED=true`
- `BROKER_SESSION_TIMEOUT=28800`
- `BROKER_HEALTH_INTERVAL=60`

### 2.3 Verify Database Migration State
Ensure SQLite database schema is at `head`:
```powershell
alembic upgrade head
```
Expected output:
```text
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
```

### 2.4 Start the Terminal Server
In a dedicated PowerShell terminal:
```powershell
python run.py
```
Expected console output:
```text
{"timestamp": "...", "level": "INFO", "message": "Kotak Neo Terminal initializing...", "event": "STARTUP"}
{"timestamp": "...", "level": "INFO", "message": "SQLite database initialized successfully", "event": "DB_INIT"}
 * Running on http://127.0.0.1:5000
```

---

## 3. Test Suite 1: Authentication

### TC-AUTH-01: User Registration (Happy Path)
* **Objective:** Verify a new operator account can be registered with a salted password hash.
* **Preconditions:** Server running on `http://127.0.0.1:5000`.
* **Execution (PowerShell):**
  ```powershell
  $body = @{
      username = "test_trader"
      email = "trader@terminal.local"
      password = "Password@123!"
  } | ConvertTo-Json

  Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/register" `
      -Method Post -ContentType "application/json" -Body $body
  ```
* **Expected Results:**
  - HTTP Status: `201 Created`
  - Response payload:
    ```json
    {
      "success": true,
      "message": "User registered successfully",
      "data": {
        "user_id": 1,
        "username": "test_trader",
        "email": "trader@terminal.local"
      }
    }
    ```
  - Database check confirms no plaintext password:
    ```powershell
    python -c "from app.models.db import init_db, get_session; from app.auth.models.user import User; init_db(); s = get_session(); u = s.query(User).filter_by(username='test_trader').first(); print('Hash:', u.password_hash); assert 'Password@123!' not in u.password_hash; s.close()"
    ```

### TC-AUTH-02: Duplicate Registration Rejection
* **Objective:** Ensure duplicate usernames or email addresses are rejected defensively.
* **Preconditions:** `TC-AUTH-01` completed.
* **Execution (PowerShell):**
  ```powershell
  try {
      Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/register" `
          -Method Post -ContentType "application/json" -Body $body
  } catch {
      $_.Exception.Response.StatusCode.value__
      $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
      $reader.ReadToEnd()
  }
  ```
* **Expected Results:**
  - HTTP Status: `400 Bad Request`
  - `error_code`: `USER_ALREADY_EXISTS`
  - Error message indicates username or email is already registered.

### TC-AUTH-03: User Login & Token Generation
* **Objective:** Validate authentication with valid credentials produces a valid session token.
* **Preconditions:** User `test_trader` exists.
* **Execution (PowerShell):**
  ```powershell
  $loginBody = @{
      username = "test_trader"
      password = "Password@123!"
  } | ConvertTo-Json

  $resp = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/login" `
      -Method Post -ContentType "application/json" -Body $loginBody
  $global:USER_TOKEN = $resp.data.token
  $global:USER_SESSION_ID = $resp.data.session_id
  $resp | ConvertTo-Json
  ```
* **Expected Results:**
  - HTTP Status: `200 OK`
  - Response contains `token` (64-character URL-safe string), `session_id`, and `user` object.
  - Variable `$global:USER_TOKEN` is populated.

### TC-AUTH-04: Login with Bad Credentials Rejection
* **Objective:** Verify incorrect password attempts are rejected and audited.
* **Preconditions:** Server running.
* **Execution (PowerShell):**
  ```powershell
  $badLogin = @{
      username = "test_trader"
      password = "WrongPassword999!"
  } | ConvertTo-Json

  try {
      Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/login" `
          -Method Post -ContentType "application/json" -Body $badLogin
  } catch {
      $_.Exception.Response.StatusCode.value__
  }
  ```
* **Expected Results:**
  - HTTP Status: `401 Unauthorized`
  - Response `error_code`: `INVALID_CREDENTIALS`
  - Log records `LOGIN_FAILED` audit entry.

### TC-AUTH-05: Protected Route Access (`/api/auth/me`)
* **Objective:** Verify authenticated requests with Bearer token resolve current user context.
* **Preconditions:** `$global:USER_TOKEN` available from `TC-AUTH-03`.
* **Execution (PowerShell):**
  ```powershell
  $headers = @{ "Authorization" = "Bearer $global:USER_TOKEN" }
  Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/me" `
      -Method Get -Headers $headers | ConvertTo-Json
  ```
* **Expected Results:**
  - HTTP Status: `200 OK`
  - Returns current user details (`id`, `username`, `email`, `is_active`).

### TC-AUTH-06: Protected Route Rejection on Missing/Invalid Token
* **Objective:** Ensure unauthenticated requests cannot access protected routes.
* **Execution (PowerShell):**
  ```powershell
  try {
      Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/me" `
          -Method Get -Headers @{ "Authorization" = "Bearer invalid_garbage_token" }
  } catch {
      $_.Exception.Response.StatusCode.value__
  }
  ```
* **Expected Results:**
  - HTTP Status: `401 Unauthorized`
  - `error_code`: `INVALID_SESSION_TOKEN`

---

## 4. Test Suite 2: Session Management

### TC-SESS-01: Operator Session Persistence in SQLite
* **Objective:** Verify session record exists in `sessions` table and has unexpired timestamp.
* **Preconditions:** Logged in via `TC-AUTH-03`.
* **Execution (PowerShell):**
  ```powershell
  python -c "from app.models.db import init_db, get_session; from app.auth.models.session import Session; init_db(); s = get_session(); sess = s.query(Session).filter_by(is_active=True).first(); print('Session ID:', sess.id, 'User ID:', sess.user_id, 'Expires:', sess.expiry_time); assert sess is not None; s.close()"
  ```
* **Expected Results:**
  - An active session row is printed.
  - `expiry_time` is ~24 hours into the future.
  - `is_active` is `True` (1).

### TC-SESS-02: Session Invalidation on Logout
* **Objective:** Ensure `/api/auth/logout` revokes the session in SQLite.
* **Preconditions:** User is currently logged in.
* **Execution (PowerShell):**
  ```powershell
  $headers = @{ "Authorization" = "Bearer $global:USER_TOKEN" }
  Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/logout" `
      -Method Post -Headers $headers | ConvertTo-Json
  ```
* **Expected Results:**
  - HTTP Status: `200 OK`
  - Message: `Logged out successfully`
  - Subsequent call to `/api/auth/me` with old token returns `401 Unauthorized`.
  - Database verification shows session marked `is_active = 0`:
    ```powershell
    python -c "from app.models.db import init_db, get_session; from app.auth.models.session import Session; init_db(); s = get_session(); sess = s.query(Session).filter_by(id=$global:USER_SESSION_ID).first(); print('Is Active:', sess.is_active); assert not sess.is_active; s.close()"
    ```

---

## 5. Test Suite 3: Encryption & Data Protection

### TC-ENC-01: Symmetric Encryption Roundtrip & Decryption Integrity
* **Objective:** Verify Fernet symmetric encryption encrypts and restores secrets accurately.
* **Execution (PowerShell):**
  ```powershell
  python -c "from app.core.encryption import encryption_service; secret = 'KotakAccessToken_987654321'; token = encryption_service.encrypt(secret); print('Ciphertext:', token); assert token != secret; assert encryption_service.decrypt(token) == secret; print('TC-ENC-01 PASSED')"
  ```
* **Expected Results:**
  - Output displays base64 URL-safe ciphertext starting with `gAAAAA...`
  - Plaintext is recovered cleanly.
  - Console prints `TC-ENC-01 PASSED`.

### TC-ENC-02: Ciphertext Tamper Detection
* **Objective:** Ensure modified ciphertext fails decryption immediately without leaking secrets.
* **Execution (PowerShell):**
  ```powershell
  python -c "from app.core.encryption import encryption_service; from app.core.exceptions import ValidationException; enc = encryption_service.encrypt('super_secret_token'); tampered = enc[:15] + ('A' if enc[15] != 'A' else 'B') + enc[16:]; 
  try:
      encryption_service.decrypt(tampered)
      print('FAILED: Tampered data decrypted')
  except ValidationException:
      print('TC-ENC-02 PASSED: Tampering detected and rejected cleanly')
  "
  ```
* **Expected Results:**
  - Console prints: `TC-ENC-02 PASSED: Tampering detected and rejected cleanly`.

### TC-ENC-03: At-Rest Encryption in `broker_sessions` Table
* **Objective:** Confirm broker session tokens stored in SQLite are encrypted and NEVER stored in plaintext.
* **Preconditions:** Complete broker login in `TC-BRK-03` below, then run this check:
* **Execution (PowerShell):**
  ```powershell
  python -c "from app.models.db import init_db, get_session; from app.broker.models.broker_session import BrokerSession; init_db(); s = get_session(); b_sess = s.query(BrokerSession).first(); print('Stored Token Ciphertext:', b_sess.session_token_encrypted[:30] + '...'); assert 'kotak' not in b_sess.session_token_encrypted; assert b_sess.session_token_encrypted.startswith('gAAAA'); print('TC-ENC-03 PASSED: Tokens encrypted at rest'); s.close()"
  ```
* **Expected Results:**
  - Raw session tokens in SQLite begin with `gAAAA` (Fernet header).
  - No plaintext words (such as `kotak_token`) exist in the database column.

---

## 6. Test Suite 4: Auditing & Request Tracing

### TC-AUD-01: Correlation ID & Request ID Propagation
* **Objective:** Verify client-provided `X-Correlation-ID` header is echoed in HTTP response and recorded in logs.
* **Execution (PowerShell):**
  ```powershell
  $customCorrId = "audit-manual-test-corr-" + [System.Guid]::NewGuid().ToString()
  $customReqId = "req-" + [System.Guid]::NewGuid().ToString()

  $headers = @{
      "X-Correlation-ID" = $customCorrId
      "X-Request-ID" = $customReqId
  }

  $response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/health" -Headers $headers
  Write-Host "Response Headers:"
  Write-Host "X-Correlation-ID:" $response.Headers["X-Correlation-ID"]
  Write-Host "X-Request-ID:" $response.Headers["X-Request-ID"]

  if ($response.Headers["X-Correlation-ID"] -eq $customCorrId) {
      Write-Host "TC-AUD-01 PASSED"
  } else {
      Write-Host "TC-AUD-01 FAILED"
  }
  ```
* **Expected Results:**
  - The response headers mirror the supplied `$customCorrId` and `$customReqId`.
  - Console prints `TC-AUD-01 PASSED`.

### TC-AUD-02: Audit Trail Entry in Log File
* **Objective:** Verify immutable audit records are written to `logs/terminal.log`.
* **Execution (PowerShell):**
  ```powershell
  Get-Content "logs/terminal.log" -Tail 20 | Select-String "AUDIT_RECORD"
  ```
* **Expected Results:**
  - Log lines contain JSON output with:
    - `"event": "AUDIT_RECORD"`
    - `"audit_category": "AUTH"` or `"BROKER"`
    - Matching `correlation_id` and `request_id`.

---

## 7. Test Suite 5: Broker Connectivity & Diagnostics

### TC-BRK-01: Unauthenticated Broker Status Check
* **Objective:** Verify initial broker status without login returns `DISCONNECTED` or `LOGIN_REQUIRED`.
* **Execution (PowerShell):**
  ```powershell
  $status = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/broker/status" -Method Get
  $status | ConvertTo-Json
  ```
* **Expected Results:**
  - HTTP Status: `200 OK`
  - `status.data.status`: `"DISCONNECTED"` or `"LOGIN_REQUIRED"`
  - `status.data.connected`: `false`
  - `status.data.authenticated`: `false`

### TC-BRK-02: Capability Discovery
* **Objective:** Verify `/api/broker/capabilities` reports exchanges, segments, and order types, while confirming trading features are disabled.
* **Execution (PowerShell):**
  ```powershell
  $caps = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/broker/capabilities" -Method Get
  $caps | ConvertTo-Json
  ```
* **Expected Results:**
  - `data.supported_exchanges` includes `["NSE", "BSE", "NFO", "BFO", "MCX"]`
  - `data.features.order_placement`: `false`
  - `data.features.market_streaming`: `false`
  - `data.features.session_recovery`: `true`

### TC-BRK-03: Broker Authentication via API
* **Objective:** Authenticate broker session for the logged-in operator.
* **Preconditions:** Re-login operator to acquire fresh `$global:USER_TOKEN`:
  ```powershell
  $loginResp = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/login" `
      -Method Post -ContentType "application/json" `
      -Body (@{ username="test_trader"; password="Password@123!" } | ConvertTo-Json)
  $global:USER_TOKEN = $loginResp.data.token
  ```
* **Execution (PowerShell):**
  ```powershell
  $brokerAuthBody = @{
      consumer_key = "neo_mock_key_123"
      consumer_secret = "neo_mock_secret_456"
      mobile_number = "9876543210"
      ucc = "TESTUCC"
      mpin = "123456"
      totp_secret = "JBSWY3DPEHPK3PXP"
  } | ConvertTo-Json

  $headers = @{ "Authorization" = "Bearer $global:USER_TOKEN" }
  $bResp = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/broker/login" `
      -Method Post -Headers $headers -ContentType "application/json" -Body $brokerAuthBody
  $bResp | ConvertTo-Json
  ```
* **Expected Results:**
  - HTTP Status: `200 OK`
  - `data.status`: `"AUTHENTICATED"`
  - `data.broker_session.broker_name`: `"KOTAK_NEO"`
  - `data.broker_session.is_active`: `true`
  - No secret tokens exposed in JSON payload.

### TC-BRK-04: Active Broker Diagnostic Health Check
* **Objective:** Query `/api/broker/status` after login and verify state updates to `AUTHENTICATED`.
* **Execution (PowerShell):**
  ```powershell
  $health = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/broker/status" -Method Get
  $health | ConvertTo-Json
  ```
* **Expected Results:**
  - `data.status`: `"AUTHENTICATED"`
  - `data.connected`: `true`
  - `data.authenticated`: `true`
  - `data.latency_ms` reported (> 0.0 ms).

### TC-BRK-05: Broker Logout & Invalidation
* **Objective:** Explicitly terminate broker connectivity via `/api/broker/logout`.
* **Execution (PowerShell):**
  ```powershell
  $headers = @{ "Authorization" = "Bearer $global:USER_TOKEN" }
  $logoutResp = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/broker/logout" `
      -Method Post -Headers $headers
  $logoutResp | ConvertTo-Json
  ```
* **Expected Results:**
  - HTTP Status: `200 OK`
  - `data.status`: `"DISCONNECTED"`
  - Subsequent `/api/broker/status` returns `status: "DISCONNECTED"` or `"LOGIN_REQUIRED"`.

---

## 8. Test Suite 6: Session Recovery & Resilience

### TC-REC-01: Reconnect & Recover Broker Session
* **Objective:** Authenticate broker session, simulate terminal disconnect, and restore session via `/api/broker/restore`.
* **Preconditions:** Broker is logged in via `TC-BRK-03`.
* **Execution (PowerShell):**
  ```powershell
  # 1. Login broker again to ensure active session exists in DB
  $headers = @{ "Authorization" = "Bearer $global:USER_TOKEN" }
  $brokerAuthBody = @{
      consumer_key = "neo_mock_key_123"
      consumer_secret = "neo_mock_secret_456"
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/broker/login" `
      -Method Post -Headers $headers -ContentType "application/json" -Body $brokerAuthBody | Out-Null

  # 2. Simulate fresh connection / reload: invoke /api/broker/restore
  $restoreResp = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/broker/restore" `
      -Method Post -Headers $headers
  $restoreResp | ConvertTo-Json
  ```
* **Expected Results:**
  - HTTP Status: `200 OK`
  - `data.restored`: `true`
  - `data.status`: `"AUTHENTICATED"`
  - Audit log records `BROKER_SESSION_RESTORED`.

### TC-REC-02: Recovery Rejection on Expired Session
* **Objective:** Verify recovery rejects and auto-deactivates sessions whose validity time has passed.
* **Execution (PowerShell):**
  ```powershell
  # 1. Artificially expire the active broker session in SQLite
  python -c "from app.models.db import init_db, get_session; from app.broker.models.broker_session import BrokerSession; from datetime import datetime, timedelta, timezone; init_db(); s = get_session(); b = s.query(BrokerSession).filter_by(is_active=True).first(); b.expiry_time = datetime.now(timezone.utc) - timedelta(hours=2); s.commit(); print('Expired session ID:', b.id); s.close()"

  # 2. Attempt restore
  try {
      $headers = @{ "Authorization" = "Bearer $global:USER_TOKEN" }
      Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/broker/restore" `
          -Method Post -Headers $headers
  } catch {
      Write-Host "HTTP Status:" $_.Exception.Response.StatusCode.value__
      $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
      Write-Host "Error Body:" $reader.ReadToEnd()
  }
  ```
* **Expected Results:**
  - HTTP Status: `400 Bad Request`
  - `error_code`: `BROKER_RESTORE_FAILED`
  - System logs audit entry `BROKER_SESSION_EXPIRED`.
  - Database row marked `is_active = 0`.

### TC-REC-03: Recovery Rejection on Corrupted Token Ciphertext
* **Objective:** Ensure tampering or database corruption causes recovery failure rather than unhandled exception.
* **Execution (PowerShell):**
  ```powershell
  python -c "from app.core.exceptions import ValidationException; from app.broker.services.broker_session_manager import BrokerSessionManager; from app.broker.adapters.kotak_adapter import KotakBrokerAdapter; from app.models.db import init_db, get_session; from app.broker.models.broker_session import BrokerSession; init_db(); s = get_session(); b = s.query(BrokerSession).first(); b.is_active = True; b.session_token_encrypted = 'gAAAAABcorrupted_cipher_data_string'; s.commit();
  mgr = BrokerSessionManager()
  adapter = KotakBrokerAdapter()
  res = mgr.restore_session(user_id=b.user_id, adapter=adapter)
  print('Recovery result on corrupted token:', res)
  assert res is False
  print('TC-REC-03 PASSED: Corrupted token cleanly rejected')
  s.close()
  "
  ```
* **Expected Results:**
  - Console output: `Recovery result on corrupted token: False`
  - `TC-REC-03 PASSED: Corrupted token cleanly rejected`.

---

## 9. Consolidated Pass/Fail Execution Checklist

| ID | Verification Area | Target Capability | Method | Expected Outcome | Result |
|:---:|---|---|---|---|:---:|
| **1.1** | **Authentication** | User Registration | POST `/api/auth/register` | HTTP 201, User Created | `[  ]` PASS |
| **1.2** | **Authentication** | Duplicate Prevention | POST `/api/auth/register` | HTTP 400, USER_ALREADY_EXISTS | `[  ]` PASS |
| **1.3** | **Authentication** | User Login | POST `/api/auth/login` | HTTP 200, JWT/Session token | `[  ]` PASS |
| **1.4** | **Authentication** | Bad Credentials | POST `/api/auth/login` | HTTP 401, INVALID_CREDENTIALS | `[  ]` PASS |
| **1.5** | **Authentication** | Token Verification | GET `/api/auth/me` | HTTP 200, User metadata | `[  ]` PASS |
| **1.6** | **Authentication** | Unauthorized Access | GET `/api/auth/me` | HTTP 401, Unauthorized | `[  ]` PASS |
| **2.1** | **Sessions** | Session Persistence | SQLite `sessions` table | Active row with future expiry | `[  ]` PASS |
| **2.2** | **Sessions** | Session Invalidation | POST `/api/auth/logout` | Session row set to `is_active=0` | `[  ]` PASS |
| **3.1** | **Encryption** | Symmetric Roundtrip | `EncryptionService.encrypt/decrypt` | Plaintext matches exactly | `[  ]` PASS |
| **3.2** | **Encryption** | Tamper Protection | Mutated ciphertext test | `ValidationException` thrown | `[  ]` PASS |
| **3.3** | **Encryption** | At-Rest Storage | `broker_sessions` table check | Plaintext tokens never in DB | `[  ]` PASS |
| **4.1** | **Auditing** | Trace Lineage | Header `X-Correlation-ID` | Correlation ID echoed in resp/log | `[  ]` PASS |
| **4.2** | **Auditing** | File Audit Trail | `logs/terminal.log` inspect | Structured `AUDIT_RECORD` logs | `[  ]` PASS |
| **5.1** | **Broker** | Initial Health Status | GET `/api/broker/status` | `DISCONNECTED` or `LOGIN_REQUIRED` | `[  ]` PASS |
| **5.2** | **Broker** | Capability Discovery | GET `/api/broker/capabilities` | Exchanges reported; orders disabled | `[  ]` PASS |
| **5.3** | **Broker** | Broker Handshake | POST `/api/broker/login` | `AUTHENTICATED`, encrypted session | `[  ]` PASS |
| **5.4** | **Broker** | Health Diagnostics | GET `/api/broker/status` | `AUTHENTICATED`, latency > 0 ms | `[  ]` PASS |
| **5.5** | **Broker** | Broker Logout | POST `/api/broker/logout` | `DISCONNECTED`, session deactivated | `[  ]` PASS |
| **6.1** | **Recovery** | Active State Recovery | POST `/api/broker/restore` | HTTP 200, `restored: true` | `[  ]` PASS |
| **6.2** | **Recovery** | Expired Session Check | Artificially expired restore | HTTP 400, Auto-deactivated | `[  ]` PASS |
| **6.3** | **Recovery** | Corrupt Cipher Check | Tampered token restore | False returned, clean fallback | `[  ]` PASS |
| **7.0** | **Governance** | Zero-Order Verification | Inspection of interfaces/routes | Zero order execution endpoints | `[  ]` PASS |

---

## 10. Troubleshooting & Remediation

| Symptom | Probable Cause | Remediation Step |
|---|---|---|
| `sqlite3.OperationalError: no such table: broker_sessions` | Alembic migrations not applied | Run `alembic upgrade head` in `.venv`. |
| `ConfigurationException: EncryptionService requires ENCRYPTION_KEY or SECRET_KEY` | Missing key in `.env` | Add `SECRET_KEY=...` to `.env` file. |
| `HTTP 401 Unauthorized` on `/api/broker/login` | Missing or invalid local operator session | Log in via `/api/auth/login` and pass `Authorization: Bearer <token>`. |
| `HTTP 400 BROKER_RESTORE_FAILED` | No active session or token expired | Re-authenticate with broker credentials via POST `/api/broker/login`. |
| Port 5000 in use | Orphaned development server running | Run `Get-Process python \| Stop-Process` in PowerShell and restart. |

