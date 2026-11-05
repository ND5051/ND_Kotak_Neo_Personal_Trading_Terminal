# Lessons Learned & Operational Insights

## Phase 1: Project Skeleton & Architectural Foundation
- **Isolation of Dependencies**: Virtual environments (`.venv`) on local developer machines must be kept self-contained to avoid polluting global Python 3.14 installations.
- **SQLite Concurrency & Multi-threading**: When using SQLite with multi-threaded web servers (Flask / Flask-SocketIO), `check_same_thread=False` and connection scoped sessions are mandatory to prevent `SQLite objects created in a thread can only be used in that same thread` exceptions.
- **Strict Decoupling via Event Bus**: Implementing an in-memory thread-safe `EventBus` at Phase 1 prevents cyclic dependencies between the order engine, risk checks, and frontend notification streams in upcoming phases.
- **Log Formatting Integrity**: Emitting pure JSON log records directly to stdout and rotating files ensures production log ingestion pipelines (ELK / Vector / Loki) parse logs without brittle regexes.

