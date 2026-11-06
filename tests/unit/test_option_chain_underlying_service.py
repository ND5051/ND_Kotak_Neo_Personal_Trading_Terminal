"""
Unit Tests for Underlying Service and User Favourites.
Phase 10: Option Chain Workbench.
"""

import pytest

from app.option_chain.services.underlying_service import UnderlyingService


@pytest.fixture
def service():
    return UnderlyingService()


def test_underlying_catalog_lookup(service):
    """Verify supported benchmark indices and equities exist in catalog."""
    nifty = service.get_underlying("NIFTY")
    assert nifty is not None
    assert nifty.lot_size == 25
    assert nifty.strike_step == 50.0

    bn = service.get_underlying("BANKNIFTY")
    assert bn is not None
    assert bn.lot_size == 15
    assert bn.strike_step == 100.0

    rel = service.get_underlying("RELIANCE")
    assert rel is not None
    assert rel.lot_size == 250
    assert rel.is_index is False


def test_user_favourites_toggle(service):
    """Verify pinning, unpinning, and querying user favourite underlyings."""
    user_id = 999

    # Initial favourites (defaults to NIFTY, BANKNIFTY)
    favs = service.get_favourites(user_id=user_id)
    fav_symbols = [f["symbol"] for f in favs]
    assert "NIFTY" in fav_symbols
    assert "BANKNIFTY" in fav_symbols

    # Pin RELIANCE
    assert service.toggle_favourite(user_id=user_id, symbol="RELIANCE", is_favourite=True) is True
    favs_after_add = service.get_favourites(user_id=user_id)
    assert any(f["symbol"] == "RELIANCE" for f in favs_after_add)

    # Unpin NIFTY
    assert service.toggle_favourite(user_id=user_id, symbol="NIFTY", is_favourite=False) is True
    favs_after_del = service.get_favourites(user_id=user_id)
    assert not any(f["symbol"] == "NIFTY" for f in favs_after_del)

    # Invalid symbol toggle returns False
    assert service.toggle_favourite(user_id=user_id, symbol="NON_EXISTENT", is_favourite=True) is False


def test_spot_ltp_resolution(service):
    """Verify Spot LTP returns non-zero positive prices."""
    spot_nifty = service.get_spot_ltp("NIFTY")
    assert spot_nifty > 20000.0

    spot_bn = service.get_spot_ltp("BANKNIFTY")
    assert spot_bn > 40000.0

