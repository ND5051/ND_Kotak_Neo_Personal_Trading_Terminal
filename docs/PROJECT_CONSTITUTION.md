# PROJECT CONSTITUTION: Kotak Neo Personal Trading Terminal

## Core Architecture Principles
The following architectural hierarchy is non-negotiable for all design, implementation, and operations:

```
Correctness > Features
Reliability > Speed
Recovery    > Elegance
Auditability> Convenience
State Consistency > Performance
```

---

## Non-Negotiable Tenets (Rules 1 to 10)

### Rule 1: No direct broker SDK calls outside Broker Adapter
Direct calls to the Kotak Neo API SDK (`kotakneoapi` / `neo-api-client` or any underlying HTTP/WebSocket endpoints) are strictly forbidden across UI, services, routes, or strategies. All communication must pass through an explicit implementation of `BrokerInterface` inside `app/broker/adapters/`.

### Rule 2: All order actions must pass through Order Engine
No module may place, modify, or cancel orders directly with the adapter. All order requests must go through the Order Engine and Order Service, undergoing state validation, risk validation, and audit recording.

### Rule 3: All critical actions must be auditable
Every state-altering operation—including authentication, order placement, order modification, order cancellation, risk boundary breach, system startup, and recovery—must be persistently logged via the Audit Framework (`app/core/audit.py`).

### Rule 4: All features require tests
No code reaches production without accompanying automated unit tests and integration tests covering positive paths, boundary conditions, and catastrophic failure modes.

### Rule 5: Every phase requires rollback instructions
Every development phase, migration, and deployment must come with explicit, tested rollback instructions to revert state safely without data loss or orphan orders.

### Rule 6: Every phase updates `lessons_learned.md`
At the conclusion of each development phase, architectural findings, unexpected behavior, and broker-specific idiosyncrasies must be documented in `docs/lessons_learned.md`.

### Rule 7: No phase proceeds without approval
Work proceeds strictly in gated phases. No subsequent phase may be started or suggested until the current phase is fully reviewed, tested, and explicitly approved by the system owner.

### Rule 8: State recovery is mandatory
The system must be capable of reconstructing its complete in-memory portfolio, open order state, and position state from local persistence and broker reconciliation upon restart or unhandled crash.

### Rule 9: Trading safety overrides convenience
Fail-safe mechanisms, kill switches, and circuit breakers take precedence over user convenience or uninterrupted execution. When in doubt or during state divergence, the system must halt new order flow and protect capital.

### Rule 10: Paper and Live trading must share architecture
Paper trading and live trading must execute through identical interfaces, pipelines, data contracts, and risk checks. Paper trading differs only by routing execution through a simulated broker adapter rather than the live broker adapter.

---

## Phase Lifecycle & Governance
- **Phase 1**: Project Skeleton Specification & Architectural Foundation
- **Phase Gate**: Verification of tests, linters, application startup, and architectural compliance.
- **Sign-off**: Explicit user approval required prior to embarking on Phase 2.

