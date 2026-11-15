# Environment Variable Loading Diagnostic (`ENV_LOADING_DIAGNOSTIC.md`)

**Document Type:** Root Cause & Configuration Diagnostic  
**Date:** 2026-11-12  
**Observed Error:** `"Kotak Neo TOTP login failed: Consumer key YOUR_CONSUMER_KEY does not exist"`  

---

## 1. Executive Summary

The error `"Consumer key YOUR_CONSUMER_KEY does not exist"` occurred because:

1. **Duplicate Key in `.env`:** Line 19 of `.env` contains `NEO_CONSUMER_KEY=YOUR_CONSUMER_KEY`, while line 23 contains the real key `NEO_CONSUMER_KEY=836bde98-19ef-4d49-9df3-cfd5dc1a1b0f`.
2. **Process Lifecycle vs File Modification Time:**
   - The Flask server process was started at **`2026-11-12T16:43:44Z`**.
   - The `.env` file was modified at **`2026-11-12T16:44:40Z`**.
   - `load_dotenv()` only runs **once** when [`config/base.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/config/base.py#L9) is imported at server boot. Modifying `.env` while the Flask server is running **does not** update `os.environ` in the running process memory.
   - Consequently, the running Flask process continued to use the in-memory value (`YOUR_CONSUMER_KEY`) loaded at startup for all broker login requests (`16:44:03Z`, `16:44:45Z`, and `16:44:55Z`).

---

## 2. Answers to Specific Questions

### Question 1: Where is `NEO_CONSUMER_KEY` loaded from?
- Loaded from `os.getenv("NEO_CONSUMER_KEY")` in [`app/broker/routes.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/routes.py#L119):
  ```python
  credentials = {
      "consumer_key": payload.get("consumer_key") or os.getenv("NEO_CONSUMER_KEY"),
      "consumer_secret": payload.get("consumer_secret") or os.getenv("NEO_CONSUMER_SECRET"),
      "mobile_number": payload.get("mobile_number") or os.getenv("NEO_MOBILE_NUMBER"),
      "ucc": payload.get("ucc") or os.getenv("NEO_UCC"),
      "mpin": payload.get("mpin") or os.getenv("NEO_MPIN"),
      "totp_secret": payload.get("totp_secret") or os.getenv("NEO_TOTP_SECRET"),
  }
  ```
- Also referenced during session restoration in [`app/broker/adapters/kotak_adapter.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/app/broker/adapters/kotak_adapter.py#L225).

### Question 2: Is the application loading `.env` or `.env.example`?
- The application loads **`.env`** directly via `load_dotenv(BASE_DIR / ".env")` in [`config/base.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/config/base.py#L9).
- The application does **not** load `.env.example`.

### Question 3: Effective runtime values (masked)
Inspected from `.env` and `dotenv_values()`:
- **`NEO_CONSUMER_KEY`**: `836b...1b0f` *(Note: line 19 also contains duplicate `YOUR_CONSUMER_KEY`)*
- **`NEO_MOBILE_NUMBER`**: `+9199...8714`
- **`NEO_UCC`**: `W0EZB`
- **`NEO_MPIN`**: `16...81`
- **`NEO_TOTP_SECRET`**: `E3EL...QLDQ`

### Question 4: Which file path was loaded?
- **Absolute Path:** `C:\Users\User\Documents\02.NMD Docs\Trading\Learn To Code - Nitin Joshi\ND Projects\ND_Kotak_Neo_Personal_Trading_Terminal\.env`
- Defined in `config/base.py` as `BASE_DIR / ".env"`.

### Question 5: Is dotenv initialized?
- **Yes.** Initialized in [`config/base.py`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/config/base.py#L9):
  ```python
  from dotenv import load_dotenv
  BASE_DIR = Path(__file__).resolve().parent.parent
  load_dotenv(BASE_DIR / ".env")
  ```
- **Crucial limitation:**
  - `load_dotenv` is only invoked once during module import at process launch.
  - In `config/base.py`, it does not set `override=True`, meaning any pre-existing environment variables in the parent shell or running process take precedence.

### Question 6: Is Broker Login modal reading environment values or placeholder defaults?
- **Neither.** The Broker Login modal in [`templates/components/broker_login_modal.html`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/templates/components/broker_login_modal.html#L53-L58) has the checkbox:
  ```html
  <input type="checkbox" id="broker-use-env" checked>
  <span>Use server .env Kotak Neo credentials (NEO_*)</span>
  ```
- When checked (`checked = true`), [`static/js/terminal_shell.js`](file:///c:/Users/User/Documents/02.NMD%20Docs/Trading/Learn%20To%20Code%20-%20Nitin%20Joshi/ND%20Projects/ND_Kotak_Neo_Personal_Trading_Terminal/static/js/terminal_shell.js#L543-L560) constructs an **empty JSON body (`{}`)** and sends it via `POST /api/broker/login`.
- The modal does **not** read environment variables or send placeholder defaults. The fallback to `os.getenv("NEO_*")` occurs entirely on the server backend inside `app/broker/routes.py`.

---

## 3. Timeline of Observed Failure in `logs/terminal.log`

| Timestamp (UTC) | Event | Details |
|---|---|---|
| **16:43:44.065Z** | `SERVER_START` | Flask server started on `http://127.0.0.1:5000` with `debug=True`. At boot time, `.env` had `NEO_CONSUMER_KEY=YOUR_CONSUMER_KEY`. |
| **16:44:03.884Z** | `HTTP_REQUEST` | Live HTTP/2 connection opened to `https://mis.kotaksecurities.com/login/1.0/tradeApiLogin` with consumer key `YOUR_CONSUMER_KEY`. |
| **16:44:04.416Z** | `BROKER_LOGIN_FAILED` | Kotak Neo API returned error: `"Consumer key YOUR_CONSUMER_KEY does not exist"`. |
| **16:44:40.498Z** | File Edit | `.env` file modified on disk (line 23 appended with real key, but line 19 left intact). Running server did **not** reload `.env`. |
| **16:44:45.392Z** | `BROKER_LOGIN_FAILED` | Second login attempt still used the in-memory `YOUR_CONSUMER_KEY` from process startup. |
| **16:44:55.330Z** | `BROKER_LOGIN_FAILED` | Third login attempt failed with identical error. |

---

## 4. Remediation Steps

1. **Clean `.env` File:**
   Remove line 19 (`NEO_CONSUMER_KEY=YOUR_CONSUMER_KEY`) from `.env` so that only the valid `NEO_CONSUMER_KEY=836bde98-19ef-4d49-9df3-cfd5dc1a1b0f` remains.

2. **Enable Dynamic / Override Reloading in Server:**
   Update `config/base.py` to use `load_dotenv(BASE_DIR / ".env", override=True)` so that `.env` takes precedence over any placeholder environment variables.

3. **Restart the Server Process:**
   Restart the Flask application (`.venv\Scripts\python run.py`) so that the running Python process memory loads the valid `NEO_CONSUMER_KEY`.

