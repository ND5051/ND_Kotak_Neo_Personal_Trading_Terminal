# Kotak Neo Personal Trading Terminal
## Release Notes — Milestone M1 Baseline

**Release Version:** Milestone M1 Baseline  
**Release Date:** 2026-11-06  
**Target Platform:** Kotak Neo Broker API (`kotakneoapi>=3.0.13`)  
**Architecture Status:** Stable / Production Foundation  
**Test Suite Status:** 51 / 51 Passing (100% Coverage of Baseline Capabilities)  
**Git Commit Reference:** `bc11ff1`  

---

## 1. Executive Summary

Milestone M1 establishes the enterprise-grade foundation for the Kotak Neo Personal Trading Terminal. Spanning Phases 1, 2, and 3, this milestone delivers a resilient, auditable, and secure backend infrastructure designed specifically for live algorithmic trading.

In strict adherence to the **Project Constitution**, Milestone M1 establishes core infrastructure—including user identity, encrypted session lifecycles, correlation tracing, broker connectivity, capability discovery, and disaster recovery—while deliberately excluding financial execution logic (order placement, market watch feeds, positions, and live tick streaming).

---

## 2. Implemented Features

### Phase 1 — Project Foundation & Architecture Skeleton
* **Application Factory Pattern (`create_app`)**:
  - Environment-driven configuration resolution (`DevelopmentConfig`, `TestingConfig`, `ProductionConfig`).
  - Dynamic blueprint registration and dependency injection.
  - Standardized error handling and API response envelopes (`api_response`, `api_error`).
* **Structured JSON Logging Framework (`app/logging`)**:
  - Pure JSON log record formatting with ISO-8601 UTC timestamps, log levels, process IDs, and contextual metadata.
  - Dual-output logging to `stdout` and rotating log sinks in `logs/terminal.log`.
* **In-Memory Event Bus (`app/events`)**:
  - Decoupled, thread-safe Publish/Subscribe engine for asynchronous system coordination.
  - Isolated exception boundaries preventing broken subscriber handlers from disrupting event publishers.
* **Feature Flags Engine (`app/core/feature_flags.py`)**:
  - Granular runtime capability toggles (e.g. `PAPER_TRADING`, `GTT`, `SCANNER_ENGINE`, `STRATEGY_ENGINE`, `NOTIFICATIONS`).
* **Database & Repository Framework (`app/models`, `app/repositories`)**:
  - SQLAlchemy ORM foundation with connection pooling and thread safety.
  - Generic `BaseRepository[T]` with full CRUD patterns.
  - Alembic database migration management.

### Phase 2 — Authentication, Security & Session Foundation
* **Local User Identity & Credential Security (`app/auth`)**:
  - User registration and authentication workflows with salted password hashing (Werkzeug).
  - Defense against credential leakage (zero plaintext password storage).
* **Terminal Operator Session Management (`sessions` Table)**:
  - Secure 64-character URL-safe session token issuance.
  - Absolute session expiration and sliding window activity tracking.
  - Defense-in-depth session revocation on logout, account deactivation, or password changes.
* **Request Context & Correlation Tracing (`app/core/request_context.py`)**:
  - Automatic `request_id` and `correlation_id` injection across all inbound HTTP requests via middleware.
  - Bidirectional header propagation (`X-Correlation-ID`, `X-Request-ID`) linking client interactions to audit logs.
* **Symmetric Encryption Engine (`app/core/encryption.py`)**:
  - AES-128-CBC + HMAC-SHA256 authenticated encryption (`Fernet`).
  - Key derivation via SHA-256 over `ENCRYPTION_KEY` / `SECRET_KEY`.
  - Cryptographic tamper resistance and verified key-rotation capabilities.
* **Central Audit Framework (`app/core/audit.py`)**:
  - Append-only audit logger supporting categorized actions (`AUTH`, `SESSION`, `SYSTEM`).
  - Immutable `AuditRecord` tracking actor, correlation ID, request ID, event ID, and structured JSON payloads.
* **Two-Factor Authentication (TOTP) Scaffold (`app/auth/services/totp_service.py`)**:
  - Base32 secret generation, QR provisioning URI generation, and RFC-6238 time-based OTP verification.

### Phase 3 — Kotak Neo Session Management & Broker Connectivity
* **Broker Adapter Contract (`app/broker/interfaces/broker_interface.py`)**:
  - Strict abstract base class defining session lifecycle, health diagnostics, and capability discovery.
  - **Zero-Order Governance**: Deliberately omits order methods (`place_order`, `modify_order`, `cancel_order`) to enforce phase boundaries.
* **Production Kotak Neo Adapter (`app/broker/adapters/kotak_adapter.py`)**:
  - Encapsulates `kotakneoapi` (`NeoAPI`) SDK interactions behind strict adapter boundaries.
  - Automated 2FA generation using `pyotp` from configured base32 TOTP secrets.
  - Fallback and mock simulation hooks for automated headless CI/CD testing.
* **Decoupled Two-Tier Session Architecture (`broker_sessions` Table)**:
  - Complete isolation between terminal operator sessions (`sessions` table) and broker connectivity (`broker_sessions` table).
  - Prevents third-party broker session expiries from disrupting terminal operator navigation or audit inspection.
* **Encrypted At-Rest Broker Credentials**:
  - Broker session tokens and refresh tokens encrypted via `EncryptionService` before persistence to SQLite.
  - Plaintext tokens never exposed in database dumps, serialization outputs, or API responses.
