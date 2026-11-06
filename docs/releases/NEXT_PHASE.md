# Phase 4 Planning — Market Data & Real-Time Streaming Foundation
## Next Phase Scoping & Architectural Roadmap

**Document Version:** 1.0.0  
**Target Phase:** Phase 4  
**Target Milestone:** Milestone M2  
**Precondition:** Milestone M1 Baseline Locked & Tagged (`M1_BASELINE`)  

---

## 1. Phase 4 Objective

The primary objective of Phase 4 is to establish reliable, high-throughput, low-latency market data feeds and real-time WebSocket tick streaming (`SFeed`) from Kotak Neo, and propagate real-time ticker updates to the frontend via Flask-SocketIO.

---

## 2. Phase 4 Scope

During Phase 4, the system will implement:

1. **Kotak Neo SFeed WebSocket Streaming**:
   - Establish live binary WebSocket connection to Kotak Neo streaming servers.
   - Parse binary tick buffers (LTP, best bid/ask, day volume, open, high, low, close, open interest).
   - Manage connection heartbeat, ping/pong cycles, and automatic exponential-backoff reconnects.
2. **Market Data Service (`app/services/market_data_service/`)**:
   - Manage instrument subscription registry (subscribing/unsubscribing tokens).
   - Cache latest market ticks in memory with sub-millisecond access.
   - Maintain instrument master mapping (symbol <-> token <-> exchange segment).
3. **Frontend WebSocket Broadcast (`app/websocket/`)**:
   - Socket.IO gateway broadcasting parsed market data rooms to connected terminal browser clients.
   - Client subscription management for custom watchlists.
4. **Mandatory Carry-Forward Items from Phase 3 Audit**:
   - **Broker Circuit Breaker (`BrokerCircuitBreaker`)**: Implement 3-state sliding-window breaker (`CLOSED`, `OPEN`, `HALF-OPEN`) to prevent hammering Kotak REST/WebSocket endpoints during outages.
   - **Cache TTL Support**: Implement time-to-live expiration policies on `BrokerCache` items.
   - **Capability Refresh Framework**: Implement dynamic user account profile inspection (`NeoAPI.profile()` / `limits()`) to discover actual authorized segments rather than static defaults.

---

## 3. Phase 4 Non-Scope

The following capabilities remain **strictly prohibited** in Phase 4:

1. **No Order Placement**: No live orders, market orders, limit orders, or bracket orders.
2. **No Order Modification / Cancellation**: Zero order management methods on adapters or routes.
3. **No Portfolio / Positions Execution**: No account trade history execution, squaring off, or position adjustments.
4. **No Automated Strategy Execution**: No algorithmic scanners or automatic order triggers.
5. **No Paper Trading Execution**: Paper trading engine will be integrated in Phase 8 after live feeds and order engines are architecturally verified.

---

## 4. Phase 4 Carry-Forward Matrix

| Carry-Forward Item | Origin | Priority | Implementation Target in Phase 4 |
|---|---|---|---|
| **Broker Circuit Breaker** | Phase 3 Audit | **High** | `app/broker/services/broker_circuit_breaker.py` |
| **Cache TTL Support** | Phase 3 Audit | **Medium** | `app/broker/cache/broker_cache.py` |
| **Dynamic Capability Refresh** | Phase 3 Audit | **Medium** | `KotakBrokerAdapter.get_capabilities()` |
| **Instrument Master Scaffolding** | Phase 3 Audit | **High** | `app/services/market_data_service/instrument_manager.py` |
| **SFeed Binary Protocol Parser** | Architecture | **Critical** | `app/broker/adapters/kotak_streamer.py` |

---

*Awaiting formal authorization before commencing Phase 4 implementation.*

