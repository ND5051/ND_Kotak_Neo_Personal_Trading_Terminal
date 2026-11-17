# Kotak Neo Personal Trading Terminal

A high-performance, single-operator personal algorithmic & discretionary trading terminal built on top of the **Kotak Neo Broker API** (`neo-api-client` v3.0.8+).

Designed for low latency, zero dummy data, defensive order execution, and real-time portfolio reconciliation.

---

## 🚀 Live Production Deployment

The terminal is deployed and active on Oracle Cloud Infrastructure (OCI):
* **Live Terminal URL**: [https://ndtradingterminaloci.nikhildeo.online/terminal](https://ndtradingterminaloci.nikhildeo.online/terminal)
* **Hosting**: OCI Ubuntu Ampere Compute (`141.148.223.101`)
* **Tunnel / DNS**: Cloudflare Zero Trust Tunnel
* **Process Manager**: `systemd` (`kotak-terminal.service`)
* **Reverse Proxy**: Nginx with WebSocket streaming (`/socket.io/`)

---

## 🛠️ Architecture & Core Subsystems

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Terminal Web UI (SPA)                          │
│   Light/Dark Themes · Silent Hotkeys · Real-Time Canvas / DOM Tables  │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ WebSocket / REST API
┌────────────────────────────────────▼───────────────────────────────────┐
│                          Flask / Gevent Backend                        │
├───────────────────┬───────────────────┬────────────────────────────────┤
│ Market Watch      │ Portfolio Engine  │ Order Management Engine        │
│ • Scrip Master    │ • Demat Holdings  │ • FSM Lifecycle & Reconciliation│
│ • Price Engine    │ • Positions (MTM) │ • Pre-flight Risk & Kill-Switch│
│ • Level-2 Depth   │ • Funds / Margins │ • Multi-Leg Basket DAG Engine  │
├───────────────────┴───────────────────┴────────────────────────────────┤
│                      Option Chain & Analytics Engine                   │
│ • 3 Core Indices (NIFTY, BANKNIFTY, SENSEX)                            │
│ • Search-as-you-type Combobox for all 224 F&O Equities                 │
│ • PCR (OI & Vol), Greeks (Black-Scholes), Quick Multi-Leg Baskets     │
├────────────────────────────────────────────────────────────────────────┤
│                      Kotak Neo Adapter Layer                           │
│ • neo-api-client v3.0.8+ · SFeed Binary/JSON WebSocket Stream         │
│ • Session Auto-Restore & AES-256 Token Encryption                     │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ Native API
                        ┌────────────▼───────────┐
                        │   Kotak Neo Brokerage  │
                        └────────────────────────┘
```

---

## 🖥️ Terminal Workspaces & Tabs

| Workspace | Description | Features |
|:---|:---|:---|
| **1. Market Watch** | Fast watchlist for equities and derivatives. | Real-time quotes, 5-level depth, scrip search modal, 1-click option chain bridge (`⛓️`). |
| **2. Orders** | Comprehensive Order Book & Audit Log. | Open, Executed, Cancelled, and Rejected tabs with real-time FSM order lifecycle timeline. |
| **3. Holdings** | CNC Delivery portfolio reconciled from Demat. | Realized cost, LTP, current valuation, Total P&L, Day P&L, and 1-click Add/Exit tickets. |
| **4. Positions** | Real-time Derivatives & Intraday trades. | Grouped by MIS/NRML, live tick MTM calculation, emergency "Square Off All", and Reverse position. |
| **5. Option Chain** | Professional options matrix & strategy builder. | NIFTY, BANKNIFTY, SENSEX quick chips + 224 F&O stocks, strike filters, PCR, and Strategy Builder. |
| **6. Baskets** | Multi-leg execution engine. | Atomic or sequential leg execution, hedge-benefit margin calculation, and execution report. |
| **7. Funds** | Real-time margin ledger. | Available cash, collateral, SPAN margin used, and margin utilization meter. |
| **8. System Health** | Low-level diagnostic dashboard. | WebSocket connectivity, heartbeat latency, rate limits, and Kotak session expiry countdown. |

---

## ⌨️ Silent Keyboard Shortcuts

Work smoothly across the terminal without reaching for your mouse:
* **`1` – `8`**: Instantly switch between the 8 navigation tabs.
* **`Alt + T`**: Toggle Theme (**Light** &harr; **Dark**).
* **`Alt + C`**: Toggle Compact Mode (**ON** &harr; **OFF**).
* **`/`** or **`Ctrl + K`**: Open Scrip Search Command Palette.
* **`Escape`**: Dismiss active modals and search popups.
* **`Shift + Escape`**: Emergency Kill-Switch &mdash; cancels all open orders instantly.

---

## 🎨 Themes & Design System

The terminal supports two fully responsive, high-contrast themes:
* **Light Theme** *(Default)*: Clean, professional palette inspired by the official Kotak Neo broker portal with optimal contrast, soft backgrounds, and crisp typography.
* **Dark Theme**: High-contrast, night-trading palette with deep charcoal surfaces and radiant status indicators.

---

## 💻 Local Development Setup

### 1. Prerequisites
* Python 3.10+ (Recommended: Python 3.11 / 3.12 / 3.14)
* Virtualenv

### 2. Installation
```powershell
# Clone the repository
git clone https://github.com/ND5051/ND_Kotak_Neo_Personal_Trading_Terminal.git
cd ND_Kotak_Neo_Personal_Trading_Terminal

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate # Linux / macOS

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the root directory:
```env
FLASK_ENV=development
SECRET_KEY=your-random-secret-key
DATABASE_URI=sqlite:///data/kotak_terminal.db

# Kotak Neo Credentials
KOTAK_API_KEY=your_kotak_neo_consumer_key
KOTAK_API_SECRET=your_kotak_neo_consumer_secret
KOTAK_MOBILE_NUMBER=your_registered_mobile
KOTAK_PASSWORD=your_password
KOTAK_MPIN=your_mpin
```

### 4. Running the Terminal
```powershell
python run.py
```
Open your browser at `http://127.0.0.1:5000/terminal`.

### 5. Running Integration & Unit Tests
```powershell
pytest tests/ -v
```

---

## 🔒 Security & Defensive Principles
1. **Zero Raw Market Orders**: All market orders are executed as marketable Limit orders with strict slippage limits.
2. **Double-Confirmation Modal**: Required for high-exposure trades (> ₹1,00,000) or emergency square-offs.
3. **Encrypted Session Tokens**: Kotak Neo tokens are AES-256 encrypted at rest in SQLite.
4. **Paper Trading Sandbox**: Dedicated simulation mode with zero financial risk to practice strategies.

---

## 📜 License
Personal Trading Terminal &copy; 2026 Nikhil Deo. All Rights Reserved.
