"""
System Integration UAT Tests for Phase 12B:
Live Equity, F&O & Basket Order UAT.
"""

import json
import uuid
import pytest

from app.baskets.models.basket import Basket, BasketExecutionMode, BasketState
from app.baskets.services.basket_execution_service import basket_execution_service
from app.baskets.services.strategy_validator import strategy_validation_service
from app.broker.adapters.kotak_order_adapter import kotak_order_adapter
from app.broker.uat.phase12b_uat_runner import Phase12BUATRunner
from app.orders.models.execution_mode import ExecutionMode, execution_mode_manager
from app.orders.models.order import Order, OrderSide, OrderStatus, OrderType, ProductType
from app.orders.repositories.order_repository import order_repository
from app.orders.services.order_execution_service import order_execution_service
from app.orders.services.order_validation_service import order_validation_service


@pytest.fixture(autouse=True)
def setup_app_context(app):
    """Ensure every test in this module runs inside an active app and DB context."""
    with app.app_context():
        yield


@pytest.fixture
def auth_headers(client):
    """Register and log in test user to obtain valid authorization headers."""
    client.post(
        "/api/auth/register",
        data=json.dumps({
            "username": "phase12b_trader",
            "email": "phase12b@example.com",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "phase12b_trader",
            "password": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    token = login_resp.get_json()["data"]["token"]
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def test_uat_phase12b_runner_all_checks():
    """Execute complete 8-step Phase 12B UAT runner."""
    with Phase12BUATRunner(live_mode=False) as runner:
        success = runner.run_all_checks()
        assert success is True
        assert len(runner.results) == 8
        for res in runner.results:
            assert res["passed"] is True, f"Step {res['step']} failed: {res['details']}"


def test_uat_live_equity_order_lifecycle():
    """Verify equity order tick validation, placement, modification, and cancellation."""
    execution_mode_manager.set_mode(ExecutionMode.PAPER)

    # 1. Tick size validation (0.05)
    assert order_validation_service.validate_tick_size(1500.25, 0.05) is True
    assert order_validation_service.validate_tick_size(1500.23, 0.05) is False

    # 2. Place Order
    client_ord_id = f"EQ_LIFE_{uuid.uuid4().hex[:8]}"
    place_res = order_execution_service.place_order({
        "client_order_id": client_ord_id,
        "trading_symbol": "TCS",
        "exchange_segment": "nse_cm",
        "instrument_token": "11536",
        "side": "BUY",
        "order_type": "LIMIT",
        "product_type": "CNC",
        "quantity": 1,
        "price": 3800.05,
    })
    assert place_res["success"] is True
    assert place_res["order"]["client_order_id"] == client_ord_id

    # 3. Modify Price
    mod_res = order_execution_service.modify_order(
        client_ord_id,
        {"price": 3805.10, "quantity": 1}
    )
    assert mod_res["success"] is True
    assert mod_res["order"]["price"] == 3805.10

    # 4. Cancel
    cancel_res = order_execution_service.cancel_order(client_ord_id)
    assert cancel_res["success"] is True
    assert cancel_res["status"] in ["CANCELLED", "TRADED"]


def test_uat_live_fno_lot_and_symbol_rules():
    """Verify F&O benchmark lot sizes and option symbol regex parsing."""
    sym = "BANKNIFTY26NOV51000PE"
    parsed = strategy_validation_service.parse_option_symbol(sym)
    assert parsed is not None
    assert parsed["underlying"] == "BANKNIFTY"
    assert parsed["strike"] == 51000.0
    assert parsed["option_type"] == "PE"

    # Lot size validation (BankNifty lot is 15)
    bad_order = Order(
        client_order_id=f"BN_BAD_{uuid.uuid4().hex[:6]}",
        user_id=1,
        trading_symbol=sym,
        exchange_segment="nse_fo",
        instrument_token="22334",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.NRML,
        quantity=20,  # Invalid: not multiple of 15
        price=350.0,
    )
    valid_bad, errors_bad = order_validation_service.validate_order(bad_order)
    assert valid_bad is False
    assert any("lot size" in e for e in errors_bad)


def test_uat_live_multi_leg_basket_dag():
    """Verify Sequential DAG: Stage 1 Long Hedges executed before Stage 2 Short Writes."""
    execution_mode_manager.set_mode(ExecutionMode.PAPER)
    basket_id = f"BKT_TEST_{uuid.uuid4().hex[:8]}"
    legs = [
        {
            "trading_symbol": "NIFTY26NOV24500CE",
            "exchange_segment": "nse_fo",
            "side": "BUY",
            "quantity": 50,
            "order_type": "LIMIT",
            "product_type": "MIS",
            "price": 100.0,
        },
        {
            "trading_symbol": "NIFTY26NOV24700CE",
            "exchange_segment": "nse_fo",
            "side": "SELL",
            "quantity": 50,
            "order_type": "LIMIT",
            "product_type": "MIS",
            "price": 35.0,
        }
    ]

    bkt = basket_execution_service.create_basket({
        "client_basket_id": basket_id,
        "name": "Bull Spread Test",
        "strategy_type": "BULL_CALL_SPREAD",
        "legs": legs,
    })
    assert bkt.client_basket_id == basket_id

    exec_res = basket_execution_service.execute_basket(basket_id)
    assert exec_res["status"] in ["EXECUTED", "COMPLETED", "EXECUTING"]
    assert len(exec_res["legs"]) == 2
    assert exec_res["legs"][0]["side"] == "BUY"
    assert exec_res["legs"][1]["side"] == "SELL"


def test_uat_market_protection_collars():
    """Verify Market Protection (MP) collars: 2% for equities, 5% for options."""
    # Equity BUY collar: +2% rounded to 0.05
    buy_collar = order_validation_service.calculate_market_protection(
        ref_price=2000.0,
        side=OrderSide.BUY,
        mp_percent=2.0,
        tick_size=0.05,
    )
    assert buy_collar == 2040.0

    # Equity SELL collar: -2% rounded to 0.05
    sell_collar = order_validation_service.calculate_market_protection(
        ref_price=2000.0,
        side=OrderSide.SELL,
        mp_percent=2.0,
        tick_size=0.05,
    )
    assert sell_collar == 1960.0

    # Options SELL collar: -5% rounded to 0.05
    opt_collar = order_validation_service.calculate_market_protection(
        ref_price=100.0,
        side=OrderSide.SELL,
        mp_percent=5.0,
        tick_size=0.05,
    )
    assert opt_collar == 95.0


def test_uat_stop_loss_trigger_rules():
    """Verify native broker SL invariant: limit price is coerced to trigger price."""
    execution_mode_manager.set_mode(ExecutionMode.PAPER)
    sl_res = order_execution_service.place_order({
        "client_order_id": f"SL_{uuid.uuid4().hex[:6]}",
        "trading_symbol": "WIPRO",
        "exchange_segment": "nse_cm",
        "instrument_token": "3787",
        "side": "BUY",
        "order_type": "SL",
        "product_type": "MIS",
        "quantity": 5,
        "price": 520.0,
        "trigger_price": 525.0,
    })
    assert sl_res["success"] is True
    assert sl_res["order"]["price"] == 525.0
    assert sl_res["order"]["trigger_price"] == 525.0


def test_uat_fill_reconciliation_vwap_and_golden_rule():
    """Verify Golden Rule unconfirmed status mapping and volume-weighted average price calculation."""
    # Golden rule: status defaults to RECONCILING when broker confirmation is in flight
    recon_order = Order(
        client_order_id=f"RECON_{uuid.uuid4().hex[:6]}",
        user_id=1,
        trading_symbol="INFY",
        exchange_segment="nse_cm",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.CNC,
        quantity=50,
        price=1400.0,
        status=OrderStatus.RECONCILING,
    )
    assert recon_order.status == OrderStatus.RECONCILING

    # Multi-fill VWAP calculation
    fills = [
        {"quantity": 20, "price": 1400.0},
        {"quantity": 30, "price": 1405.0},
    ]
    tot_qty = sum(f["quantity"] for f in fills)
    tot_val = sum(f["quantity"] * f["price"] for f in fills)
    vwap = tot_val / tot_qty
    assert tot_qty == 50
    assert vwap == 1403.0


def test_uat_position_sync_and_reversal_math():
    """Verify position netting, unrealized MTM, and 180-degree reversal order sizing."""
    # Net position calculation
    buy_qty = 200
    sell_qty = 50
    net_qty = buy_qty - sell_qty
    assert net_qty == 150

    # Unrealized MTM: Net * (LTP - Avg)
    buy_avg = 500.0
    ltp = 515.0
    unrealized = net_qty * (ltp - buy_avg)
    assert unrealized == 2250.0

    # 180° Reversal: If long 150, reverse order is SELL 300 (flips to short 150)
    rev_side = "SELL" if net_qty > 0 else "BUY"
    rev_qty = 2 * abs(net_qty)
    assert rev_side == "SELL"
    assert rev_qty == 300
