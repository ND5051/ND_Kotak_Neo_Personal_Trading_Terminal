"""
Integration tests for Phase 11A: Terminal Shell & Professional Trading Terminal UI.
Verifies master layout rendering, static design system assets, modular components,
funds/health widgets, and ExecutionMode integration.
"""

import json
import pytest


@pytest.fixture
def auth_headers(client):
    """Register and log in test user to obtain valid authorization headers."""
    client.post(
        "/api/auth/register",
        data=json.dumps({
            "username": "terminal_user",
            "email": "terminal@example.com",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "terminal_user",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    token = login_resp.get_json()["data"]["token"]
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def test_terminal_dashboard_page_loads_successfully(client):
    """Verify GET /terminal renders the Phase 11A Terminal Shell container."""
    response = client.get("/terminal")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Brand and Header
    assert "KOTAK NEO" in html
    assert "TRADING TERMINAL" in html
    assert "NIFTY 50" in html
    assert "BANKNIFTY" in html
    assert "SENSEX" in html

    # Mode and Compact Mode controllers
    assert "compact-mode-toggle" in html
    assert "workspace-reset-btn" in html
    assert "execution-mode-badge" in html

    # Navigation Tabs
    assert "tab-market-watch" in html
    assert "tab-orders" in html
    assert "tab-holdings" in html
    assert "tab-positions" in html
    assert "tab-option-chain" in html
    assert "tab-baskets" in html
    assert "tab-funds" in html
    assert "tab-health" in html

    # Core Widgets
    assert "funds-widget" in html
    assert "health-widget" in html
    assert "margin-progress-bar" in html

    # Execution Mode Challenge Modal
    assert "execution-mode-modal" in html
    assert "CONFIRM_LIVE" in html

    # Scripts and Stylesheets
    assert "terminal.css" in html
    assert "workspace_persistence.js" in html
    assert "terminal_shell.js" in html


def test_terminal_css_design_system_asset(client):
    """Verify GET /static/css/terminal.css serves design system tokens and compact mode."""
    response = client.get("/static/css/terminal.css")
    assert response.status_code == 200
    css = response.data.decode("utf-8")

    # Tokens and Palette
    assert "--bg-app" in css
    assert "--bg-surface" in css
    assert "--market-green" in css
    assert "--market-red" in css
    assert "--font-numeric" in css

    # Compact Mode Overrides
    assert ".compact-mode" in css
    assert "--row-height: 28px" in css

    # Modals and Widgets
    assert ".modal-backdrop" in css
    assert ".progress-bar" in css
    assert ".pulse-dot" in css


def test_terminal_workspace_persistence_js_asset(client):
    """Verify GET /static/js/workspace_persistence.js serves state persistence manager."""
    response = client.get("/static/js/workspace_persistence.js")
    assert response.status_code == 200
    js = response.data.decode("utf-8")

    assert "kotak_neo_workspace_v1" in js
    assert "class WorkspaceManager" in js
    assert "applyToDOM" in js
    assert "compact_mode" in js
    assert "active_tab" in js


def test_terminal_shell_controller_js_asset(client):
    """Verify GET /static/js/terminal_shell.js serves navigation and modal event handlers."""
    response = client.get("/static/js/terminal_shell.js")
    assert response.status_code == 200
    js = response.data.decode("utf-8")

    assert "class TerminalShell" in js
    assert "toggleCompactMode" in js
    assert "switchTab" in js
    assert "submitExecutionModeChange" in js
    assert "CONFIRM_LIVE" in js
    assert "refreshFunds" in js
    assert "refreshHealth" in js


def test_terminal_funds_margin_api_integration(client, auth_headers):
    """Verify /api/portfolio/margins endpoint provides structured data consumed by Funds widget."""
    response = client.get("/api/portfolio/margins", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()["data"]["margins"]

    assert "available_cash" in data
    assert "collateral_value" in data
    assert "total_margin_available" in data
    assert "total_margin_used" in data
    assert "margin_utilization_percent" in data


def test_terminal_execution_mode_api_roundtrip(client, auth_headers):
    """Verify /api/orders/mode endpoint integrates with shell ExecutionMode switching."""
    # 1. Switch to PAPER mode
    resp1 = client.post(
        "/api/orders/mode",
        data=json.dumps({"mode": "PAPER"}),
        headers=auth_headers,
    )
    assert resp1.status_code == 200
    assert resp1.get_json()["data"]["execution_mode"] == "PAPER"

    # 2. Check /api/orders/status reflects PAPER
    status_resp = client.get("/api/orders/status")
    assert status_resp.status_code == 200
    assert status_resp.get_json()["data"]["execution_mode"] == "PAPER"

    # 3. Switch back to DISABLED for safety
    resp2 = client.post(
        "/api/orders/mode",
        data=json.dumps({"mode": "DISABLED"}),
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    assert resp2.get_json()["data"]["execution_mode"] == "DISABLED"
