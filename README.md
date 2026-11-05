# Kotak Neo Personal Trading Terminal

A personal, browser-based algorithmic and discretionary trading cockpit for the Kotak Neo broker platform.

> **Current Phase**: Phase 1 — Project Skeleton & Architectural Foundation  
> **Status**: COMPLETED &bull; Zero Trading Operations Active

---

## Architectural Principles (Non-Negotiable)

```
Correctness       > Features
Reliability       > Speed
Recovery          > Elegance
Auditability      > Convenience
State Consistency > Performance
```

For full governance tenets and rules, refer to [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md).

---

## Technology Stack

- **Backend**: Python 3.14, Flask, Flask-SocketIO, SQLAlchemy 2.0, Alembic, SQLite
- **Frontend**: Clean HTML5, Modern CSS (Dark Theme), Vanilla JavaScript (Socket.IO client)
- **Quality & Testing**: Pytest, Structured JSON Logging, Thread-safe EventBus

---

## Quickstart

### 1. Environment Setup
```bash
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies (already pinned in requirements.txt)
pip install -r requirements.txt
```

### 2. Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 3. Run Tests
```bash
pytest -v
```

### 4. Start the Terminal Foundation
```bash
python run.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## Directory Layout
```
ND_Kotak_Neo_Personal_Trading_Terminal/
├── app/
│   ├── auth/                     # Authentication blueprint skeleton
│   ├── dashboard/                # Main dashboard UI & system health
│   ├── market_watch/             # Watchlist endpoints skeleton
│   ├── orders/                   # Order book endpoints skeleton
│   ├── basket/                   # Multi-leg basket endpoints skeleton
│   ├── positions/                # Positions endpoints skeleton
│   ├── holdings/                 # Long-term holdings endpoints skeleton
│   ├── option_chain/             # Option chain endpoints skeleton
│   ├── settings/                 # Settings & Feature flags endpoints
│   ├── paper_trading/            # Paper trading module skeleton
│   ├── broker/
│   │   ├── adapters/             # BaseBrokerAdapter implementation
│   │   ├── interfaces/           # IBrokerAdapter interface contract
│   │   └── cache/                # Instrument & session cache package
│   ├── services/                 # Business domain service skeletons
│   ├── websocket/                # SocketManager & WebSocket lifecycle
│   ├── risk/                     # RiskEngine skeleton
│   ├── events/                   # Thread-safe EventBus & event types
│   ├── repositories/             # BaseRepository & domain repository skeletons
│   ├── models/                   # BaseModel & SQLAlchemy db initialization
│   ├── logging/                  # Structured JSON logger & rotating handlers
│   ├── middleware/               # Global error handlers & request tracer
│   └── core/                     # Exceptions, feature flags, audit logger
├── tests/
│   ├── unit/                     # Unit test suite
│   ├── integration/              # Integration test suite
│   └── system/                   # End-to-end system test suite
├── docs/
│   ├── adr/                      # Architecture Decision Records (ADR 001 - 003)
│   ├── lessons_learned.md        # Architectural insights per phase
│   ├── known_issues.md           # Tracked issues & workarounds
│   ├── broker_findings.md        # Kotak Neo API idiosyncrasies
│   └── architecture_decisions.md # Index of architectural decisions
├── migrations/                   # Alembic database migration environment
├── static/                       # Dark theme CSS and frontend scripts
├── templates/                    # Jinja2 HTML templates
├── config/                       # Base, Dev, Test, Prod configuration classes
├── requirements.txt              # Pinned project dependencies
├── PROJECT_CONSTITUTION.md       # 10 core non-negotiable architectural rules
└── run.py                        # Application entry point
```

