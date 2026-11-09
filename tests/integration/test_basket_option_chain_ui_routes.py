"""
Integration tests for Phase 11D: Basket Builder UI & Option Chain Workbench UI.
Verifies Option Chain symmetrical strike matrix, PCR and Max Pain widgets,
Quick Strategy shortcuts, Basket Builder leg grid, Dependency DAG visualization,
Risk and Exposure calculations, Pre-flight validation, Sequential execution flow,
Draft auto-save elements, and Unsaved Changes Warning modal.
"""

import json
import pytest

from app.orders.models.execution_mode import ExecutionMode, execution_mode_manager


@pytest.fixture
def auth_headers(client):
    """Register and log in test user to obtain valid authorization headers."""
    client.post(
        "/api/auth/register",
        data=json.dumps({
            "username": "phase11d_user",
            "email": "phase11d@example.com",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "phase11d_user",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    token = login_resp.get_json()["data"]["token"]
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def test_terminal_loads_phase11d_components(client):
    """Verify /terminal loads Option Chain, Basket Builder, Docked Drawer, and Modals."""
    response = client.get("/terminal")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # 1. Option Chain View & Controls
    assert "option-chain-container" in html
    assert "oc-underlying-select" in html
    assert "oc-expiry-select" in html
    assert "oc-preset-select" in html
    assert "oc-refresh-btn" in html
    assert "oc-fav-btn" in html
    assert "oc-sentiment-bar" in html
    assert "oc-pcr-oi" in html
    assert "oc-max-pain" in html
    assert "oc-matrix-table" in html
    assert 'data-oc-strat="BULL_CALL_SPREAD"' in html
    assert 'data-oc-strat="BEAR_PUT_SPREAD"' in html
    assert 'data-oc-strat="STRADDLE"' in html
    assert 'data-oc-strat="STRANGLE"' in html
    assert 'data-oc-strat="IRON_CONDOR"' in html
    assert 'data-oc-strat="IRON_BUTTERFLY"' in html
    assert "oc-open-basket-btn" in html

    # 2. Basket Builder View & Controls
    assert "basket-builder-container" in html
    assert "basket-templates-card" in html
    assert 'data-template="BULL_CALL_SPREAD"' in html
    assert 'data-template="BEAR_PUT_SPREAD"' in html
    assert 'data-template="STRADDLE"' in html
    assert 'data-template="STRANGLE"' in html
    assert 'data-template="IRON_CONDOR"' in html
    assert 'data-template="IRON_BUTTERFLY"' in html
    assert 'data-template="COVERED_CALL"' in html
    assert 'data-template="PROTECTIVE_PUT"' in html
    assert "lot-multiplier-display" in html
    assert "basket-legs-table" in html
    assert "basket-add-manual-leg-btn" in html
    assert "basket-clear-btn" in html
    assert "basket-draft-status" in html

    # 3. Dependency DAG & Pre-Flight Validation
    assert "basket-dag-card" in html
    assert "dag-pipeline-container" in html
    assert "dag-stage-1-nodes" in html
    assert "dag-stage-2-nodes" in html
    assert "basket-validation-card" in html
    assert "btn-validate-basket" in html
    assert "chk-syntax" in html
    assert "chk-expiry" in html
    assert "chk-ratio" in html
    assert "chk-margin" in html
    assert "chk-risk" in html

    # 4. Risk, Exposure & Execution Controls
    assert "risk-gross-margin" in html
    assert "risk-combined-margin" in html
    assert "risk-margin-savings" in html
    assert "risk-avail-cash" in html
    assert "risk-net-premium" in html
    assert "risk-gross-notional" in html
    assert "risk-max-profit" in html
    assert "risk-max-loss" in html
    assert "risk-breakeven" in html
    assert "basket-mode-indicator" in html
    assert "btn-execute-basket" in html
    assert "basket-exec-monitor" in html
    assert "monitor-progress-bar" in html
    assert "btn-abort-basket" in html

    # 5. Modals & Docked Drawer
    assert "unsaved-changes-modal" in html
    assert "unsaved-modal-confirm" in html
    assert "basket-docked-drawer" in html
    assert "drawer-legs-container" in html
    assert "drawer-goto-basket-btn" in html


def test_phase11d_static_assets(client):
    """Verify CSS and JavaScript assets load with HTTP 200."""
    css_resp = client.get("/static/css/baskets_option_chain.css")
    assert css_resp.status_code == 200
    assert "oc-matrix-table" in css_resp.data.decode("utf-8")
    assert "dag-pipeline" in css_resp.data.decode("utf-8")

    js_oc_resp = client.get("/static/js/option_chain.js")
    assert js_oc_resp.status_code == 200
    assert "OptionChainController" in js_oc_resp.data.decode("utf-8")

    js_bb_resp = client.get("/static/js/basket_builder.js")
    assert js_bb_resp.status_code == 200
    assert "BasketBuilderController" in js_bb_resp.data.decode("utf-8")
    assert "kotak_neo_basket_draft_v1" in js_bb_resp.data.decode("utf-8")


def test_option_chain_apis_integration(client, auth_headers):
    """Verify option chain REST endpoints powering UI matrix and sentiment bar."""
    # Underlyings
    u_resp = client.get("/api/option-chain/underlyings", headers=auth_headers)
    assert u_resp.status_code == 200
    u_data = u_resp.get_json()["data"]
    symbols = [u["symbol"] for u in u_data["underlyings"]]
    assert "NIFTY" in symbols

    # Expiries
    e_resp = client.get("/api/option-chain/expiries?symbol=NIFTY", headers=auth_headers)
    assert e_resp.status_code == 200
    e_data = e_resp.get_json()["data"]
    expiries = e_data["expiries"]
    assert len(expiries) > 0
    target_expiry = expiries[0]["expiry_date"]

    # Matrix Table Data
    chain_resp = client.get(
        f"/api/option-chain?symbol=NIFTY&expiry={target_expiry}&preset=ATM_10",
        headers=auth_headers
    )
    assert chain_resp.status_code == 200
    chain_data = chain_resp.get_json()["data"]
    assert chain_data["underlying_symbol"] == "NIFTY"
    assert "strikes" in chain_data
    assert len(chain_data["strikes"]) > 0
    assert "call_quote" in chain_data["strikes"][0]
    assert "put_quote" in chain_data["strikes"][0]

    # PCR and Max Pain
    pcr_resp = client.get(
        f"/api/option-chain/pcr?symbol=NIFTY&expiry={target_expiry}",
        headers=auth_headers
    )
    assert pcr_resp.status_code == 200
    pcr_data = pcr_resp.get_json()["data"]
    assert "pcr_oi" in pcr_data
    assert "pcr_volume" in pcr_data


def test_basket_preflight_and_execution_integration(client, auth_headers):
    """Verify pre-flight validation and basket execution API integration."""
    execution_mode_manager.set_mode(ExecutionMode.PAPER)

    legs_payload = [
        {
            "trading_symbol": "NIFTY26NOV24500CE",
            "exchange_segment": "nse_fo",
            "side": "BUY",
            "quantity": 50,
            "order_type": "LIMIT",
            "product_type": "MIS",
            "price": 120.0,
        },
        {
            "trading_symbol": "NIFTY26NOV24700CE",
            "exchange_segment": "nse_fo",
            "side": "SELL",
            "quantity": 50,
            "order_type": "LIMIT",
            "product_type": "MIS",
            "price": 45.0,
        }
    ]

    # Pre-Flight Validation
    val_resp = client.post(
        "/api/baskets/validate",
        data=json.dumps({
            "client_basket_id": "phase11d_val_test_01",
            "name": "Test Bull Call Spread",
            "strategy_type": "BULL_CALL_SPREAD",
            "available_margin": 300000.0,
            "legs": legs_payload
        }),
        headers=auth_headers
    )
    assert val_resp.status_code == 200
    val_data = val_resp.get_json()["data"]
    assert val_data["valid"] is True
    assert val_data["strategy_syntax_passed"] is True
    assert val_data["risk_checks_passed"] is True
    assert "margin_snapshot" in val_data

    # Basket Creation
    create_resp = client.post(
        "/api/baskets",
        data=json.dumps({
            "client_basket_id": "phase11d_exec_bkt_01",
            "name": "Integration Test Basket",
            "strategy_type": "BULL_CALL_SPREAD",
            "legs": legs_payload
        }),
        headers=auth_headers
    )
    assert create_resp.status_code == 201
    created_basket = create_resp.get_json()["data"]
    basket_id = created_basket["client_basket_id"]
    assert basket_id == "phase11d_exec_bkt_01"
    assert created_basket["status"] == "DRAFT"

    # Basket Execution in PAPER Mode
    exec_resp = client.post(
        f"/api/baskets/{basket_id}/execute",
        headers=auth_headers
    )
    assert exec_resp.status_code == 200
    exec_data = exec_resp.get_json()["data"]
    assert exec_data["client_basket_id"] == basket_id
    assert exec_data["status"] in ["EXECUTING", "COMPLETED", "EXECUTED"]
    assert len(exec_data["legs"]) == 2


def test_basket_validation_error_on_empty_legs(client, auth_headers):
    """Verify validation responds with errors when legs are missing."""
    val_resp = client.post(
        "/api/baskets/validate",
        data=json.dumps({
            "client_basket_id": "empty_bkt_val",
            "strategy_type": "CUSTOM",
            "legs": []
        }),
        headers=auth_headers
    )
    assert val_resp.status_code in [200, 400]
    data = val_resp.get_json()
    if val_resp.status_code == 200:
        assert data["data"]["valid"] is False
    else:
        assert data["status"] == "error"
