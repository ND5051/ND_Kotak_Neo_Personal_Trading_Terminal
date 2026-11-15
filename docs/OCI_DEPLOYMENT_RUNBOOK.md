# OCI Cloud Deployment Runbook
**Kotak Neo Personal Trading Terminal**  
**Target Environment:** Oracle Cloud Infrastructure (OCI) Compute &bull; Ubuntu 22.04 / 24.04 LTS  
**Document Version:** 1.0.0  
**Last Updated:** 2026-11-15  
**Classification:** Operational Runbook & Production Deployment Standard  

---

## Table of Contents
1. [Architecture & Topology Overview](#1-architecture--topology-overview)
2. [Step 1: GitHub Migration & Source Preparation](#step-1-github-migration--source-preparation)
3. [Step 2: OCI Compute Instance Provisioning & Ubuntu Setup](#step-2-oci-compute-instance-provisioning--ubuntu-setup)
4. [Step 3: Python Application & Dependency Installation](#step-3-python-application--dependency-installation)
5. [Step 4: Environment Variables & Secret Key Management](#step-4-environment-variables--secret-key-management)
6. [Step 5: SQLite Database Deployment & WAL Mode Configuration](#step-5-sqlite-database-deployment--wal-mode-configuration)
7. [Step 6: Systemd Daemon Service Configuration](#step-6-systemd-daemon-service-configuration)
8. [Step 7: Nginx Reverse Proxy & WebSocket Configuration](#step-7-nginx-reverse-proxy--websocket-configuration)
9. [Step 8: Cloudflare Tunnel Deployment (Zero-Trust Option)](#step-8-cloudflare-tunnel-deployment-zero-trust-option)
10. [Step 9: Automated Backup & Retention Strategy](#step-9-automated-backup--retention-strategy)
11. [Step 10: Post-Deployment Smoke Test Checklist](#step-10-post-deployment-smoke-test-checklist)
12. [Step 11: Live Production Trading Prerequisites](#step-11-live-production-trading-prerequisites)
13. [Step 12: Emergency Disaster Recovery & Rollback Procedure](#step-12-emergency-disaster-recovery--rollback-procedure)

---

## 1. Architecture & Topology Overview

```
                      +---------------------------------------+
                      |       Operator Browser / Mobile       |
                      +---------------------------------------+
                                          |
                      (HTTPS / WSS via Cloudflare / Let's Encrypt)
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| OCI Ubuntu 22.04 LTS Instance (VM.Standard.A1.Flex or VM.Standard.E2.1.Micro)    |
|                                                                                   |
|   +---------------------------------------------------------------------------+   |
|   |                         Nginx Reverse Proxy                               |   |
|   |         (SSL Termination, Static Assets, WebSocket Upgrade Proxy)         |   |
|   +---------------------------------------------------------------------------+   |
|                                     | (Unix Socket / 127.0.0.1:5000)              |
|                                     v                                             |
|   +---------------------------------------------------------------------------+   |
|   |                   systemd: kotak-terminal.service                         |   |
|   |         Flask-SocketIO + Async Worker (Dedicated 'trading' user)          |   |
|   +---------------------------------------------------------------------------+   |
|              |                             |                           |          |
|              v                             v                           v          |
|   +---------------------+       +--------------------+       +----------------+   |
|   |  SQLite 3 Engine    |       | PriceEngine Cache  |       | WebSocketSup.  |   |
|   |  (WAL Mode / Data)  |       | (In-Memory L1)     |       | (SFeed Stream) |   |
|   +---------------------+       +--------------------+       +----------------+   |
|              |                                                         |          |
+--------------|---------------------------------------------------------|----------+
               | (Automated Cron Live Backup)                            | (mTLS / WSS)
               v                                                         v
    +--------------------+                                    +---------------------+
    | OCI Object Storage |                                    | Kotak Neo Gateways  |
    | (Encrypted Vault)  |                                    | (REST APIs + SFeed) |
    +--------------------+                                    +---------------------+
```

---

## Step 1: GitHub Migration & Source Preparation

Execute these steps on your local development machine to push the codebase to a secure private repository.

### 1.1 Verify `.gitignore` Safeguards
Ensure that `.env`, SQLite databases (`*.db`), virtual environments, and log files are strictly excluded before staging.

```powershell
# Verify .gitignore contains these critical exclusions
Get-Content .gitignore | Select-String -Pattern "^\.env$|\.db$|data/|logs/|\.venv/"
```

### 1.2 Initialize Git & Create Private GitHub Repository
```bash
# Initialize local repo (if not already initialized)
git init

# Stage all project files (safe under .gitignore)
git add .

# Verify no secrets or databases are staged
git status

# Commit
git commit -m "feat: complete Phase 12B production hardening & clean documentation hierarchy"

# Create a private GitHub repository via GitHub CLI
gh repo create ND_Kotak_Neo_Personal_Trading_Terminal --private --source=. --remote=origin --push

# Or add your manual remote and push
# git remote add origin git@github.com:<YOUR_USER>/ND_Kotak_Neo_Personal_Trading_Terminal.git
# git branch -M main
# git push -u origin main
```

---

## Step 2: OCI Compute Instance Provisioning & Ubuntu Setup

### 2.1 Recommended Instance Profile
* **Compartment:** Your dedicated trading compartment.
* **Shape:** 
  * *Option A (Always Free Ampere ARM):* `VM.Standard.A1.Flex` (2 OCPU, 12 GB RAM) &bull; *Recommended for lowest latency & zero cost*.
  * *Option B (Always Free AMD x86):* `VM.Standard.E2.1.Micro` (1 OCPU, 1 GB RAM &bull; requires 2GB Swap).
* **OS Image:** Canonical Ubuntu 22.04 LTS Minimal or Standard (64-bit).
* **Storage:** 50 GB Boot Volume (Balanced performance).

### 2.2 OCI VCN Ingress Security List
Configure your Virtual Cloud Network (VCN) Ingress Rules under **Security Lists**:

| Source CIDR | IP Protocol | Source Port | Destination Port | Purpose |
| :--- | :---: | :---: | :---: | :--- |
| `0.0.0.0/0` (or your static IP) | TCP | All | `22` | SSH Administration |
| `0.0.0.0/0` | TCP | All | `80` | HTTP (Certbot & Nginx) |
| `0.0.0.0/0` | TCP | All | `443` | HTTPS / WSS (Trading UI) |

> [!IMPORTANT]
> If using **Cloudflare Tunnel** (Step 8), you do **not** need to open ports 80 or 443 in the OCI Security List. Only port 22 (restricted to your IP) is needed.

### 2.3 Host OS Preparation (SSH onto the OCI Instance)
Connect via SSH to your OCI instance and run the initial setup:

```bash
# Connect as ubuntu user
ssh -i ~/.ssh/id_rsa_oci ubuntu@<OCI_INSTANCE_PUBLIC_IP>

# Update package repositories and system packages
sudo apt update && sudo apt upgrade -y

# Install essential development, compilation, and networking utilities
sudo apt install -y build-essential python3-dev python3-pip python3-venv \
    libffi-dev libssl-dev sqlite3 curl git htop fail2ban ufw chrony

# Set Timezone strictly to Asia/Kolkata (Essential for Indian Exchange Timestamps)
sudo timedatectl set-timezone Asia/Kolkata
timedatectl

# Configure Chrony for Ultra-Low NTP Drift (Exchange order audit compliance)
sudo systemctl enable --now chrony
chronyc tracking
```

### 2.4 Configure Swap Space (Crucial for 1GB Micro Instances)
```bash
# Allocate 4GB Swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make swap persistent across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 2.5 Fix OCI Ubuntu Default iptables
> [!WARNING]
> OCI Ubuntu images include default `iptables` rules that reject inbound HTTP/HTTPS traffic even if permitted by OCI Security Lists. Run:

```bash
# Allow HTTP and HTTPS through host firewall
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

---

## Step 3: Python Application & Dependency Installation

### 3.1 Create Dedicated System User
Never run financial trading applications as `root` or `ubuntu`.

```bash
# Create isolated trading user
sudo useradd -m -s /bin/bash trading

# Setup application directory
sudo mkdir -p /opt/kotak_terminal
sudo chown -R trading:trading /opt/kotak_terminal
```

### 3.2 Setup Deploy Keys & Clone Repository
```bash
# Switch to trading user
sudo -u trading -i

# Generate dedicated SSH deploy key
ssh-keygen -t ed25519 -C "oci-trading-terminal" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```
*Copy the public key and add it to your GitHub Repo: **Settings &rarr; Deploy keys &rarr; Add deploy key (Read-only)**.*

```bash
# Clone the repository
cd /opt/kotak_terminal
git clone git@github.com:<YOUR_USER>/ND_Kotak_Neo_Personal_Trading_Terminal.git .

# Create the isolated Python 3 virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade packaging tools and install production dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install gevent-websocket gunicorn

# Exit back to ubuntu sudo user
exit
```

---

## Step 4: Environment Variables & Secret Key Management

### 4.1 Generate Production Cryptographic Keys
Run this one-liner to generate production-grade keys:

```bash
python3 -c "
import secrets
from cryptography.fernet import Fernet
print('SECRET_KEY=' + secrets.token_hex(32))
print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())
"
```

### 4.2 Populate `/opt/kotak_terminal/.env`
Create the production environment file:

```bash
sudo -u trading nano /opt/kotak_terminal/.env
```

Paste and customize your credentials:

```dotenv
# ==============================================================================
# KOTAK NEO PERSONAL TRADING TERMINAL — PRODUCTION CONFIGURATION
# ==============================================================================

# Core System
APP_ENV=production
DEBUG=false
SECRET_KEY=<PASTE_GENERATED_SECRET_KEY>
ENCRYPTION_KEY=<PASTE_GENERATED_FERNET_KEY>
DATABASE_URL=sqlite:////opt/kotak_terminal/data/kotak_terminal.db
LOG_LEVEL=INFO
LOG_DIR=/opt/kotak_terminal/logs
NEO_LOG_FILE_ENABLED=false

# Broker Engine
KOTAK_BROKER_ENABLED=true
BROKER_SESSION_TIMEOUT=28800
BROKER_HEALTH_INTERVAL=60

# Kotak Neo API Credentials (Encrypted at rest via AES-256 Fernet)
NEO_CONSUMER_KEY=<YOUR_KOTAK_NEO_CONSUMER_KEY>
NEO_CONSUMER_SECRET=<YOUR_KOTAK_NEO_CONSUMER_SECRET>
NEO_MOBILE_NUMBER=+91<YOUR_REGISTERED_MOBILE>
NEO_UCC=<YOUR_KOTAK_UCC_ID>
NEO_MPIN=<YOUR_6_DIGIT_MPIN>
NEO_TOTP_SECRET=<YOUR_TOTP_BASE32_SECRET>

# Feature Flags
FEATURE_PAPER_TRADING=true
FEATURE_GTT=false
FEATURE_SCANNER_ENGINE=false
FEATURE_STRATEGY_ENGINE=false
FEATURE_NOTIFICATIONS=false

# Network Binding
HOST=127.0.0.1
PORT=5000
```

### 4.3 Restrict File Permissions
```bash
# Secure .env strictly to the trading user (Read/Write owner only)
sudo chown trading:trading /opt/kotak_terminal/.env
sudo chmod 600 /opt/kotak_terminal/.env
```

---

## Step 5: SQLite Database Deployment & WAL Mode Configuration

### 5.1 Initialize Directories & Database
```bash
sudo -u trading mkdir -p /opt/kotak_terminal/data /opt/kotak_terminal/logs

# Initialize DB schema via Alembic / Python Factory
sudo -u trading bash -c "cd /opt/kotak_terminal && source .venv/bin/activate && python3 -c 'from app.models.db import init_db; init_db()'"
```

### 5.2 Enforce High-Concurrency Write-Ahead Logging (WAL)
Apply production SQLite performance pragmas:

```bash
sudo -u trading sqlite3 /opt/kotak_terminal/data/kotak_terminal.db << 'EOF'
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;
PRAGMA busy_timeout = 5000;
EOF
```

---

## Step 6: Systemd Daemon Service Configuration

Create the system service unit to manage the application process lifecycle.

```bash
sudo nano /etc/systemd/system/kotak-terminal.service
```

Paste the following service configuration:

```ini
[Unit]
Description=Kotak Neo Personal Trading Terminal
After=network.target network-online.target time-sync.target
Wants=network-online.target time-sync.target

[Service]
Type=simple
User=trading
Group=trading
WorkingDirectory=/opt/kotak_terminal
EnvironmentFile=/opt/kotak_terminal/.env
ExecStart=/opt/kotak_terminal/.venv/bin/python run.py

# Defensive Resilience & Auto-Restart
Restart=always
RestartSec=5s
TimeoutStopSec=15s

# Hardening & Security Limits
LimitNOFILE=65535
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=/opt/kotak_terminal/data /opt/kotak_terminal/logs

# Standard Output / Logging to Journald
StandardOutput=journal
StandardError=journal
SyslogIdentifier=kotak-terminal

[Install]
WantedBy=multi-user.target
```

### 6.1 Enable and Start the Service
```bash
# Reload systemd daemon
sudo systemctl daemon-reload

# Enable service to launch on boot
sudo systemctl enable kotak-terminal

# Start service
sudo systemctl start kotak-terminal

# Check status
sudo systemctl status kotak-terminal
```

---

## Step 7: Nginx Reverse Proxy & WebSocket Configuration

### 7.1 Install Nginx & Certbot
```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 7.2 Configure Nginx Server Block
```bash
sudo nano /etc/nginx/sites-available/kotak-terminal
```

Paste the configuration (replace `your-domain.com` with your domain or dynamic DNS):

```nginx
# Upstream application cluster
upstream kotak_app {
    server 127.0.0.1:5000;
    keepalive 32;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect all plain HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL Certificates (Managed by Certbot in Step 7.3)
    # ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Static Assets Fast Delivery
    location /static/ {
        alias /opt/kotak_terminal/static/;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }

    # WebSocket SFeed & Socket.IO Engine
    location /socket.io/ {
        proxy_pass http://kotak_app/socket.io/;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # REST APIs & Application Endpoints
    location / {
        proxy_pass http://kotak_app;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_read_timeout 60s;
    }
}
```

### 7.3 Enable Site & Acquire SSL Certificate
```bash
# Enable configuration
sudo ln -sf /etc/nginx/sites-available/kotak-terminal /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Verify syntax
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Issue automated Let's Encrypt TLS Certificate
sudo certbot --nginx -d your-domain.com
```

---

## Step 8: Cloudflare Tunnel Deployment (Zero-Trust Option)

If you prefer **not** to expose any open public inbound ports (80/443) on OCI, use Cloudflare Tunnel.

```bash
# 1. Install cloudflared on Ubuntu
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# 2. Authenticate Cloudflare
cloudflared tunnel login

# 3. Create Tunnel
cloudflared tunnel create kotak-terminal-tunnel

# 4. Route DNS hostname to tunnel
cloudflared tunnel route dns kotak-terminal-tunnel terminal.yourdomain.com

# 5. Configure Tunnel config (/etc/cloudflared/config.yml)
sudo mkdir -p /etc/cloudflared
sudo nano /etc/cloudflared/config.yml
```

Paste configuration:
```yaml
tunnel: <TUNNEL_UUID>
credentials-file: /etc/cloudflared/<TUNNEL_UUID>.json

ingress:
  - hostname: terminal.yourdomain.com
    service: http://127.0.0.1:5000
  - service: http_status:404
```

```bash
# 6. Install as system service and start
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```
*Your terminal is now securely accessible worldwide over Cloudflare's edge with zero inbound ports open on OCI!*

---

## Step 9: Automated Backup & Retention Strategy

Because SQLite operates in WAL mode, never copy the raw `.db` file directly while the process is running. Use SQLite's online `.backup` API.

### 9.1 Create Backup Script
```bash
sudo nano /usr/local/bin/backup_trading_db.sh
```

Paste:
```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/opt/backups/kotak_terminal"
DB_SRC="/opt/kotak_terminal/data/kotak_terminal.db"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DEST_FILE="${BACKUP_DIR}/kotak_backup_${TIMESTAMP}.db"

mkdir -p "${BACKUP_DIR}"

# Online atomic backup (WAL safe)
sqlite3 "${DB_SRC}" ".backup '${DEST_FILE}'"

# Compress snapshot
gzip -f "${DEST_FILE}"

# Enforce 14-day retention (Delete older snapshots)
find "${BACKUP_DIR}" -name "kotak_backup_*.db.gz" -mtime +14 -delete

echo "[$(date -u)] Backup completed: ${DEST_FILE}.gz"
```

```bash
# Grant execution permissions
sudo chmod +x /usr/local/bin/backup_trading_db.sh

# Test backup execution
sudo /usr/local/bin/backup_trading_db.sh
```

### 9.2 Setup Automated Cron Job
```bash
# Open root crontab
sudo crontab -e
```

Add backup schedules (Hourly during trading hours + Daily EOD):
```cron
# Run hourly backups during trading days (Mon-Fri, 9am - 4pm IST)
0 9-16 * * 1-5 /usr/local/bin/backup_trading_db.sh >> /var/log/kotak_backup.log 2>&1

# Run daily EOD snapshot at 18:00 IST
0 18 * * 1-5 /usr/local/bin/backup_trading_db.sh >> /var/log/kotak_backup.log 2>&1
```

---

## Step 10: Post-Deployment Smoke Test Checklist

Execute these verification commands on the OCI instance to certify healthy deployment:

```bash
# 1. Systemd Service Verification
systemctl is-active kotak-terminal   # Expected: active

# 2. Local Health Endpoint
curl -s http://127.0.0.1:5000/api/v1/health | grep '"status":"ok"'

# 3. Public Domain SSL / Nginx Verification
curl -I https://your-domain.com | grep "HTTP/2 200\|HTTP/1.1 200"

# 4. Authentication Endpoint State
curl -s https://your-domain.com/api/auth/status

# 5. Broker Wiring & Client Initialization State
curl -s https://your-domain.com/api/broker/client-state

# 6. Option Chain API Live Test
curl -s "https://your-domain.com/api/option-chain?symbol=NIFTY" | grep '"lot_size":65'

# 7. Check Systemd Journal for Zero Unhandled Exceptions
sudo journalctl -u kotak-terminal -n 50 --no-pager
```

---

## Step 11: Live Production Trading Prerequisites

Before placing real capital orders on Kotak Neo from the cloud terminal:

1. **Verify Clock Drift:** Run `chronyc tracking` and confirm `System time` offset is **$< 20\text{ ms}$**.
2. **Operator Login:** Access `https://your-domain.com`, sign in with operator credentials, and verify rolling session cookie.
3. **Broker Authentication:** Complete 2FA login (TOTP + MPIN). Confirm header displays **`BROKER: CONNECTED`** and your **`UCC`**.
4. **Pre-Flight Execution Mode:** Confirm header badge is **`DISABLED`** or **`PAPER`** by default.
5. **Two-Factor Mode Gate:** When ready for live trades, press **`Alt + E`**, select **LIVE**, and complete the mandatory **`CONFIRM_LIVE`** typing challenge.
6. **Kill-Switch Verification:** Verify that **`Shift + Esc`** prompts the emergency cancel dialog.

---

## Step 12: Emergency Disaster Recovery & Rollback Procedure

If an erroneous release is deployed or unexpected behavior occurs in live trading:

### 12.1 Immediate Panic Stop (Zero Market Risk)
```bash
# 1. Stop terminal application instantly (halts all local order dispatch)
sudo systemctl stop kotak-terminal

# 2. Emergency cancel all resting open orders on Kotak Neo via CLI emergency script
sudo -u trading bash -c "cd /opt/kotak_terminal && source .venv/bin/activate && python3 -c '
from app.broker.adapters.kotak_order_adapter import kotak_order_adapter
res = kotak_order_adapter.cancel_all_orders()
print(\"Emergency Cancel Result:\", res)
'"
```

### 12.2 Codebase Rollback
```bash
sudo -u trading -i
cd /opt/kotak_terminal

# Check git history
git log -n 5 --oneline

# Hard reset to previous known good commit or tag (e.g. Milestone M6)
git reset --hard <PREVIOUS_STABLE_COMMIT_HASH>

# Reinstall dependencies if requirements were changed
source .venv/bin/activate
pip install -r requirements.txt
exit
```

### 12.3 Database Snapshot Restoration
```bash
# Stop application
sudo systemctl stop kotak-terminal

# Restore database from latest gzip snapshot
LATEST_BACKUP=$(ls -t /opt/backups/kotak_terminal/kotak_backup_*.db.gz | head -n 1)
sudo -u trading gunzip -c "${LATEST_BACKUP}" > /opt/kotak_terminal/data/kotak_terminal.db

# Ensure WAL mode is active
sudo -u trading sqlite3 /opt/kotak_terminal/data/kotak_terminal.db "PRAGMA journal_mode=WAL;"

# Restart service
sudo systemctl start kotak-terminal
sudo systemctl status kotak-terminal
```

