# Milestone M1 Rollback Guide
## Disaster Recovery & Rollback Procedure

**Document Version:** 1.0.0  
**Target Baseline:** `M1_BASELINE`  
**Git Tag:** `M1_BASELINE`  
**Baseline Commit:** `ae851b8` (or current tag reference)  
**Database Head Revision:** `6b0dd678a5e4`  

---

## 1. Baseline Target Identifiers

In the event of an unrecoverable failure during post-M1 deployments (e.g. during Phase 4 market data work), this document provides exact operational procedures to return the terminal to the verified Milestone M1 state.

| Identifier | Target Value | Verification Command |
|---|---|---|
| **Git Baseline Tag** | `M1_BASELINE` | `git describe --tags` |
| **Git Baseline Commit** | Reference commit of `M1_BASELINE` | `git rev-parse M1_BASELINE` |
| **Database Migration ID** | `6b0dd678a5e4` | `alembic current` |
| **Python Virtualenv** | `.venv` (Python 3.14.x) | `python --version` |

---

## 2. Full Rollback Procedures

### Step 1: Terminate Active Processes
Ensure no running terminal processes are locking the SQLite database or ports:
```powershell
# PowerShell:
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
```

### Step 2: Database Rollback (If Rolled Forward in Phase 4)
If migrations beyond `6b0dd678a5e4` were applied, downgrade to the M1 schema:
```powershell
.\.venv\Scripts\Activate.ps1
alembic downgrade 6b0dd678a5e4
```
To verify the schema is strictly at M1:
```powershell
alembic current
# Expected Output: 6b0dd678a5e4 (head)
```

To rollback Phase 3 completely to Phase 2 baseline (if needed):
```powershell
alembic downgrade 4a7a9972b64d
```

### Step 3: Git Codebase Rollback
Reset the working branch cleanly to the tagged `M1_BASELINE`:

```powershell
# Fetch all tags from remote origin
git fetch origin --tags

# Option A: Clean hard reset to baseline tag (Warning: Discards uncommitted changes)
git checkout main
git reset --hard M1_BASELINE

# Option B: Create a recovery branch from the baseline
git checkout -b recovery/m1-restore M1_BASELINE
```

### Step 4: Environment & Dependency Verification
Verify all Phase 1–3 dependencies match the `M1_BASELINE` requirements:
```powershell
pip install -r requirements.txt
```

### Step 5: Verification & Smoke Test
Run the comprehensive 51-test suite to confirm baseline integrity:
```powershell
.\.venv\Scripts\pytest -v
```
Expected Output:
```text
============================= 51 passed in 10.00s =============================
```

Start the application to confirm health:
```powershell
python run.py
```
Execute health check probe:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/health" -Method Get
```
Expected response:
```json
{
  "success": true,
  "data": {
    "status": "healthy"
  }
}
```
