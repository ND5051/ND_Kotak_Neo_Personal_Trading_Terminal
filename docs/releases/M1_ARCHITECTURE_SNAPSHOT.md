# Milestone M1 Architecture Snapshot
## System Structure & Component Topology at M1 Baseline

**Document Version:** 1.0.0  
**Baseline Date:** 2026-11-06  
**Git Baseline Commit:** `ae851b8`  
**Git Tag:** `M1_BASELINE`  

---

## 1. Repository Structure

```text
ND_Kotak_Neo_Personal_Trading_Terminal/
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
├── run.py
├── PROJECT_CONSTITUTION.md
├── M1_RELEASE_NOTES.md
├── MILESTONE_M1_VALIDATION.md
├── app/
│   ├── __init__.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── decorators.py
│   │   ├── routes.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── session.py
│   │   │   └── user.py
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── session_repository.py
│   │   │   └── user_repository.py
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── auth_service.py
│   │       ├── session_manager.py
│   │       └── totp_service.py
│   ├── basket/
│   ├── broker/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── adapters/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── kotak_adapter.py
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   └── broker_cache.py
│   │   ├── interfaces/
│   │   │   ├── __init__.py
│   │   │   └── broker_interface.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── broker_session.py
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   └── broker_session_repository.py
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── broker_health_service.py
│   │       └── broker_session_manager.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── audit.py
│   │   ├── encryption.py
│   │   ├── exceptions.py
│   │   ├── feature_flags.py
│   │   ├── request_context.py
│   │   └── response.py
│   ├── dashboard/
│   ├── events/
│   │   ├── __init__.py
│   │   ├── event_bus.py
│   │   └── event_types.py
│   ├── holdings/
│   ├── logging/
│   │   ├── __init__.py
│   │   ├── formatters.py
│   │   └── logger.py
│   ├── market_watch/
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── error_handler.py
│   │   └── request_logger.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── db.py
│   ├── option_chain/
│   ├── orders/
│   ├── paper_trading/
│   ├── positions/
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── holding_repository.py
│   │   ├── order_repository.py
│   │   ├── position_repository.py
│   │   └── watchlist_repository.py
│   ├── risk/
│   ├── services/
│   ├── settings/
│   └── websocket/
├── config/
│   ├── __init__.py
│   ├── base.py
│   ├── development.py
│   ├── production.py
│   └── testing.py
├── data/
│   └── kotak_terminal.db
├── docs/
│   ├── architecture_decisions.md
│   ├── broker_findings.md
│   ├── known_issues.md
│   ├── lessons_learned.md
│   ├── adr/
│   │   ├── ADR-001-SQLite.md
│   │   ├── ADR-002-Broker-Adapter.md
│   │   ├── ADR-003-Paper-Trading.md
│   │   ├── ADR-004-Session-Management.md
│   │   ├── ADR-005-Security-Request-Tracing.md
│   │   ├── ADR-006-Broker-Session-Management.md
│   │   └── ADR-007-Kotak-Integration-Strategy.md
│   └── releases/
│       ├── M1_BASELINE.md
│       └── M1_ARCHITECTURE_SNAPSHOT.md
├── migrations/
│   ├── versions/
│   │   ├── 4a7a9972b64d_create_users_and_sessions_tables.py
│   │   └── 6b0dd678a5e4_create_broker_sessions_table.py
│   └── env.py
└── tests/
    ├── integration/
    ├── system/
    └── unit/
```

---

## 2. Major Services & Architecture Topology

```
+---------------------------------------------------------------------------------------+
|                                    PRESENTATION LAYER                                 |
|   /api/auth/* (Routes)             /api/broker/* (Routes)           /api/health       |
+-------------------------------------------+-------------------------------------------+
                                            |
                                            v
+---------------------------------------------------------------------------------------+
|                                    MIDDLEWARE GATES                                   |
|   request_logger (Correlation IDs)  |  @login_required (Auth)  |  error_handler (JSON)|
+-------------------------------------------+-------------------------------------------+
                                            |
                                            v
+---------------------------------------------------------------------------------------+
|                                     SERVICE LAYER                                     |
|   +-----------------------+   +------------------------+   +----------------------+   |
|   |      AuthService      |   |  BrokerSessionManager  |   | BrokerHealthService  |   |
|   |  - Register / Login   |   |  - Token Encryption    |   | - Latency Monitor    |   |
|   |  - Hash Passwords     |   |  - Session Recovery    |   | - 5-State Machine    |   |
|   +-----------------------+   +------------------------+   +----------------------+   |
|   +-----------------------+   +------------------------+   +----------------------+   |
|   |     SessionManager    |   |    EncryptionService   |   |     TOTPService      |   |
|   |  - Bearer Token CRUD  |   |  - Fernet AES-128-CBC  |   | - Dynamic 2FA Codes  |   |
|   +-----------------------+   +------------------------+   +----------------------+   |
+---------------------+---------------------+---------------------+---------------------+
                      |                     |                     |
                      v                     v                     v
+---------------------------+ +---------------------------+ +---------------------------+
|      REPOSITORY LAYER     | |       EVENT BUS LAYER     | |        ADAPTER LAYER      |
| UserRepository            | | publish(EVENT, payload)   | | KotakBrokerAdapter        |
| SessionRepository         | | subscribe(EVENT, handler) | | (Encapsulates NeoAPI)     |
| BrokerSessionRepository   | |                           | | BrokerCache (In-memory)   |
+-------------+-------------+ +-------------+-------------+ +-------------+-------------+
              |                             |                             |
              v                             v                             v
+---------------------------------------------------------------------------------------+
|                                     DATA / SINK LAYER                                 |
|  SQLite DB (kotak_terminal.db)     Audit Trail (terminal.log)     Live Kotak Neo API  |
+---------------------------------------------------------------------------------------+
```

