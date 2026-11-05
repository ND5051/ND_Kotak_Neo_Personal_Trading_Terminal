import json


def test_auth_registration_and_login_flow(client):
    """Integration test: Register, login, access protected route, check security headers, and logout."""
    # 1. Register new trader
    reg_resp = client.post(
        "/api/auth/register",
        data=json.dumps({
            "username": "flow_trader",
            "email": "flow@kotakneo.local",
            "password": "SuperSecretPass123!",
        }),
        content_type="application/json",
    )
    assert reg_resp.status_code == 201
    reg_data = reg_resp.get_json()
    assert reg_data["status"] == "success"
    assert reg_data["data"]["user"]["username"] == "flow_trader"

    # Verify Security Headers
    assert reg_resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert reg_resp.headers.get("X-Frame-Options") == "DENY"
    assert reg_resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "X-Request-ID" in reg_resp.headers
    assert "X-Correlation-ID" in reg_resp.headers

    # 2. Access protected route without authentication -> Must return 401
    unauth_resp = client.get("/api/auth/me")
    assert unauth_resp.status_code == 401
    assert unauth_resp.get_json()["error_code"] == "UNAUTHORIZED"

    # 3. Login with credentials
    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "flow_trader",
            "password": "SuperSecretPass123!",
        }),
        content_type="application/json",
    )
    assert login_resp.status_code == 200
    login_data = login_resp.get_json()
    token = login_data["data"]["token"]
    assert token is not None

    # 4. Access protected route with Bearer token -> Must return 200
    auth_resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert auth_resp.status_code == 200
    auth_data = auth_resp.get_json()
    assert auth_data["data"]["user"]["username"] == "flow_trader"

    # 5. Check status endpoint with Bearer token
    status_resp = client.get(
        "/api/auth/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_resp.status_code == 200
    assert status_resp.get_json()["data"]["authenticated"] is True

    # 6. Logout
    logout_resp = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout_resp.status_code == 200

    # 7. Access protected route after logout -> Must return 401 (session revoked)
    post_logout_resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert post_logout_resp.status_code == 401
