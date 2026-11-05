# ADR-007: Kotak Neo Broker Integration & Health Monitoring Strategy

## Status
Accepted

## Context
Integrating the Kotak Neo broker API (`kotakneoapi`) requires strict governance to satisfy Project Constitution Rule 1 ("No direct broker SDK calls outside Broker Adapter") while managing multi-factor authentication (MPIN + TOTP), token rotation, capability discovery, and connection health diagnostics.

## Decision
1. **Contract Adherence**: `KotakBrokerAdapter` exclusively implements the strict `BrokerInterface`, encapsulating all SDK imports, error transformations, and session interactions.
2. **Dynamic TOTP Generation**: Utilizes `pyotp` to dynamically compute valid 6-digit TOTP tokens from configured secrets at authentication time.
3. **Capability Discovery & In-Memory Cache**: Discovers supported exchanges, products, and order types dynamically via `get_capabilities()` and caches them in `broker_cache` to eliminate repeated redundant REST round-trips.
4. **Health Diagnostics**: `BrokerHealthService` polls and classifies connectivity into explicit states: `CONNECTED`, `DISCONNECTED`, `AUTHENTICATED`, `SESSION_EXPIRED`, `LOGIN_REQUIRED`.
5. **Trading Logic Isolation**: Strictly omits order placement, modification, cancellation, positions, holdings, and WebSocket streaming in Phase 3.

## Consequences
### Positive
- Strict encapsulation ensures changes to the Kotak Neo SDK do not bleed into application business logic.
- Enables complete headless verification and mocking without hitting live broker rate limits.
- Diagnostic transparency through structured JSON logs and audit records.

### Negative / Trade-offs
- Requires maintaining adapter compatibility across Kotak SDK version updates.

## Compliance with Project Constitution
- **Rule 1 (No Direct Broker SDK Calls)**: All broker communication is confined to `KotakBrokerAdapter`.
- **Reliability > Speed**: Predictable health evaluation prevents sending transactions to dead sessions.

