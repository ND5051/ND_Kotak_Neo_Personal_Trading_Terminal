# ADR-006: Dedicated Broker Session Management & State Restoration

## Status
Accepted

## Context
Third-party broker sessions (Kotak Neo) operate on distinct authentication lifecycles, token renewal horizons, and security postures compared to user application sessions. Conflating local operator authentication with broker authentication violates single responsibility, introduces security exposure, and complicates automated disaster recovery upon terminal restarts.

## Decision
We introduce a dedicated **Broker Session Management Framework**:
1. **Decoupled Architecture**: `BrokerSession` is isolated from user `Session` records and stored in the dedicated `broker_sessions` table.
2. **Encrypted at Rest**: All access tokens, refresh tokens, and session identifiers are symmetrically encrypted via `EncryptionService` before persisting.
3. **Automated Session Recovery**: On startup or user reconnect, `restore_session()` retrieves the active broker session, decrypts credentials, and validates the session against the broker adapter. If valid, connectivity is restored without re-prompting credentials; if expired or corrupted, the session is deactivated without human intervention.
4. **State Transition Auditing**: Generates dedicated audit events (`BROKER_SESSION_CREATED`, `BROKER_SESSION_RESTORED`, `BROKER_SESSION_EXPIRED`) and publishes decoupling events to the internal Event Bus.

## Consequences
### Positive
- Strict isolation between operator sessions and financial execution credentials.
- Zero plaintext exposure of broker session tokens in database backups or dumps.
- Seamless crash recovery and cold-start reconnects.

### Negative / Trade-offs
- Requires encryption/decryption cycle per broker credential storage and restoration.
- Requires managing token synchronization with Kotak's intraday token expiration schedule.

## Compliance with Project Constitution
- **Rule 3 (Audit Everything)**: Every broker session lifecycle transition is recorded in the audit trail.
- **Rule 8 (State Recovery Mandatory)**: Broker connectivity is restored autonomously from persistence.
- **Rule 9 (Trading Safety Overrides Convenience)**: Failed token decryption or expired tokens immediately halt broker operations.
