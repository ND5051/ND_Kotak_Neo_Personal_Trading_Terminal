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
