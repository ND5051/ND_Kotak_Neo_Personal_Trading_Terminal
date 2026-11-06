"""
Unit Tests for Option Chain Domain Models.
Phase 10: Option Chain Workbench.
"""

import pytest

from app.option_chain.models.chain import (
    ExpiryInfo,
    OptionChainSnapshot,
    OptionContractQuote,
    OptionStrikeRow,
)
from app.option_chain.models.underlying import (
    StrikeFilterPreset,
    UnderlyingSpecification,
)


def test_strike_filter_preset_parsing_and_window_size():
    """Verify StrikeFilterPreset parsing from strings/integers and window sizes."""
    assert StrikeFilterPreset.ATM_5.window_size == 5
    assert StrikeFilterPreset.ATM_10.window_size == 10
    assert StrikeFilterPreset.ATM_15.window_size == 15
    assert StrikeFilterPreset.ATM_20.window_size == 20

    # Parsing from integer
    assert StrikeFilterPreset.from_value(5) == StrikeFilterPreset.ATM_5
    assert StrikeFilterPreset.from_value(10) == StrikeFilterPreset.ATM_10
    assert StrikeFilterPreset.from_value(15) == StrikeFilterPreset.ATM_15
    assert StrikeFilterPreset.from_value(20) == StrikeFilterPreset.ATM_20

    # Parsing from strings
    assert StrikeFilterPreset.from_value("ATM_5") == StrikeFilterPreset.ATM_5
    assert StrikeFilterPreset.from_value("ATM±10") == StrikeFilterPreset.ATM_10
    assert StrikeFilterPreset.from_value("ATM_15") == StrikeFilterPreset.ATM_15
    assert StrikeFilterPreset.from_value("ATM+-20") == StrikeFilterPreset.ATM_20

    # Default fallback
    assert StrikeFilterPreset.from_value("UNKNOWN_PRESET") == StrikeFilterPreset.ATM_10


def test_underlying_specification_serialization():
    """Verify UnderlyingSpecification properties and dictionary output."""
    spec = UnderlyingSpecification(
        symbol="NIFTY",
        display_name="Nifty 50 Index",
        exchange_segment="nse_cm",
        derivatives_segment="nse_fo",
        spot_instrument_token="26000",
        spot_index_name="Nifty 50",
        strike_step=50.0,
        lot_size=25,
    )
    d = spec.to_dict(spot_ltp=24500.50, is_favourite=True)
    assert d["symbol"] == "NIFTY"
    assert d["strike_step"] == 50.0
    assert d["lot_size"] == 25
    assert d["spot_ltp"] == 24500.50
    assert d["is_favourite"] is True


def test_option_contract_quote_serialization_and_timestamps():
    """Verify OptionContractQuote serialization including oi_source_timestamp."""
    quote = OptionContractQuote(
        instrument_token="45210",
        trading_symbol="NIFTY26NOV24500CE",
        option_type="CE",
        strike_price=24500.0,
        expiry_date="2026-11-26",
        ltp=150.25,
        bid_price=150.10,
        ask_price=150.35,
        open_interest=5000000,
        change_in_oi=250000,
        percent_change_in_oi=5.26,
        volume=1200000,
        total_traded_value=180000000.0,
        oi_source_timestamp="2026-11-06T10:00:00Z",
        moneyness="ITM",
        intrinsic_value=12.40,
        is_max_oi=True,
    )

    d = quote.to_dict()
    assert d["trading_symbol"] == "NIFTY26NOV24500CE"
    assert d["ltp"] == 150.25
    assert d["open_interest"] == 5000000
    assert d["oi_source_timestamp"] == "2026-11-06T10:00:00Z"
    assert d["moneyness"] == "ITM"
    assert d["is_max_oi"] is True


def test_option_chain_snapshot_serialization():
    """Verify top-level OptionChainSnapshot serialization with dual timestamps and presets."""
    row = OptionStrikeRow(
        strike_price=24500.0,
        is_atm=True,
        distance_from_spot=0.0,
    )
    snap = OptionChainSnapshot(
        underlying_symbol="NIFTY",
        spot_price=24500.0,
        expiry_date="2026-11-26",
        atm_strike=24500.0,
        preset=StrikeFilterPreset.ATM_10,
        pcr_oi=1.125,
        strikes=[row],
        source_timestamp="2026-11-06T10:00:01Z",
        oi_source_timestamp="2026-11-06T10:00:00Z",
    )

    d = snap.to_dict()
    assert d["underlying_symbol"] == "NIFTY"
    assert d["atm_strike"] == 24500.0
    assert d["preset"] == "ATM_10"
    assert d["pcr_oi"] == 1.125
    assert d["source_timestamp"] == "2026-11-06T10:00:01Z"
    assert d["oi_source_timestamp"] == "2026-11-06T10:00:00Z"
    assert "retrieved_timestamp" in d
    assert d["total_strikes"] == 1

