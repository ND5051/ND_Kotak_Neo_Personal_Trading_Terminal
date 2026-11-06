"""
Unit tests for Order Risk Service.
Phase 7: Order Domain Foundation.
"""

from unittest.mock import MagicMock

from app.orders.models.order import (
    Order,
    OrderSide,
    OrderType,
    ProductType,
)
from app.orders.services.order_risk_service import OrderRiskService
from app.portfolio.models.holding import Holding
from app.portfolio.models.margin import MarginSummary
from app.portfolio.models.portfolio_summary import PortfolioSummary


def test_order_risk_margin_sufficiency():
    """Verify margin calculation and available cash coverage."""
    risk_svc = OrderRiskService()

    # Buy order requiring 100 * 2000 = ₹2,00,000 (+5% buffer = ₹2,10,000)
    order = Order(
        client_order_id="risk-margin-1",
        user_id=1,
        instrument_token="26000",
        exchange_segment="nse_cm",
        trading_symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.CNC,
        quantity=100,
        price=2000.00,
    )

    # Cash insufficient (only ₹1,00,000 available)
    approved, meta = risk_svc.evaluate_risk(order, available_cash=100000.0)
    assert approved is False
    assert any("Insufficient funds" in v for v in meta["violations"])

    # Cash sufficient (₹3,00,000 available)
    approved, meta = risk_svc.evaluate_risk(order, available_cash=300000.0)
    assert approved is True
    assert meta["risk_status"] == "APPROVED"


def test_order_risk_max_order_value_ceiling():
    """Verify rejection when order value exceeds ₹5 Lakh limit."""
    risk_svc = OrderRiskService()

    # Order value: 1000 * 600 = ₹6,00,000 (> ₹5,00,000 limit)
    large_order = Order(
        client_order_id="risk-val-1",
        user_id=1,
        instrument_token="11536",
        exchange_segment="nse_cm",
        trading_symbol="TCS",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        product_type=ProductType.MIS,
        quantity=1000,
        price=600.00,
    )

    approved, meta = risk_svc.evaluate_risk(large_order, available_cash=10000000.0)
    assert approved is False
    assert any("exceeds maximum single order limit" in v for v in meta["violations"])


def test_order_risk_short_selling_delivery_check():
    """Verify short selling rejection in CNC when user lacks Demat custody."""
    mock_portfolio = MagicMock()
    # User holds only 20 shares of INFY
    mock_portfolio.get_holdings.return_value = [
        Holding(
            instrument_token="1594",
            exchange_segment="nse_cm",
            trading_symbol="INFY",
            isin="INE009A01021",
            total_quantity=20,
            settled_quantity=20,
            t1_quantity=0,
            pledged_quantity=0,
            average_price=1400.0,
            invested_value=28000.0,
            current_price=1500.0,
            current_value=30000.0,
            unrealized_pnl=2000.0,
            unrealized_pnl_percent=7.14,
            close_price=1450.0,
            day_pnl=1000.0,
            day_pnl_percent=3.45,
        )
    ]
    mock_portfolio.get_summary.return_value = PortfolioSummary(total_portfolio_pnl=0.0)

    risk_svc = OrderRiskService(portfolio=mock_portfolio)

    # Attempt to sell 50 shares of INFY in CNC (exceeds 20 available)
    sell_order = Order(
        client_order_id="risk-short-1",
        user_id=1,
        instrument_token="1594",
        exchange_segment="nse_cm",
        trading_symbol="INFY",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        product_type=ProductType.CNC,
        quantity=50,
        price=1500.00,
    )

    approved, meta = risk_svc.evaluate_risk(sell_order, available_cash=500000.0)
    assert approved is False
    assert any("Short selling prohibited in CNC" in v for v in meta["violations"])
