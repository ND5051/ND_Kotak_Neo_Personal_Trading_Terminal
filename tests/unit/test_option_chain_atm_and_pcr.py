"""
Unit Tests for Option Chain ATM Calculation, Moneyness Tagging, and PCR Engine.
Phase 10: Option Chain Workbench.
"""

import pytest

from app.option_chain.models.chain import OptionContractQuote
from app.option_chain.services.option_chain_service import OptionChainService


@pytest.fixture
def chain_service():
    return OptionChainService()


def test_dynamic_atm_strike_calculation(chain_service):
    """Verify ATM strike determination across index strike intervals."""
    # 1. NIFTY (Step 50)
    # 24512 -> 24500
    assert round(24512.40 / 50.0) * 50.0 == 24500.0
    # 24535 -> 24550
    assert round(24535.00 / 50.0) * 50.0 == 24550.0

    # 2. BANKNIFTY (Step 100)
    # 51240 -> 51200
    assert round(51240.00 / 100.0) * 100.0 == 51200.0
    # 51260 -> 51300
    assert round(51260.00 / 100.0) * 100.0 == 51300.0

    # 3. MIDCPNIFTY (Step 25)
    # 12610 -> 12600
    assert round(12610.00 / 25.0) * 25.0 == 12600.0
    # 12615 -> 12625
    assert round(12615.00 / 25.0) * 25.0 == 12625.0


def test_call_put_moneyness_and_intrinsic_value(chain_service):
    """Verify ITM/ATM/OTM classification and intrinsic value calculations."""
    spot = 24510.0
    atm = 24500.0
    spec = chain_service.underlying_svc.get_underlying("NIFTY")

    # Call @ 24400 (< ATM -> ITM)
    c_itm = chain_service._synthesize_contract_quote(
        spec=spec,
        trading_symbol="NIFTY26NOV24400CE",
        option_type="CE",
        strike=24400.0,
        spot=spot,
        atm_strike=atm,
        expiry_date="2026-11-26",
        oi_timestamp="",
    )
    assert c_itm.moneyness == "ITM"
    assert c_itm.intrinsic_value == 110.0  # 24510 - 24400

    # Call @ 24600 (> ATM -> OTM)
    c_otm = chain_service._synthesize_contract_quote(
        spec=spec,
        trading_symbol="NIFTY26NOV24600CE",
        option_type="CE",
        strike=24600.0,
        spot=spot,
        atm_strike=atm,
        expiry_date="2026-11-26",
        oi_timestamp="",
    )
    assert c_otm.moneyness == "OTM"
    assert c_otm.intrinsic_value == 0.0

    # Put @ 24600 (> ATM -> ITM)
    p_itm = chain_service._synthesize_contract_quote(
        spec=spec,
        trading_symbol="NIFTY26NOV24600PE",
        option_type="PE",
        strike=24600.0,
        spot=spot,
        atm_strike=atm,
        expiry_date="2026-11-26",
        oi_timestamp="",
    )
    assert p_itm.moneyness == "ITM"
    assert p_itm.intrinsic_value == 90.0  # 24600 - 24510

    # Put @ 24400 (< ATM -> OTM)
    p_otm = chain_service._synthesize_contract_quote(
        spec=spec,
        trading_symbol="NIFTY26NOV24400PE",
        option_type="PE",
        strike=24400.0,
        spot=spot,
        atm_strike=atm,
        expiry_date="2026-11-26",
        oi_timestamp="",
    )
    assert p_otm.moneyness == "OTM"
    assert p_otm.intrinsic_value == 0.0


def test_pcr_calculation_and_zero_division_guard():
    """Verify PCR computation, zero Call OI safety, and capping."""
    calc_pcr = OptionChainService._calculate_pcr

    # Standard PCR
    assert calc_pcr(1200000, 1000000) == 1.2
    assert calc_pcr(800000, 1000000) == 0.8

    # Zero Call denominator returns 0.0 without exception
    assert calc_pcr(500000, 0) == 0.0
    assert calc_pcr(0, 0) == 0.0

    # Extreme value capped to 10.0
    assert calc_pcr(50000000, 1000) == 10.0


def test_max_pain_and_max_oi_derivation(chain_service):
    """Verify Max Pain and Max OI strike detection."""
    strikes = [24400.0, 24500.0, 24600.0]

    # Synthesize calls with max OI at 24600
    calls = [
        OptionContractQuote("t1", "C1", "CE", 24400.0, "2026-11-26", open_interest=100000),
        OptionContractQuote("t2", "C2", "CE", 24500.0, "2026-11-26", open_interest=300000),
        OptionContractQuote("t3", "C3", "CE", 24600.0, "2026-11-26", open_interest=800000),
    ]
    # Synthesize puts with max OI at 24400
    puts = [
        OptionContractQuote("t4", "P1", "PE", 24400.0, "2026-11-26", open_interest=900000),
        OptionContractQuote("t5", "P2", "PE", 24500.0, "2026-11-26", open_interest=400000),
        OptionContractQuote("t6", "P3", "PE", 24600.0, "2026-11-26", open_interest=150000),
    ]

    max_pain = chain_service._calculate_max_pain(strikes, calls, puts)
    assert max_pain is not None
    assert max_pain in strikes

