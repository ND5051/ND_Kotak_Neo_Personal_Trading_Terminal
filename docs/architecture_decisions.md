# Architecture Decisions Summary

## Architectural Hierarchy
1. **Correctness > Features**: Financial accuracy and strict validation precede new capabilities.
2. **Reliability > Speed**: Predictable, resilient execution supersedes premature latency optimization.
3. **Recovery > Elegance**: Disaster recovery and state reconstruction must succeed even under corrupted sessions.
4. **Auditability > Convenience**: Every single state-altering trade event must leave a trace.
5. **State Consistency > Performance**: In-flight state must match broker reality before taking actions.

## Index of Architecture Decision Records (ADRs)
- [ADR-001: SQLite as Initial Local Persistence Layer](adr/ADR-001-SQLite.md)
- [ADR-002: Broker Adapter Abstraction Pattern](adr/ADR-002-Broker-Adapter.md)
- [ADR-003: Unified Architecture for Paper and Live Trading](adr/ADR-003-Paper-Trading.md)

