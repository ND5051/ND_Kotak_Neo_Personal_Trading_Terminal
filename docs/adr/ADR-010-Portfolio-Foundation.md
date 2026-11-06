# ADR-010: Portfolio Foundation & Real-Time MTM Engine

## Status
Accepted

## Context
Following the completion of Phase 5 (Market Watch Foundation), the terminal requires portfolio tracking capabilities: Demat holdings custody, day/net open positions, cash and collateral margin utilization, portfolio valuation, and live Mark-to-Market (MTM) calculations. All order execution, order management, basket orders, and option chains remain strictly prohibited until future phases.

## Decision
1. **Pure Broker-Authoritative Model:** Do not create local database tables for holdings, positions, or margins. Authoritative custody resides strictly on the broker gateway; local persistence introduces split-brain hazards when trades occur out-of-band via broker mobile or web apps.
2. **Dual-Timestamp Protocol:** Mandate `source_timestamp` (exchange/broker timestamp) and `retrieved_timestamp` (local ingest UTC ISO 8601) across all portfolio domain dataclasses (`Holding`, `Position`, `MarginSummary`, `PortfolioSummary`).
3. **The Golden Rule of State Reconciliation:** "Absence of data != value zero." When reconciling positions or checking specific symbols, if the broker response omits a symbol or returns an empty/unreachable payload, treat position status as `None` (Unknown/Undetermined), NEVER `0`. This prevents algorithmic systems from falsely concluding a position was closed out-of-band and dropping protective stop-loss orders.
4. **Polymorphic Response Extraction:** Implement robust payload normalizers (`_extract_records`) to seamlessly unpack disparate Kotak Neo response formats (`list[dict]`, `{"data": [...]}`, `{"result": [...]}`, `{"dataList": [...]}`).
5. **Real-Time In-Memory MTM Engine:** Wire active open positions to Phase 5's `MarketWatchPriceEngine` touchline cache. Compute live unrealized floating MTM dynamically ($Net \times (LTP - BuyAvg)$ for longs, $|Net| \times (SellAvg - LTP)$ for shorts, and $0.0$ for closed positions) without issuing repetitive REST requests to the broker.
6. **Multi-Tier TTL Caching & Cache Invalidation:** Leverage Phase 4's `BrokerCache` with partitioned TTLs (`TTL_HOLDINGS = 300s`, `TTL_POSITIONS = 5s`, `TTL_MARGINS = 10s`) and provide explicit force-refresh endpoints (`POST /api/portfolio/refresh`) to purge stale caches.

## Consequences
- Zero risk of split-brain state desynchronization with broker custody.
- Complete auditability and freshness verification through dual timestamps.
- Maximum resilience against false position closure assumptions during network interruptions.
- Sub-millisecond MTM recalculation upon touchline ticks via Phase 5 price engine integration.
- Strict compliance: absolutely no order execution, basket orders, or option chains implemented.
