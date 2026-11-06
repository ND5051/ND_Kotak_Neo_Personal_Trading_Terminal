# Lessons Learned & Operational Insights

## Phase 1: Project Skeleton & Architectural Foundation
- **Isolation of Dependencies**: Virtual environments (`.venv`) on local developer machines must be kept self-contained to avoid polluting global Python 3.14 installations.
- **SQLite Concurrency & Multi-threading**: When using SQLite with multi-threaded web servers (Flask / Flask-SocketIO), `check_same_thread=False` and connection scoped sessions are mandatory to prevent `SQLite objects created in a thread can only be used in that same thread` exceptions.
- **Strict Decoupling via Event Bus**: Implementing an in-memory thread-safe `EventBus` at Phase 1 prevents cyclic dependencies between the order engine, risk checks, and frontend notification streams in upcoming phases.
- **Log Formatting Integrity**: Emitting pure JSON log records directly to stdout and rotating files ensures production log ingestion pipelines (ELK / Vector / Loki) parse logs without brittle regexes.

## Phase 2: Authentication, Security & Session Foundation
- **Module Attribute Rebinding in Python**: Importing mutable module globals directly (e.g., `from app.models.db import db_session`) binds the importing module's namespace to the object at import time (`None`). If initialized later during app factory bootstrap, the imported variable retains `None`. Replacing direct global imports with dynamic accessor functions (`get_session()`, `get_engine()`) completely resolves this decoupling challenge.
- **In-Memory SQLite Concurrency via StaticPool**: When running multi-step integration and unit tests with `sqlite:///:memory:`, standard SQLAlchemy connection pools allocate separate transient in-memory databases per connection. Enforcing `poolclass=StaticPool` for in-memory testing guarantees that all concurrent scoped sessions and threads operate on the identical schema and committed state.
- **Correlation ID Lineage**: Capturing incoming `X-Correlation-ID` (or minting a new one) at the earliest middleware gate and injecting it into `RequestContext` ensures unbroken operational tracing across authentication, audit records, and downstream trading engines.
- **Defense-in-Depth Session Invalidation**: Password changes or account disabling must immediately cascade to terminate all active sessions in the persistence layer (`deactivate_user_sessions`), preventing compromised tokens from continuing to execute requests.
- **Secure Secret Storage Readiness**: Using Fernet (AES-128-CBC + HMAC-SHA256) keyed via deterministic hash of `SECRET_KEY`/`ENCRYPTION_KEY` establishes an encryption engine ready to protect broker tokens and session keys at rest without premature SDK coupling.

## Phase 3: Kotak Session Management & Broker Connectivity Foundation
- **Separation of Operator Identity and Broker Sessions**: Operator sessions (`sessions` table) and broker connectivity (`broker_sessions` table) must remain strictly decoupled. Operators can log in and manage terminal settings without a broker session, while broker connections can be revived or rotated without disrupting UI operators.
- **Dynamic TOTP Synchronization**: Computing 2FA tokens directly inside the adapter via `pyotp` from configured base32 secrets eliminates human delays during morning pre-market authentication routines.
- **Fault-Tolerant Session Recovery**: Restoring broker sessions upon application startup requires a three-way defensive check: 1) local database record must be unexpired, 2) token decryption must authenticate with zero tampering, and 3) broker adapter must validate the token before declaring recovery successful.
- **Zero-Order Governance**: Enforcing a strict prohibition against order methods in `BrokerInterface` guarantees that connectivity and health checks are battle-tested and auditable before financial execution logic is exposed.

## Milestone M1: Operational Validation & Baseline Review

### 1. What Worked
- **Two-Tier Session Decoupling**: Separating local user operator identity (`sessions` table) from broker connectivity (`broker_sessions` table) prevented broker disconnects or token expiries from logging the operator out of the terminal.
- **Authenticated Symmetric Token Encryption**: Utilizing Fernet (AES-128-CBC + HMAC-SHA256) ensured stored broker credentials cannot be decoded from database dumps without the secret key, while automatically detecting tampering.
- **Upstream Session Validation on Recovery**: Requiring `adapter.restore_session()` during startup prevented ghost sessions by immediately marking invalid or revoked tokens inactive in SQLite.
- **Structured JSON Audit Trail**: Every sensitive action (`AUTH`, `SESSION`, `BROKER`) emitted an immutable audit record tied to `request_id` and `correlation_id`, establishing full accountability.
- **Automated Dynamic TOTP Generation**: Integrating `pyotp` directly inside `KotakBrokerAdapter` eliminated manual 2FA entry hurdles during automated tests and headless broker handshakes.

### 2. What Failed & Required Remediation
- **PowerShell Command Chaining**: Standard POSIX command separators (`&&`) caused parser failures in Windows PowerShell during manual verification scripts. Remediated by standardizing on PowerShell semicolons (`;`) or discrete command executions in all documentation.
- **Module Import Binding Hazard**: Importing mutable SQLAlchemy session globals (`db_session`) bound the importing module namespace to `None` at import time before initialization. Remediated across the codebase by replacing direct variable imports with dynamic accessor functions (`get_session()`, `get_engine()`).
- **SQLite In-Memory Test Isolation**: Testing in-memory SQLite instances across concurrent threads allocated disjoint transient databases. Remediated by enforcing `poolclass=StaticPool` for all in-memory test connections.
- **Port Contention During Fast Server Restarts**: Fast iterative manual restarts caused orphaned Python processes to hold TCP port 5000. Remediated by documenting process cleanup commands (`Get-Process python | Stop-Process`).

### 3. Testing Results
- **Automated Test Suite**: 51 / 51 tests passing (`100%` pass rate in 10.00 seconds).
  - Unit tests: 39 passing (Config, EventBus, Exceptions, Features, Repositories, Security, Session, TOTP, UserAuth, BrokerAdapter, BrokerSession, BrokerHealth, BrokerEncryption).
  - Integration tests: 4 passing (AppFactory, AuthRoutes, Database, BrokerRoutes).
  - System tests: 4 passing (Index, Health, FeatureFlags, 404 handler).
- **Manual QA Execution**: All 22 test procedures in `MILESTONE_M1_VALIDATION.md` verified and marked `PASSED`.

### 4. Architectural Observations
- **Strict Interface Boundaries Pay Dividends**: Isolating all third-party SDK calls within `KotakBrokerAdapter` enabled complete unit testing and mocking without leaking vendor classes into business services.
- **Zero-Order Discipline**: Resisting the temptation to build preliminary order placement logic during Phases 1–3 ensured the connectivity, encryption, session recovery, and health frameworks were thoroughly hardened before handling financial capital.
- **Event Bus Decoupling**: Having the broker layer emit event bus notifications (`BROKER_CONNECTED`, `BROKER_AUTHENTICATED`) rather than directly calling UI or data services will simplify the upcoming Phase 4 WebSocket and Market Data integration.
