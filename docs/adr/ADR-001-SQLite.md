# ADR-001: SQLite as Primary Local Persistence Engine

## Status
Accepted

## Context
The terminal is designed as a personal, single-trader, browser-based execution cockpit. We require a persistent store for local state reconstruction, audit logging, order journals, watchlist configs, and feature preferences. A heavy client-server database (e.g., standalone PostgreSQL cluster) introduces deployment overhead, network latency, and operational fragility on a local single-user machine.

## Decision
We select **SQLite** combined with **SQLAlchemy 2.0** and **Alembic** for schema migrations.
- Database access is abstracted via the Repository Pattern (`BaseRepository`).
- SQLite database is stored locally in `data/kotak_terminal.db`.
- Schema migrations are versioned via Alembic to allow seamless schema updates.
- In-memory SQLite (`sqlite:///:memory:`) is utilized for high-speed automated unit and integration tests.

## Consequences
### Positive
- Zero external dependencies or background services required to boot the application.
- Self-contained, portable database file that can be easily backed up before market open.
- Fast execution for local transactions.

### Negative / Trade-offs
- File lock contention if multiple external processes attempt simultaneous writes.
- Mitigated by connection pooling parameters, WAL mode, and keeping write transactions localized.

## Compliance with Project Constitution
- **Reliability > Speed**: Embedded database eliminates network socket partition risks.
- **Recovery > Elegance**: Backups and state restore are as simple as copying a single `.db` file.

