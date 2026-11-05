# ADR-005: Request Tracing, Correlation IDs, and Secret Encryption

## Status
Accepted

## Context
In live trading architectures, tracking the lifecycle of an order from user intent to broker execution requires unbroken lineage. When discrepancies or state divergences occur, the operator must be able to correlate the HTTP request, audit log, order event, and broker response using a single trace identifier. Furthermore, future broker integration requires secure at-rest encryption for Kotak Neo session tokens and credentials.

## Decision
1. **Request & Correlation Tracing**:
   - `RequestContextMiddleware` intercepts every incoming HTTP request.
   - Preserves or issues `X-Request-ID` and `X-Correlation-ID`.
   - Propagates IDs into `RequestContext` and structured JSON logs.
   - Automatically enriches all `AuditLogger` entries with `correlation_id` and `request_id`.
2. **Security Headers**:
   - Injects `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `Referrer-Policy: strict-origin-when-cross-origin` on all responses.
3. **Secret Encryption**:
   - Implements `EncryptionService` utilizing Fernet (AES-128-CBC + HMAC-SHA256) keyed by `SECRET_KEY` or `ENCRYPTION_KEY` to secure credentials and broker tokens before persistent storage.

## Consequences
### Positive
- End-to-end auditability across the entire software stack.
- Cryptographic isolation for sensitive broker tokens and user data.
- Enhanced browser security postures against clickjacking and MIME-sniffing.

### Negative / Trade-offs
- Slight overhead for encryption/decryption operations; minimal for financial transaction volumes.

## Compliance with Project Constitution
- **Auditability > Convenience**: Enforces traceability across every state change.
- **Reliability > Speed**: Correlation IDs enable rapid diagnostic post-mortems after operational anomalies.
