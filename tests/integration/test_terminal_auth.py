import json
import pytest
from app import create_app


def test_default_operator_creation_and_terminal_auth_lifecycle(client):
    """
    Integration test verifying the end-to-end terminal authentication lifecycle:
    1. Default operator exists but is NOT automatically logged in.
    2. Unauthenticated GET /terminal renders with unauthenticated state.
    3. Unauthenticated GET /api/auth/status returns authenticated=False.
    4. Unauthenticated POST /api/orders/mode is rejected with 401.
    5. Operator logs in with explicit credentials via POST /api/auth/login.
    6. Cookie 'session_id' is set with Path=/ and HttpOnly.
    7. GET /api/auth/status via cookie returns authenticated=True and operator details.
    8. POST /api/orders/mode succeeds with session cookie (changes mode to PAPER).
    9. POST /api/auth/logout invalidates session and clears cookie.
    10. Subsequent protected API calls return 401.
    """
    # 1. Verify unauthenticated GET /api/auth/status
    status_resp = client.get("/api/auth/status")
    assert status_resp.status_code == 200
    status_data = status_resp.get_json()
    assert status_data["data"]["authenticated"] is False
    assert status_data["data"]["user"] is None

    # 2. Verify unauthenticated POST /api/orders/mode returns 401
    mode_resp = client.post(
        "/api/orders/mode",
        data=json.dumps({"mode": "PAPER", "reason": "Testing auth gate"}),
        content_type="application/json",
    )
    assert mode_resp.status_code == 401
    assert "session" in mode_resp.get_json()["message"].lower()

    # 3. Verify GET /terminal renders
    term_resp = client.get("/terminal")
    assert term_resp.status_code == 200
    html = term_resp.get_data(as_text=True)
    # Check that login modal is included in terminal template
    assert "operator-login-modal" in html
    assert "Operator Authentication Required" in html

    # 4. Operator logs in explicitly with default operator credentials
    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "admin",
            "password": "AdminPassword123!",
        }),
        content_type="application/json",
    )
    assert login_resp.status_code == 200
    login_json = login_resp.get_json()
    assert login_json["status"] == "success"
    assert login_json["data"]["user"]["username"] == "admin"
    token = login_json["data"]["token"]
    assert token is not None

    # Verify session cookie was set with Path=/ and HttpOnly
    cookie_header = login_resp.headers.get("Set-Cookie")
    assert cookie_header is not None
    assert "session_id=" in cookie_header
    assert "Path=/" in cookie_header or "path=/" in cookie_header
    assert "HttpOnly" in cookie_header or "httponly" in cookie_header

    # 5. Verify GET /api/auth/status now returns authenticated=True via cookie
    auth_status_resp = client.get("/api/auth/status")
    assert auth_status_resp.status_code == 200
    auth_status_data = auth_status_resp.get_json()
    assert auth_status_data["data"]["authenticated"] is True
    assert auth_status_data["data"]["user"]["username"] == "admin"

    # 6. Verify GET /terminal with session cookie reflects authenticated state
    term_auth_resp = client.get("/terminal")
    assert term_auth_resp.status_code == 200
    term_html = term_auth_resp.get_data(as_text=True)
    assert "admin" in term_html

    # 7. Verify POST /api/orders/mode succeeds using session cookie
    mode_change_resp = client.post(
        "/api/orders/mode",
        data=json.dumps({"mode": "PAPER", "reason": "Operator session active"}),
        content_type="application/json",
    )
    assert mode_change_resp.status_code == 200
    mode_change_data = mode_change_resp.get_json()
    assert mode_change_data["status"] == "success"
    assert mode_change_data["data"]["execution_mode"] == "PAPER"

    # 8. Operator logs out via POST /api/auth/logout
    logout_resp = client.post("/api/auth/logout")
    assert logout_resp.status_code == 200

    # 9. Verify GET /api/auth/status is unauthenticated again
    post_logout_status = client.get("/api/auth/status")
    assert post_logout_status.status_code == 200
    assert post_logout_status.get_json()["data"]["authenticated"] is False

    # 10. Verify POST /api/orders/mode returns 401 after logout
    post_logout_mode = client.post(
        "/api/orders/mode",
        data=json.dumps({"mode": "DISABLED", "reason": "After logout"}),
        content_type="application/json",
    )
    assert post_logout_mode.status_code == 401


def test_root_redirects_to_terminal_and_broker_session_status(client, monkeypatch):
    """
    Integration test verifying TERMINAL_ENTRYPOINT_REMEDIATION:
    1. GET / redirects (302) to /terminal and does not serve old Phase 1 skeleton.
    2. GET /terminal renders Broker Session Status widget and Broker Login Validation panel.
    3. GET /api/broker/session-status returns required schema before and after broker login.
    """
    from unittest.mock import MagicMock
    mock_sdk = MagicMock()
    mock_sdk.totp_login.return_value = {"data": {"token": "view_tok", "sid": "view_sid"}}
    mock_sdk.totp_validate.return_value = {
        "data": {"token": "trade_tok", "sid": "trade_sid", "ucc": "UAT_UCC_99", "greetingName": "UAT Trader"}
    }
    monkeypatch.setattr("app.broker.adapters.kotak_adapter.NeoAPI", MagicMock(return_value=mock_sdk))
    # 1. Root URL redirects to /terminal
    root_resp = client.get("/")
    assert root_resp.status_code == 302
    assert root_resp.headers["Location"].endswith("/terminal")

    followed_resp = client.get("/", follow_redirects=True)
    assert followed_resp.status_code == 200
    html = followed_resp.get_data(as_text=True)
    assert "Phase 1 - Project Skeleton Ready" not in html
    assert "broker-session-widget" in html
    assert "broker-login-modal" in html
    assert "Kotak Neo Broker Login" in html

    # 2. Initial broker session-status before operator/broker login
    pre_status = client.get("/api/broker/session-status")
    assert pre_status.status_code == 200
    pre_data = pre_status.get_json()["data"]
    for key in ("authenticated", "profile_loaded", "ucc", "session_expiry", "broker_connected"):
        assert key in pre_data

    # 3. Operator logs in explicitly
    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({"username": "admin", "password": "AdminPassword123!"}),
        content_type="application/json",
    )
    assert login_resp.status_code == 200

    # 4. Broker login via /api/broker/login
    broker_login_resp = client.post(
        "/api/broker/login",
        data=json.dumps({
            "consumer_key": "test_key",
            "ucc": "UAT_UCC_99",
            "mobile_number": "9876543210",
            "mpin": "123456",
            "totp_secret": "JBSWY3DPEHPK3PXP",
        }),
        content_type="application/json",
    )
    assert broker_login_resp.status_code == 200

    # 5. Verify GET /api/broker/session-status reflects active broker session
    post_status = client.get("/api/broker/session-status")
    assert post_status.status_code == 200
    post_data = post_status.get_json()["data"]
    assert post_data["authenticated"] is True
    assert post_data["broker_connected"] is True
    assert post_data["profile_loaded"] is True
    assert post_data["ucc"] is not None
    assert post_data["session_expiry"] is not None
    assert post_data["last_broker_sync"] is not None

    # 6. Cleanup broker & operator logout
    client.post("/api/broker/logout")
    client.post("/api/auth/logout")
