# Milestone M1 Baseline Specification
## Architecture, Security & Broker Connectivity Foundation

**Milestone Identifier:** `M1_BASELINE`  
**Milestone Status:** ACCEPTED & LOCKED  
**Baseline Date:** 2026-11-06  
**Git Tag:** `M1_BASELINE`  
**Database Schema Revision:** `6b0dd678a5e4 (head)`  
**Platform Target:** Kotak Neo Broker API (`kotakneoapi>=3.0.13`)  
**Test Suite Verification:** 51 / 51 Passing (100% Pass Rate)  

---

## 1. Milestone Overview

### 1.1 Purpose of M1
Milestone M1 establishes the unified, non-trading architectural foundation for the Kotak Neo Personal Trading Terminal. Comprising Phases 1, 2, and 3, this milestone provides all enterprise-grade infrastructure—system lifecycle, security, session management, auditing, request correlation, broker connectivity, capability discovery, and automated disaster recovery—required before introducing any financial execution logic.

### 1.2 What Has Been Implemented
Across Phases 1, 2, and 3, the following capabilities have been developed and integrated:
- **Application Core**: App factory, environment-driven configuration hierarchy, thread-safe Pub/Sub event bus, feature flags engine, and structured JSON logging.
- **Security & Identity**: Local user identity with salted password hashing, decoupled operator sessions, Bearer token lifecycle, request context propagation, symmetric AES-128-CBC token encryption at rest, TOTP 2FA framework, and an append-only audit trail.
- **Broker Connectivity**: Strict broker adapter contract, Kotak Neo adapter with dynamic TOTP generation, independent broker sessions table, upstream-validated session restoration, health monitoring with round-trip latency tracking, and thread-safe capability caching.

### 1.3 What Has Been Validated
The integrated baseline has been subjected to rigorous validation:
- Automated test suites (`51/51` passing tests spanning unit, integration, recovery, security, and health checks).
- End-to-end manual QA procedures documented in [`MILESTONE_M1_VALIDATION.md`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/MILESTONE_M1_VALIDATION.md).

---

## 2. Delivered Components

### 2.1 Architecture Foundation (Phase 1)
| Component | Module Location | Description |
|---|---|---|
| **Application Factory** | `app/__init__.py:create_app` | Environment-aware bootstrapping, blueprint registration, and dependency injection. |
| **Configuration Management** | `config/base.py`, `config/*.py` | Hierarchical configuration with `.env` overrides and strict defaults. |
| **Logging Framework** | `app/logging/` | Structured JSON log formatter emitting ISO-8601 timestamps, log levels, and contextual metadata to `stdout` and rotating `logs/terminal.log`. |
| **Event Bus** | `app/events/event_bus.py` | In-memory, thread-safe Pub/Sub message broker isolating subscriber failures. |
| **Repository Framework** | `app/repositories/base.py` | Generic `BaseRepository[T]` providing consistent CRUD persistence operations. |
| **Audit Framework** | `app/core/audit.py` | Central `AuditLogger` writing immutable audit entries linked to request correlation IDs. |

### 2.2 Security Foundation (Phase 2)
| Component | Module Location | Description |
|---|---|---|
| **Authentication** | `app/auth/services/auth_service.py` | User registration and credential verification with salted password hashing. |
| **Authorization** | `app/auth/decorators.py:login_required` | Bearer token extraction, session validation, and `g.current_user` injection. |
| **Session Management** | `app/auth/services/session_manager.py` | 64-character URL-safe session token issuance, sliding activity tracking, and cascade revocation. |
| **Request Context** | `app/core/request_context.py` | Thread-local storage capturing `request_id`, `correlation_id`, `user_id`, and `session_id`. |
| **Correlation IDs** | `app/middleware/request_logger.py` | Middleware extracting or generating `X-Correlation-ID` and propagating headers across requests and logs. |
| **Encryption Service** | `app/core/encryption.py` | Authenticated symmetric encryption (Fernet AES-128-CBC + HMAC-SHA256) for protecting sensitive tokens at rest. |
| **TOTP Foundation** | `app/auth/services/totp_service.py` | RFC-6238 time-based one-time password generation and verification scaffold. |

### 2.3 Broker Foundation (Phase 3)
| Component | Module Location | Description |
|---|---|---|
| **Broker Interface** | `app/broker/interfaces/broker_interface.py` | Formal abstract contract defining broker lifecycle, health, and discovery with zero order methods. |
| **Kotak Adapter** | `app/broker/adapters/kotak_adapter.py` | Encapsulates `kotakneoapi` (`NeoAPI`) with dynamic TOTP computation via `pyotp`. |
| **Broker Session Manager** | `app/broker/services/broker_session_manager.py` | Manages broker credentials, encryption, session persistence, and lifecycle transitions. |
| **Broker Health Framework** | `app/broker/services/broker_health_service.py` | Continuous health diagnostics evaluating `CONNECTED`, `DISCONNECTED`, `AUTHENTICATED`, `SESSION_EXPIRED`, and `LOGIN_REQUIRED`. |
| **Capability Discovery** | `KotakBrokerAdapter.get_capabilities` | Discovers supported exchanges (`NSE`, `BSE`, `NFO`, `BFO`, `MCX`), products, order types, and segment flags. |
| **Session Recovery** | `BrokerSessionManager.restore_session` | Autonomous recovery requiring upstream broker validation; automatically purges expired or corrupt sessions. |

---

## 3. Validation Results

| Test Procedure | Verification Scope | Status | Notes |
|---|---|---|---|
| **Application Startup** | Bootstrapping & DB Initialization | **PASSED** | Clean startup, tables checked, JSON logging active. |
| **User Registration** | Salted password hashing & uniqueness | **PASSED** | Duplicate usernames/emails cleanly rejected (`400 Bad Request`). |
| **User Login** | Bearer token generation & auditing | **PASSED** | Valid credentials return 64-char token; audit entry recorded. |
| **Protected Route Access** | `@login_required` middleware | **PASSED** | Unauthenticated requests return `401 Unauthorized`; valid tokens populate `g.current_user`. |
| **Broker Capability Discovery** | Query `/api/broker/capabilities` | **PASSED** | Exchanges reported; order placement confirmed `false`. |
| **Broker Login** | Multi-factor auth & token encryption | **PASSED** | Dynamic TOTP generated; tokens encrypted with Fernet before SQLite storage. |
| **Broker Health Diagnostics** | Query `/api/broker/status` | **PASSED** | Evaluates status (`AUTHENTICATED`), records round-trip latency (>0 ms). |
| **Session Recovery** | Cold-start restoration | **PASSED** | Restores valid sessions; rejects expired or tampered ciphertexts. |

---

## 4. Known Limitations

In compliance with the **Project Constitution**, the following features are intentionally omitted from Milestone M1:

1. **No Orders**: Zero endpoints or adapter methods exist for `place_order`, `modify_order`, or `cancel_order`.
2. **No Market Watch**: No instrument master download or live market watch polling.
3. **No Holdings**: No portfolio equity holdings retrieval or portfolio valuation.
4. **No Positions**: No open position tracking, day positions, or MTM calculations.
5. **No Option Chain**: No strike matrix, option Greeks, or derivatives lookup.
6. **No Streaming**: WebSocket tick feeds (`SFeed`) are not initialized; quotes are not cached.

