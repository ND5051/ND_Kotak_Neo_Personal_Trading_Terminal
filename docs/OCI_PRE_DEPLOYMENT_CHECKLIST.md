# OCI Pre-Deployment Checklist
**Kotak Neo Personal Trading Terminal**  
**Milestone:** Milestone M7 (Production Hardening & Live Cloud Migration)  
**Target Tag:** `M7_PRE_PRODUCTION`  
**Host Target:** Oracle Cloud Infrastructure (OCI) Ubuntu Compute  
**Document Version:** 1.0.0  
**Last Updated:** 2026-11-15  

---

## Pre-Deployment Verification Protocol

This checklist establishes the mandatory pre-flight criteria required before migrating the **Kotak Neo Personal Trading Terminal** from local development to a live cloud instance on Oracle Cloud Infrastructure (OCI). 

Every checkbox `[ ]` must be explicitly verified and signed off before committing live capital.

---

```
+---------------------------------------------------------------------------------------------------------+
|                                    OCI PRE-DEPLOYMENT MASTER MATRIX                                     |
+---------------------------------------------------------------------------------------------------------+
| [ ] 1. GitHub Migration Readiness                                                                      |
| [ ] 2. Secrets Removal & Sanitation Audit                                                               |
| [ ] 3. .gitignore Strict Exclusion Audit                                                                |
| [ ] 4. M7_PRE_PRODUCTION Tagging & Baseline Lock                                                        |
| [ ] 5. OCI Ubuntu Server Provisioning & Hardening                                                       |
| [ ] 6. SSH Hardening & Non-Root User Isolation                                                          |
| [ ] 7. Production .env Vault Preparation                                                                |
| [ ] 8. Post-Deployment Smoke Test Protocol                                                             |
| [ ] 9. Live Phase 12B UAT Execution Plan                                                                |
| [ ] 10. Emergency Disaster Recovery & Rollback Plan                                                     |
+---------------------------------------------------------------------------------------------------------+
```

---

## 1. GitHub Ready

- [ ] **1.1 Git Working Tree Cleanliness:**
  - Execute `git status`. Verify no unwanted temporary files, scratch scripts, or unorganized files exist.
- [ ] **1.2 Clean Documentation Hierarchy:**
  - Confirm all markdown files are categorized under `docs/` (`docs/specs/`, `docs/reviews/`, `docs/testing/`, `docs/diagnostics/`, `docs/releases/`, `docs/adr/`).
- [ ] **1.3 Private Repository Assurance:**
  - Confirm target GitHub repository visibility is set strictly to **PRIVATE**.
  - `gh repo view --json isPrivate` returns `true`.
- [ ] **1.4 Branch Protection Standard:**
  - Ensure `main` branch is designated as the production deployment branch.
- [ ] **1.5 Dedicated Deploy Key Generated:**
  - Generate a read-only SSH deploy key on the OCI instance:
    ```bash
    ssh-keygen -t ed25519 -C "oci-trading-terminal" -f ~/.ssh/id_ed25519 -N ""
    ```
  - Register public key under GitHub: **Repo &rarr; Settings &rarr; Deploy Keys (Read-only)**.

---

## 2. Secrets Removed & Sanitation Audit

- [ ] **2.1 Codebase Credentials Scan:**
  - Search entire working tree for accidental hardcoded secrets:
    ```bash
    git grep -E -i "NEO_CONSUMER_SECRET|NEO_MPIN|NEO_TOTP_SECRET|SECRET_KEY|ENCRYPTION_KEY"
    ```
  - **Assert:** Only variable references (`os.getenv(...)`) and documentation placeholders appear.
- [ ] **2.2 Git History Sanitization Check:**
  - Inspect git commit history for previous accidental `.env` commits:
    ```bash
    git log --all --full-history -- "**.env*"
    ```
  - **Assert:** No production `.env` containing live secrets exists in git history.
- [ ] **2.3 Production Key Isolation:**
  - Confirm local development `SECRET_KEY` and `ENCRYPTION_KEY` are **never** reused on the OCI cloud instance.
  - Generate fresh 256-bit cryptographically secure keys for production:
    ```bash
    python3 -c "import secrets; from cryptography.fernet import Fernet; print('SECRET_KEY=' + secrets.token_hex(32)); print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
    ```

