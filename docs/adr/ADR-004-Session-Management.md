# ADR-004: Token-Based Session Management & Sliding Expiration

## Status
Accepted

## Context
A browser-based trading terminal requires robust session isolation. Traditional server-side cookie sessions can introduce CSRF vulnerabilities or impede decoupling when transitioning to native or mobile companion apps. Furthermore, high-value financial execution demands predictable session timeouts, remote session revocation, and multi-session control.

## Decision
We implement a database-backed, cryptographically random token-based **Session Framework**:
- `Session` entity stored in SQLite (`sessions` table) with indexed `session_id`, `user_id`, `expires_at`, `last_activity`, and `is_active` status.
- Tokens are 32-byte URL-safe cryptographic strings (`secrets.token_urlsafe(32)`).
- Session authorization accepts tokens via `Authorization: Bearer <token>`, `X-Session-ID` header, or HTTP-only cookies.
- Sessions employ sliding-window activity touch on valid requests and are immediately deactivated upon logout, password change, or administrative account disablement.

## Consequences
### Positive
- Strict auditability: Every session is explicitly tracked and can be revoked individually or in bulk.
- Resilient to CSRF when invoked via Authorization header from client state.
- Ready for future multi-factor and Kotak Neo session pairing.

### Negative / Trade-offs
- Requires database lookup per protected request.
- Mitigated by indexed primary/unique constraints and lightweight in-memory caching in future scaling phases.

## Compliance with Project Constitution
- **Auditability > Convenience**: Every session creation, touch, and expiration is logged in the audit trail.
- **Trading Safety Overrides Convenience**: Inactive sessions expire automatically, reducing unauthorized order execution risks.
