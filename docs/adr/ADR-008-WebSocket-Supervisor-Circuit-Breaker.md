# ADR-008: Real-Time WebSocket Supervisor, Circuit Breaker & Telemetry Foundation

## Status
Accepted

## Context
In Phase 3, broker connectivity, authentication, and session recovery were established. However, the Phase 3 architecture audit identified two critical resilience gaps:
1. Absence of a Broker Circuit Breaker to prevent cascading failures during API outages.
2. Indefinite in-memory cache lifetimes without TTL boundaries.
Furthermore, real-time binary streaming (SFeed WebSocket) requires an asynchronous runtime operating concurrently with Flask's synchronous WSGI model, while strictly prohibiting tick rendering, market watch widgets, or order placement.

## Decision
1. Establish `WebSocketSupervisor` on a dedicated daemon thread running a self-managed `asyncio` event loop.
2. Implement a formal 5-State Machine (`DISCONNECTED`, `CONNECTING`, `CONNECTED`, `RECONNECTING`, `FAILED`) driven by exponential backoff with random jitter.
3. Implement `BrokerCircuitBreaker` (3 states: `CLOSED`, `OPEN`, `HALF_OPEN`) with a 5-failure threshold and a 30s cooldown with exponential penalty doubling up to 120s on canary failure.
4. Implement `SubscriptionManager` with reference counting ($0 \to 1$ wire subscribe, $1 \to 0$ wire unsubscribe), a 3,000-instrument quota cap, and 500-token sliced batching.
5. Upgrade `BrokerCache` to envelope-based TTL storage with lazy on-read expiration and an active `purge_expired()` sweeper.
6. Implement `WebSocketTelemetryTracker` tracking 5 discrete metrics including Cumulative Moving Average (CMA) reconnect duration.

## Consequences
- The Flask process can cleanly manage long-lived WebSockets without blocking request threads.
- Network anomalies are isolated by the circuit breaker without overloading the broker.
- Memory consumption is capped and deterministic.
- Downstream phases (Phase 5: Market Watch) can subscribe to instruments through `SubscriptionManager` without redesigning socket infrastructure.
