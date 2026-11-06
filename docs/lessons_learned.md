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

## Milestone M1: Operational Validation & Quality Assurance Review

### 1. Authentication Validation Success
- **Salted Password Security**: Verification confirmed that user passwords are saved using Werkzeug salted hashing. Database table scans confirmed zero plaintext or reversibly hashed passwords in SQLite.
- **Token Generation & Integrity**: Login generation of 64-character URL-safe session tokens demonstrated predictable round-trip validation. Duplicate registrations on username or email were defended with strict `400 Bad Request` (`USER_ALREADY_EXISTS`) responses.
- **Credential Brute-Force & Failure Tracking**: Bad credentials triggered consistent `401 Unauthorized` (`INVALID_CREDENTIALS`) responses while recording an immutable audit event (`LOGIN_FAILED`), maintaining an uncorrupted audit history.

### 2. Protected Route Validation Success
- **Decorator Isolation (`@login_required`)**: Requests lacking the `Authorization: Bearer <token>` header or supplying expired/tampered tokens were rejected with `401 Unauthorized` (`INVALID_SESSION_TOKEN`) without reaching application route handlers.
- **Context Injection**: Valid tokens resolved the associated active session from SQLite, verified expiration bounds, touched the session activity timestamp, and injected the current user model into Flask's `g.current_user` for safe downstream access.

### 3. Broker Login Validation Success
- **Multi-Factor Orchestration**: The `/api/broker/login` route demonstrated complete coordination across operator identity verification, dynamic TOTP generation via `pyotp`, adapter authentication, and token encryption.
- **Cryptographic Storage Protection**: Session tokens and refresh tokens are encrypted via AES-128-CBC + HMAC-SHA256 (`Fernet`) before SQL write operations. Inspection of the SQLite database confirmed all stored tokens begin with the Fernet `gAAAA` header and never expose plaintext credentials in table rows, server logs, or JSON payloads.
- **Audit & Event Bus Dispatch**: Successful broker logins simultaneously triggered `BROKER_LOGIN_SUCCESS` and `BROKER_SESSION_CREATED` audit logs while publishing `BROKER_CONNECTED` and `BROKER_AUTHENTICATED` to the internal event bus.

### 4. Broker Capability Discovery Success
- **Dynamic Discovery & Caching**: Calling `/api/broker/capabilities` returned the full catalog of supported exchanges (`NSE`, `BSE`, `NFO`, `BFO`, `MCX`), supported products (`MIS`, `CNC`, `NRML`), and order types (`LIMIT`, `MARKET`, `SL`, `SL-M`).
- **Strict Scope Boundaries Enforced**: Capability inspection confirmed that trading features (`order_placement: false`, `market_streaming: false`) are disabled at the adapter contract level. Capabilities are cached in `BrokerCache` under `threading.RLock`, eliminating redundant compute overhead.

### 5. Issues Encountered During Manual Testing & Applied Remediation
- **PowerShell Shell Syntax Differences**:
  - *Symptom*: Using POSIX `&&` statement chaining in Windows PowerShell failed with a parser error (`The token '&&' is not a valid statement separator`).
  - *Remediation*: Manual test procedures in `MILESTONE_M1_VALIDATION.md` use PowerShell-native semicolons (`;`) or separate command invocations.
- **Windows CRLF vs LF Line Endings**:
  - *Symptom*: Staging files created with Unix LF line endings triggered Git core warnings on Windows (`LF will be replaced by CRLF`).
  - *Remediation*: Explicitly documented Git autocrlf handling and ensured file editors preserve workspace file formatting.
- **In-Memory SQLite Concurrency during Standalone Scripting**:
  - *Symptom*: Ad-hoc Python one-liners testing SQLite in-memory without persistent disk DB require using `sqlite:///data/kotak_terminal.db` or initial table bootstrap; running against `data/kotak_terminal.db` requires running `alembic upgrade head` first.
  - *Remediation*: Documented that all manual CLI verification scripts must import `init_db()` pointing to the configured database file or run Alembic migrations prior to querying.
- **HTTP Client Header Normalization**:
  - *Symptom*: Certain HTTP testing tools lower-case headers (e.g. `x-correlation-id`), which could cause lookup misses if matching is case-sensitive.
  - *Remediation*: Request context middleware was built to retrieve headers using case-insensitive mapping (`request.headers.get('X-Correlation-ID')`), guaranteeing traceability across varied client implementations.
- **Port Contention on Rapid Restart Cycles**:
  - *Symptom*: Stopping and restarting the Flask terminal server rapidly during manual test runs occasionally left orphaned Python background processes holding TCP port 5000.
  - *Remediation*: Added explicit process-killing troubleshooting steps (`Get-Process python | Stop-Process`) to the QA execution manual.