---

## 3. .gitignore Audit

Verify `.gitignore` contains strict exclusion patterns for all sensitive files:

- [ ] **3.1 Secrets & Environment Files Excluded:**
  ```gitignore
  .env
  .env.local
  .env.*.local
  ```
- [ ] **3.2 SQLite Databases & Storage Excluded:**
  ```gitignore
  *.db
  *.sqlite3
  data/
  instance/
  ```
- [ ] **3.3 Log Files & Artifacts Excluded:**
  ```gitignore
  logs/
  *.log
  *.log.*
  ```
- [ ] **3.4 Virtual Environments Excluded:**
  ```gitignore
  .venv/
  venv/
  env/
  ```
- [ ] **3.5 Pytest & Python Cache Excluded:**
  ```gitignore
  __pycache__/
  *.py[cod]
  .pytest_cache/
  .coverage
  ```
- [ ] **3.6 Live .gitignore Check:**
  - Test ignoring rule against untracked dummy files:
    ```bash
    git check-ignore -v .env data/kotak_terminal.db logs/neo-api-client.log
    ```
  - **Assert:** All files report matching `.gitignore` rules.

---

## 4. M7_PRE_PRODUCTION Tagging & Baseline Lock

- [ ] **4.1 Test Suite Full Pass:**
  - Execute full unit test suite:
    ```bash
    .venv/Scripts/python -m pytest tests/unit/ -q
    ```
  - **Assert:** 100% tests pass (zero failures, zero regressions).
- [ ] **4.2 Stage & Commit Pre-Deployment State:**
  ```bash
  git add .
  git commit -m "chore(release): prepare production baseline for Milestone M7 OCI deployment"
  ```
- [ ] **4.3 Tag Milestone M7 Baseline:**
  ```bash
  git tag -a "M7_PRE_PRODUCTION" -m "Production-hardened baseline for Milestone M7 live OCI deployment. All Paper tests passed (Test 1-4, Sec 3-4)."
  ```
- [ ] **4.4 Push Tag to Remote:**
  ```bash
  git push origin main --tags
  ```

---

## 5. OCI Server Prepared

- [ ] **5.1 Instance Provisioned:**
  - OCI Compute shape provisioned (Ubuntu 22.04 LTS):
    - *Recommended:* `VM.Standard.A1.Flex` (4 OCPU, 24GB RAM or 2 OCPU, 12GB RAM - Always Free).
    - *Alternative:* `VM.Standard.E2.1.Micro` (1 OCPU, 1GB RAM &bull; requires 4GB swap).
- [ ] **5.2 System Packages Upgraded:**
  ```bash
  sudo apt update && sudo apt upgrade -y
  sudo apt install -y build-essential python3-dev python3-venv sqlite3 curl git htop fail2ban ufw chrony
  ```
- [ ] **5.3 Indian Market Timezone Configured:**
  ```bash
  sudo timedatectl set-timezone Asia/Kolkata
  timedatectl | grep "Time zone: Asia/Kolkata"
  ```
- [ ] **5.4 NTP Microsecond Clock Synchronization:**
  ```bash
  sudo systemctl enable --now chrony
  chronyc tracking | grep -E "System time|RMS offset"
  ```
  - **Assert:** Clock drift $< 20\text{ ms}$.
- [ ] **5.5 Swap Space Allocated (4GB):**
  ```bash
  sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
  free -h | grep "Swap"
  ```
- [ ] **5.6 Host Firewall & OCI iptables Updated:**
  ```bash
  sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
  sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
  sudo netfilter-persistent save
  ```

---

## 6. SSH Verified & Non-Root User Isolation

- [ ] **6.1 Dedicated `trading` System User Created:**
  ```bash
  sudo useradd -m -s /bin/bash trading
  id trading
  ```
- [ ] **6.2 Application Directory Permissions:**
  ```bash
  sudo mkdir -p /opt/kotak_terminal /opt/backups/kotak_terminal
  sudo chown -R trading:trading /opt/kotak_terminal /opt/backups/kotak_terminal
  ```
