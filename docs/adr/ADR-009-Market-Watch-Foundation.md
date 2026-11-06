# ADR-009: Market Watch Foundation & Real-Time Price Engine

## Status
Accepted

## Context
Following the completion of Phase 4 (WebSocket Supervisor & Streaming Foundation), the terminal required a persistent, user-customizable market watch to organize instruments, index scrips, and receive live touchline prices. All trading functionality (orders, positions, holdings, option chains) remains strictly prohibited until future phases.

## Decision
1. Implement in-memory Trie and multi-index Scrip Master repository enabling sub-millisecond search across tokens, trading symbols, and names without disk bottlenecks.
2. Establish relational `watchlists` and `watchlist_items` tables managed via Alembic revision `e5f7a1b2c3d4` with foreign key CASCADE deletion.
3. Dynamically bind watchlist additions and removals to Phase 4's `SubscriptionManager` so wire subscriptions are registered and dereferenced automatically.
4. Build `MarketWatchPriceEngine` to ingest SFeed touchlines, scale integer paise prices by segment dividers, normalize spot index frames, and maintain a thread-safe quote cache.
5. Enforce hard quotas: maximum 10 watchlists per user, maximum 50 scrips per watchlist.
6. Provide automatic self-healing `Default Watchlist` with benchmark scrips on user first access.

## Consequences
- Fast symbol lookup and autocomplete (< 2ms) without hitting database storage.
- Real-time touchline quotes are available in-memory for instant REST snapshot reads.
- Subscription lifecycle is fully synchronized with user watchlist state.
- Strictly maintains zero order execution, holdings, positions, or option chain risk.