* **Resilient Session Recovery Engine (`restore_session`)**:
  - Autonomous restoration of broker connectivity on terminal reboot or reconnect.
  - Mandatory upstream validation: verifies token validity with Kotak before activating session status, strictly preventing "ghost sessions".
  - Automatic deactivation and audit recording of expired or corrupted sessions without human intervention.
* **Broker Health Monitoring Service (`app/broker/services/broker_health_service.py`)**:
  - Formal state machine: `CONNECTED`, `DISCONNECTED`, `AUTHENTICATED`, `SESSION_EXPIRED`, `LOGIN_REQUIRED`.
  - Live round-trip latency tracking in milliseconds.
* **Broker Capability Discovery & Thread-Safe Cache (`app/broker/cache/broker_cache.py`)**:
  - Dynamic discovery of supported exchanges (`NSE`, `BSE`, `NFO`, `BFO`, `MCX`), products (`MIS`, `CNC`, `NRML`), and segments.
  - Thread-safe caching with `threading.RLock`. Prohibits tick or quote caching.
* **REST API Endpoints (`app/broker/routes.py`)**:
  - `GET /api/broker/status` — Diagnostic connectivity health check.
  - `GET /api/broker/capabilities` — Discovered exchanges and capability flags.
  - `POST /api/broker/login` — Operator-authenticated broker login & token encryption.
  - `POST /api/broker/restore` — Autonomous session restoration.
  - `POST /api/broker/logout` — Broker session termination and revocation.

---

## 3. Architecture Status

| Architectural Domain | Status | Compliance & Verification |
|---|---|---|
| **Project Constitution** | **100% Compliant** | Adheres to Rules 1 through 9 (Encapsulated SDK, Mandatory Auditing, State Recovery). |
| **Separation of Concerns** | **Verified** | Strict layering: Interfaces -> Adapters -> Services -> Repositories -> ORM Models. |
| **Database Persistence** | **Active (Alembic Head)** | SQLite schema with 3 tables (`users`, `sessions`, `broker_sessions`) and foreign keys. |
| **Security Posture** | **Enterprise Grade** | Salted password hashing, Fernet symmetric encryption, zero token leaks, tamper detection. |
| **Request Tracing** | **Active** | Unbroken `correlation_id` lineage linking HTTP calls to database actions and audit logs. |
| **Test Suite** | **51 / 51 Passing** | Unit, integration, recovery, health, security, and exception suites validated in Python 3.14. |
| **Operational Documentation** | **Complete** | Architecture reviews (`PHASE1`, `PHASE2`, `PHASE3`), ADRs (ADR-001 through ADR-007), and M1 QA Manual. |

---

## 4. Known Limitations

The following limitations are **deliberate architectural constraints** established for the Milestone M1 Baseline:

1. **No Financial Execution**:
   - Order placement, modification, and cancellation routes and methods are not yet implemented.
2. **No Real-Time Market Feed**:
   - WebSocket streaming (`SFeed`) and tick data parsing are disabled; `BrokerCache` does not store live quotes.
3. **No Portfolio Retrieval**:
   - Fetching live positions, account holdings, margin balances, and option chains will be introduced in subsequent phases.
4. **Local In-Memory Event Bus**:
   - The event bus operates within the Flask process memory space. It is optimized for single-terminal personal deployments rather than multi-node distributed clusters.
5. **Single-Broker Active Instance**:
   - While `BrokerSession` models allow multiple broker records over time, the runtime adapter is currently configured for a single active Kotak Neo connection per terminal instance.

---

## 5. Future Phases Roadmap

The completion of Milestone M1 clears the path for downstream trading capabilities:

```
[M1 Baseline (Completed)]
├── Phase 1: Foundation & Architecture Skeleton
├── Phase 2: Authentication, Security & Sessions
└── Phase 3: Kotak Connectivity & Recovery
           │
           v
[Milestone M2 — Market Data & Real-Time Feeds]
├── Phase 4: Kotak Neo SFeed WebSocket Streaming
│   ├── Binary Tick Parser (LTP, Quotes, Depth)
│   ├── Market Watch Service & Subscriptions
│   └── Real-time Socket.IO Frontend Broadcast
           │
           v
[Milestone M3 — Defensive Execution Engine]
├── Phase 5: Order Execution & Lifecycle Management
│   ├── Order Placement, Modification, Cancellation (LIMIT, MKT, SL, SL-M)
│   ├── Order State Reconciliation & Execution Machine
│   └── Defensive Pre-Trade Risk Checks & Slippage Guard
├── Phase 6: Portfolio & Position Tracking
│   ├── Real-Time Holdings & Position Reconciliation
│   └── Live MTM Calculation & Risk Limit Monitor
           │
           v
[Milestone M4 — Advanced Trading Features]
├── Phase 7: Option Chain & Multi-Leg Derivatives Analytics
│   ├── Real-Time Option Chain Matrix & Greeks
│   └── Multi-Leg Strategy Payoffs & Basket Orders
├── Phase 8: Paper Trading Simulation Engine
│   └── Zero-Capital Virtual Execution with Realistic Slippage
           │
           v
[Milestone M5 — Production Terminal UI]
└── Phase 9: Modern Reactive Trading Dashboard
    ├── Dark-Themed Professional Trading Interface
    └── Order Tickets, Depth Ladders, and Position Monitor
```

---

*Milestone M1 Baseline approved for staging and architectural sign-off.*
