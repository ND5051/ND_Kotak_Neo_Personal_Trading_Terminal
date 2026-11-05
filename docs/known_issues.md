# Known Issues & Workarounds

## Phase 1
- **Issue**: SQLite write contention under heavy concurrent writes.
  - **Mitigation**: Use WAL (Write-Ahead Logging) mode and keep transactional units of work short. In future scaling phases, migration to PostgreSQL can be achieved without domain code changes via SQLAlchemy & Alembic.
- **Issue**: Flask development server reload mechanism spawning double processes.
  - **Mitigation**: When testing WebSockets and event listeners, run with `use_reloader=False` in interactive debugging sessions if duplicate event emissions are observed.

