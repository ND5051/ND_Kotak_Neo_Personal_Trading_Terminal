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