- [ ] **6.3 SSH Key-Based Authentication Strictly Enforced:**
  - Verify `/etc/ssh/sshd_config` contains:
    ```sshconfig
    PasswordAuthentication no
    PermitRootLogin prohibit-password
    PubkeyAuthentication yes
    ```
- [ ] **6.4 Fail2ban Service Active:**
  ```bash
  sudo systemctl enable --now fail2ban
  sudo fail2ban-client status sshd
  ```

---

## 7. .env Prepared

- [ ] **7.1 Production `.env` Populated at `/opt/kotak_terminal/.env`:**
  - `APP_ENV=production`
  - `DEBUG=false`
  - `SECRET_KEY` (Freshly generated 32-byte hex token)
  - `ENCRYPTION_KEY` (Freshly generated Fernet 32-byte url-safe token)
  - `DATABASE_URL=sqlite:////opt/kotak_terminal/data/kotak_terminal.db`
  - `NEO_LOG_FILE_ENABLED=false` (Mandatory to prevent rollover file locks)
  - `NEO_CONSUMER_KEY`, `NEO_CONSUMER_SECRET` (Production Kotak Neo keys)
  - `NEO_MOBILE_NUMBER`, `NEO_UCC`, `NEO_MPIN`, `NEO_TOTP_SECRET`
- [ ] **7.2 File Permissions Hardened:**
  ```bash
  sudo chown trading:trading /opt/kotak_terminal/.env
  sudo chmod 600 /opt/kotak_terminal/.env
  ls -l /opt/kotak_terminal/.env | grep "-rw------- 1 trading trading"
  ```
- [ ] **7.3 Python Environment Loading Test:**
  - Test `.env` validity inside virtual environment:
    ```bash
    sudo -u trading bash -c "cd /opt/kotak_terminal && source .venv/bin/activate && python3 -c '
    import os
    from dotenv import load_dotenv
    load_dotenv(\".env\")
    assert os.getenv(\"APP_ENV\") == \"production\"
    assert os.getenv(\"NEO_CONSUMER_KEY\") is not None
    assert len(os.getenv(\"SECRET_KEY\")) >= 32
    print(\".env verified successfully.\")
    '"
    ```

---

## 8. Smoke Test Plan

Execute immediately following `systemctl start kotak-terminal`:

- [ ] **8.1 Systemd Service Running:**
  ```bash
  systemctl is-active kotak-terminal
  ```
  - **Assert:** Returns `active`.
- [ ] **8.2 Health Endpoint Response:**
  ```bash
  curl -s http://127.0.0.1:5000/api/v1/health
  ```
  - **Assert:** HTTP 200 `{"status":"ok", ...}`.
- [ ] **8.3 Reverse Proxy & SSL Handshake:**
  ```bash
  curl -I https://your-domain.com
  ```
  - **Assert:** HTTP/2 200 or 302 Redirect to `/dashboard`.
- [ ] **8.4 WebSocket Upgrade Handshake:**
  - Verify `/socket.io/` upgrades connection without 502/504 proxy errors.
- [ ] **8.5 SQLite WAL Mode Verified:**
  ```bash
  sudo -u trading sqlite3 /opt/kotak_terminal/data/kotak_terminal.db "PRAGMA journal_mode;"
  ```
  - **Assert:** Returns `wal`.
- [ ] **8.6 Option Chain Live Broker Test:**
  ```bash
  curl -s "http://127.0.0.1:5000/api/option-chain?symbol=NIFTY" | grep '"lot_size":65'
  ```
  - **Assert:** Returns live Nifty 50 strikes with lot size = 65.
- [ ] **8.7 Zero Exceptions in Journald:**
  ```bash
  sudo journalctl -u kotak-terminal -n 50 --no-pager
  ```
  - **Assert:** Zero tracebacks or unhandled exceptions.

---

## 9. Live UAT Plan (Phase 12B Execution)

Execute strictly during regular Indian market hours (**9:15 AM – 3:30 PM IST**):

- [ ] **9.1 Safe Starting State:**
  - Header displays **`MODE: DISABLED`** or **`MODE: PAPER`**.
