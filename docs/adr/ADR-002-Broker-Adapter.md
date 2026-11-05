# ADR-002: Broker Adapter Abstraction Pattern

## Status
Accepted

## Context
Third-party broker APIs (including Kotak Neo) frequently undergo SDK updates, payload restructuring, session model changes, and protocol shifts. Direct broker SDK calls scattered across Flask routes or UI controllers result in brittle code, untestable surfaces, and vendor lock-in.

## Decision
We enforce **Project Constitution Rule 1**: "No direct broker SDK calls outside Broker Adapter."
- All broker interactions must implement the `IBrokerAdapter` interface defined in `app/broker/interfaces/broker_interface.py`.
- Concrete adapters (`KotakNeoAdapter`, `PaperBrokerAdapter`, `MockBrokerAdapter`) encapsulate all SDK idiosyncrasies, token headers, error translation, and network retries.
- Upper domain layers (Order Engine, Risk Engine, UI Routes) only interact with `IBrokerAdapter` interfaces.

## Consequences
### Positive
- Strict isolation of third-party SDK dependencies.
- Ability to test all business logic, order rules, and UI views using deterministic mock adapters without executing real broker API calls.
- Easy adaptability if broker updates their API or if multi-broker capabilities are required in the future.

### Negative / Trade-offs
- Requires mapping domain request objects into broker-specific payloads and vice-versa.

## Compliance with Project Constitution
- **Correctness > Features**: Clear isolation prevents accidental bypass of order verification.
- **Auditability > Convenience**: Centralized adapter allows uniform wire logging of all broker requests and responses.

