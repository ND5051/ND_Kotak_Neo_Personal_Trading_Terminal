# Kotak Neo Personal Trading Terminal — Documentation Index

Welcome to the central documentation repository for the **Kotak Neo Personal Trading Terminal**. All technical design documents, architectural decision records, release baselines, testing protocols, and operational diagnostics are cataloged here.

---

## 📌 Core Project Governance & Active State

* **[OCI_DEPLOYMENT_RUNBOOK.md](OCI_DEPLOYMENT_RUNBOOK.md)** — **Production Cloud Deployment Guide**: Step-by-step runbook for OCI Ubuntu compute, systemd, Nginx, WebSocket proxying, Cloudflare Tunnel, and automated backups.
* **[OCI_PRE_DEPLOYMENT_CHECKLIST.md](OCI_PRE_DEPLOYMENT_CHECKLIST.md)** — **Pre-Flight Deployment Checklist**: Comprehensive 10-step gate covering GitHub migration, secrets removal, M7 tag, OCI server readiness, smoke testing, and rollback.
* **[PROJECT_CURRENT_STATE.md](PROJECT_CURRENT_STATE.md)** — **Latest Runtime Health & Audit Report**: Concrete verification status of all 9 core subsystems, active streaming diagnostics, and production readiness.
* **[PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)** — Non-negotiable architectural invariants: Human-Initiated Trading, Defensive Execution (no raw market orders), The Golden Rule of Reconciliation, and Zero Dummy Data.
* **[PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)** — High-level introduction to the terminal cockpit, tech stack, and milestone roadmap.
* **[architecture_decisions.md](architecture_decisions.md)** — Summary register and index of all Architecture Decision Records.
* **[broker_findings.md](broker_findings.md)** — Kotak Neo API idiosyncratic behaviors, rate limits, session constraints, and integration insights.
* **[known_issues.md](known_issues.md)** — Active and resolved issues, limitations, and defensive mitigations.
* **[lessons_learned.md](lessons_learned.md)** — Operational retrospectives and engineering lessons from live testing.

---

## 📂 Documentation Subdirectories

### 1. [testing/](testing/) — Testing, Simulation Audits & UAT
* **[LIVE_UAT_CHECKLIST.md](testing/LIVE_UAT_CHECKLIST.md)** — **Master Live UAT Checklist & Sign-Off Matrix** (Phases 1 through 8).
* **[PAPER_EXECUTION_AUDIT.md](testing/PAPER_EXECUTION_AUDIT.md)** — Simulated execution audit and risk compliance verification.
* **[PAPER_MODE_KILL_SWITCH_GUIDANCE.md](testing/PAPER_MODE_KILL_SWITCH_GUIDANCE.md)** — Emergency panic cancellation drill protocols.
* **[MILESTONE_M1_VALIDATION.md](testing/MILESTONE_M1_VALIDATION.md)** — Baseline verification tests for Milestone M1.

### 2. [specs/](specs/) — Phase Design Specifications
Detailed engineering blueprints and domain schemas for all implemented phases:
* Phase 4: SFeed Streaming Architecture
* Phase 5: Market Watch & In-Memory Price Engine
* Phase 6: Portfolio & Mark-to-Market Engine
* Phase 7 & 8: Order Management & FSM State Lifecycle
* Phase 9: Multi-Leg Basket Engine & DAG Orchestrator
* Phase 10: Option Chain Workbench & Liquidity Metrics
* Phase 11 & 12: Production Hardening, Circuit Breakers & Live Execution

### 3. [reviews/](reviews/) — Phase Architecture Reviews & Retrospectives
Formal sign-off reviews and architectural audits across Phase 1 through Phase 12B, capturing codebase compliance with the project constitution before each major release.

### 4. [releases/](releases/) — Milestones & Release Packages
* Release packages from Milestone M1 through Milestone M6 (`M1_RELEASE_NOTES.md`, `M2_RELEASE_PACKAGE.md` ... `M6_RELEASE_PACKAGE.md`).
* Rollback procedures, release baselines, and milestone transition plans (`NEXT_PHASE.md`).

### 5. [diagnostics/](diagnostics/) — Technical Investigations & Fix Reviews
Deep-dive post-mortems and technical root-cause analyses:
* Broker client sharing & session synchronization (`CLIENT_WIRING_ROOT_CAUSE.md`, `LIVE_EXECUTION_WIRING_FIX_REVIEW.md`)
* Kotak Neo SDK v3 compatibility & environment loading (`KOTAK_SDK_COMPATIBILITY_FIX_REVIEW.md`, `ENV_LOADING_DIAGNOSTIC.md`)
* Option chain live market data, expiries & tick scalers (`LIVE_MARKET_DATA_DIAGNOSTIC.md`, `MARKET_DATA_PIPELINE_FIX_REVIEW.md`)
* Terminal entrypoints, auth, and routing remediations (`TERMINAL_AUTH_FIX_REVIEW.md`, `TERMINAL_ENTRYPOINT_REMEDIATION.md`)

### 6. [adr/](adr/) — Architecture Decision Records (ADRs)
Immutable architectural records detailing technical choices, tradeoffs, and rationale:
* **ADR-001:** SQLite Embedded Database Choice
* **ADR-002:** Broker Gateway & Interface Decoupling
* **ADR-003:** Paper Mode Simulation Invariant
* **ADR-004:** Two-Tier Operator Session Management
* **ADR-005:** Dual Audit Logging & Correlation Tracing
* **ADR-006:** Encrypted Broker Token Persistence
* **ADR-007:** Kotak Neo Trade API Integration
* **ADR-008:** SFeed WebSocket Supervisor & Circuit Breaker
* **ADR-009:** Market Watch & Price Engine Cache
* **ADR-010:** Real-Time Portfolio & MTM Architecture
* **ADR-011:** Order Domain Model & Auditable Timestamps
* **ADR-012:** Defensive Order Execution & Pre-Flight Risk Engine
* **ADR-013:** Advanced Order Types & Multi-Leg Basket DAG Engine