- [ ] **9.2 Broker Session Establishment:**
  - Log in with 2FA/TOTP + MPIN &bull; Confirm header displays **`BROKER: CONNECTED`** and UCC.
- [ ] **9.3 Two-Factor Mode Gating Drill:**
  - Press `Alt + E` &rarr; select **LIVE** &rarr; verify mandatory challenge requires typing `"CONFIRM_LIVE"`.
- [ ] **9.4 Emergency Kill-Switch Drill (`Shift + Esc`):**
  - Verify global emergency cancel modal triggers and purges active orders within 500ms.
- [ ] **9.5 Section 5 & 5A: Live Equity Micro-Lot Order (1 Share):**
  - Select liquid cash scrip (**ITC** or **INFY** on `nse_cm`).
  - Place 1-share Limit Buy order at 2–3% below market.
  - Verify broker order ID (`nOrdNo`) appears with status `OPEN`/`PENDING`.
  - Modify price by +₹0.10 tick &rarr; verify status `MODIFIED`.
  - Cancel order &rarr; verify status `CANCELLED`.
  - Execute 1-share Buy & Sell roundtrip &rarr; verify Open Positions Net Qty returns to **`0`**.
- [ ] **9.6 Section 6: Live Option Micro-Lot Order (1 Lot F&O):**
  - Select liquid NIFTY Call/Put contract.
  - Verify lot size auto-populates as **`65`**.
  - Place order & test native broker stop-loss (SL) order.
- [ ] **9.7 Section 7: Live Multi-Leg Basket DAG Execution:**
  - Stage 2-leg Bull Call Spread or Bear Put Spread.
  - Execute in `DEPENDENCY` mode &bull; confirm Stage 1 (Wing) fills before Stage 2 (Body).
- [ ] **9.8 Section 8: End-of-Day Ledger & Demat Reconciliation:**
  - Confirm Trade Book fills match official Kotak Neo broker trade log.

---

## 10. Rollback Plan

If unexpected anomalies or broker rejections occur at any point:

- [ ] **10.1 Emergency Kill Switch:**
  - Press `Shift + Esc` from browser UI, OR execute broker-side cancel script via SSH:
    ```bash
    sudo -u trading bash -c "cd /opt/kotak_terminal && source .venv/bin/activate && python3 -c '
    from app.broker.adapters.kotak_order_adapter import kotak_order_adapter
    print(kotak_order_adapter.cancel_all_orders())
    '"
    ```
- [ ] **10.2 Immediate Service Halt:**
  ```bash
  sudo systemctl stop kotak-terminal
  ```
- [ ] **10.3 Code Reversion to Prior Stable Release:**
  ```bash
  sudo -u trading bash -c "cd /opt/kotak_terminal && git reset --hard M6_RELEASE_PACKAGE"
  ```
- [ ] **10.4 Atomic Database Snapshot Restoration:**
  ```bash
  LATEST_BACKUP=$(ls -t /opt/backups/kotak_terminal/kotak_backup_*.db.gz | head -n 1)
  sudo -u trading gunzip -c "${LATEST_BACKUP}" > /opt/kotak_terminal/data/kotak_terminal.db
  sudo systemctl start kotak-terminal
  ```

---

## Sign-Off Record

| Verification Stage | Operator / Lead | Date (IST) | Result |
| :--- | :--- | :---: | :---: |
| **Git & Secrets Sanitation** | ____________________ | ___ / ___ / 2026 | [ ] PASS &nbsp; [ ] FAIL |
| **OCI Compute & Network Setup** | ____________________ | ___ / ___ / 2026 | [ ] PASS &nbsp; [ ] FAIL |
| **Production Environment (.env)** | ____________________ | ___ / ___ / 2026 | [ ] PASS &nbsp; [ ] FAIL |
| **Post-Deploy Smoke Tests** | ____________________ | ___ / ___ / 2026 | [ ] PASS &nbsp; [ ] FAIL |
| **Live Phase 12B UAT Sign-Off** | ____________________ | ___ / ___ / 2026 | [ ] PASS &nbsp; [ ] FAIL |

