# ADR-003: Unified Architecture for Paper and Live Trading

## Status
Accepted

## Context
Many trading platforms treat paper trading as a separate mock system or build a secondary set of services. This produces drift between simulated execution and real market execution, leading to live bugs and false confidence in strategies.

## Decision
We enforce **Project Constitution Rule 10**: "Paper and Live trading must share architecture."
- Paper trading will utilize the exact same Order Engine, Risk Validation, State Reconciliation, Event Bus, and Frontend UI components as Live Trading.
- The only variation is the active adapter injected into the Order Engine:
  - In Live Mode: `KotakNeoAdapter`
  - In Paper Mode: `PaperBrokerAdapter` (which simulates fills against live or simulated market ticks)
- Feature flag `PAPER_TRADING` controls whether simulated execution is permitted and selectable.

## Consequences
### Positive
- Zero divergence between paper testing workflows and live production execution.
- High confidence that code verified in simulation executes reliably with live capital.

### Negative / Trade-offs
- Simulation adapter must realistically simulate order states (PENDING, TRADED, REJECTED, CANCELLED) and partial fills.

## Compliance with Project Constitution
- **State Consistency > Performance**: Guarantees identical order lifecycle state transitions across both modes.
- **Reliability > Speed**: Verifies the entire production pipeline under realistic operational constraints.

