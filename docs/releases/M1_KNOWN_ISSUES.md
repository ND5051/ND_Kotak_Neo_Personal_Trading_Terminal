# Milestone M1 Known Issues & Technical Debt
## Outstanding Audit Findings & Carry-Forward Backlog

**Document Version:** 1.0.0  
**Milestone:** `M1_BASELINE`  
**Status:** Monitored / Deferred to Phase 4 Sprint  
**Target Milestone for Resolution:** Milestone M2 (Phase 4)  

---

## 1. Overview

Milestone M1 has been validated and accepted for production baseline creation. As documented in the Phase 3 Architecture Review and manual QA cycles, several non-blocking architectural enhancements and technical debt items were identified. These items do not compromise system security or baseline stability, but must be addressed during Phase 4 prior to live tick streaming and execution.

---

## 2. Phase 3 Audit Findings & Deferred Backlog

### Issue M1-01: Broker Circuit Breaker Not Implemented Yet
* **Severity:** Medium  
* **Category:** Reliability & Resilience  
* **Description:**  
  While `BrokerHealthService` detects when Kotak Neo returns connection errors or session timeouts, the system does not currently feature an automated, sliding-window **Circuit Breaker** (e.g. tripping after 3 consecutive failures within 30 seconds). Rapid API retries during severe broker outages could lead to rate-limit throttling by Kotak Neo.
* **Current Mitigation:**  
  Manual login retry via `/api/broker/login` with health check backoff.
* **Remediation Plan (Phase 4):**  
  Implement an explicit Circuit Breaker in `app/broker/services/broker_circuit_breaker.py` with states: `CLOSED` (normal), `OPEN` (fail-fast without network requests), and `HALF-OPEN` (probing single canary request).

---

### Issue M1-02: In-Memory Cache TTL Support Not Implemented Yet
* **Severity:** Low  
* **Category:** Cache Invalidation  
* **Description:**  
  `BrokerCache` stores discovered capabilities and session metadata in memory protected by `threading.RLock`. However, cache entries currently rely on manual clearing (`clear()`, `clear_session_meta()`) rather than automated time-to-live (TTL) expiration policies.
* **Current Mitigation:**  
  Cache is explicitly updated on every login, session restore, and logout event.
* **Remediation Plan (Phase 4):**  
  Add automatic timestamp comparison and configurable TTL (e.g. `CACHE_TTL_CAPABILITIES = 86400`, `CACHE_TTL_METADATA = 3600`) to evict stale metadata entries automatically.

---

### Issue M1-03: Capability Discovery Currently Uses Default Matrix
* **Severity:** Low  
* **Category:** Capability Introspection  
* **Description:**  
  `KotakBrokerAdapter.get_capabilities()` currently returns the declared `DEFAULT_CAPABILITIES` dictionary rather than making an upstream REST call to query Kotak's dynamic user-profile or segment permission endpoints (e.g. checking whether the trading account is authorized for MCX Commodity or Currency Derivatives).
* **Current Mitigation:**  
  The default capability catalog covers all standard retail segments (NSE Equity, BSE Equity, NFO Futures/Options) with order execution explicitly disabled.
* **Remediation Plan (Phase 4):**  
  Implement a dynamic capability discovery routine querying `NeoAPI.profile()` or user limits upon successful authentication to populate account-specific segment permissions.

---

### Issue M1-04: Single Active Broker Adapter Instance
* **Severity:** Informational  
* **Category:** Architecture Extensibility  
* **Description:**  
  The terminal routes in `app/broker/routes.py` instantiate a global `KotakBrokerAdapter()` instance. While `broker_sessions` supports multi-broker records conceptually, only Kotak Neo is registered.
* **Remediation Plan (Future Milestone):**  
  A broker adapter factory will be introduced when multi-broker routing or backup broker failover is scheduled.