---

## 3. Database Schema

### Table: `users`
- `id` (INTEGER, PK, Autoincrement)
- `username` (VARCHAR(64), Unique, Indexed, Not Null)
- `email` (VARCHAR(120), Unique, Indexed, Not Null)
- `password_hash` (VARCHAR(256), Not Null)
- `is_active` (BOOLEAN, Default: 1, Not Null)
- `created_at` (DATETIME, Not Null)
- `updated_at` (DATETIME, Not Null)

### Table: `sessions` (Terminal Operator Session)
- `id` (INTEGER, PK, Autoincrement)
- `user_id` (INTEGER, FK -> `users.id` CASCADE, Indexed, Not Null)
- `token_hash` (VARCHAR(64), Unique, Indexed, Not Null)
- `ip_address` (VARCHAR(45), Nullable)
- `user_agent` (VARCHAR(256), Nullable)
- `expires_at` (DATETIME, Indexed, Not Null)
- `last_activity` (DATETIME, Not Null)
- `is_active` (BOOLEAN, Default: 1, Indexed, Not Null)
- `created_at` (DATETIME, Not Null)
- `updated_at` (DATETIME, Not Null)

### Table: `broker_sessions` (Kotak Connectivity Session)
- `id` (INTEGER, PK, Autoincrement)
- `user_id` (INTEGER, FK -> `users.id` CASCADE, Indexed, Not Null)
- `broker_name` (VARCHAR(32), Default: `'KOTAK_NEO'`, Not Null)
- `session_token_encrypted` (TEXT, Not Null)
- `refresh_token_encrypted` (TEXT, Nullable)
- `login_time` (DATETIME, Not Null)
- `expiry_time` (DATETIME, Not Null)
- `is_active` (BOOLEAN, Default: 1, Not Null)
- `created_at` (DATETIME, Not Null)
- `updated_at` (DATETIME, Not Null)

---

## 4. Active Architecture Decision Records (ADRs)

| ADR ID | Title | Status | Scope |
|---|---|---|---|
| `ADR-001` | SQLite for Operational Persistence | Accepted | Local low-latency ACID storage with WAL mode. |
| `ADR-002` | Broker Adapter Pattern & SDK Isolation | Accepted | Strict encapsulation preventing broker lock-in. |
| `ADR-003` | Paper Trading Execution Engine Isolation | Accepted | Architectural boundaries for virtual matching. |
| `ADR-004` | Operator Session Lifecycle & Token Management | Accepted | Bearer token tracking in `sessions` table. |
| `ADR-005` | Request Tracing & Correlation Lineage | Accepted | `X-Correlation-ID` context propagation across threads. |
| `ADR-006` | Dedicated Broker Session Management & State Restoration | Accepted | Decoupled `broker_sessions` with Fernet encryption. |
| `ADR-007` | Kotak Neo Broker Integration & Health Diagnostics | Accepted | 2FA orchestration via `pyotp` and health states. |

---

## 5. Event Bus Events

| Event Constant | Payload Signature | Trigger Point |
|---|---|---|
| `BROKER_CONNECTED` | `{"user_id": int, "broker": str}` | Successful initial broker handshake. |
| `BROKER_AUTHENTICATED` | `{"user_id": int, "broker": str}` | Broker session activated with verified tokens. |
| `BROKER_SESSION_RESTORED` | `{"user_id": int, "broker": str}` | Active broker session recovered and upstream-validated. |
| `BROKER_SESSION_EXPIRED` | `{"broker_session_id": int}` | Broker session validity window elapsed or rejected. |
| `BROKER_DISCONNECTED` | `{"user_id": int, "broker": str}` | Intentional logout or complete socket severance. |

---

## 6. Audit Framework Events

| Category | Action Constant | Audit Trigger Context |
|---|---|---|
| `AUTH` | `LOGIN_SUCCESS` | Operator authenticated successfully via password/token. |
| `AUTH` | `LOGIN_FAILED` | Operator authentication failed (bad password or inactive user). |
| `AUTH` | `LOGOUT` | Operator logged out; active session invalidated. |
| `AUTH` | `PASSWORD_CHANGED` | User credentials updated; cascades session termination. |
| `SESSION` | `SESSION_CREATED` | New terminal operator session row created in `sessions`. |
| `SESSION` | `SESSION_EXPIRED` | Operator session surpassed validity cutoff. |
| `BROKER` | `BROKER_LOGIN_SUCCESS` | Operator successfully authenticated Kotak Neo broker. |
| `BROKER` | `BROKER_LOGIN_FAILED` | Kotak Neo authentication rejected by upstream API. |
| `BROKER` | `BROKER_SESSION_CREATED` | Encrypted broker credentials persisted to `broker_sessions`. |
| `BROKER` | `BROKER_SESSION_RESTORED`| Cold-start restoration succeeded with upstream validation. |
| `BROKER` | `BROKER_SESSION_EXPIRED` | Broker token expired or rejected during restore. |
| `BROKER` | `BROKER_LOGOUT` | Broker session terminated and marked inactive. |
| `BROKER` | `BROKER_HEALTH_CHECK` | Diagnostic health check executed and recorded. |
