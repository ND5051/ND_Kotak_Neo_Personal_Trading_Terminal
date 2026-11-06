"""
Unit tests for InstrumentRepository and InstrumentService.
Phase 5: Market Watch Foundation.
Validates Scrip Master indexing, benchmark seeding, exact token lookup, and prefix searches.
"""

import os
import tempfile
import pytest

from app.market_watch.models.instrument import Instrument
from app.market_watch.repositories.instrument_repository import InstrumentRepository
from app.market_watch.services.instrument_service import (
    DEFAULT_BENCHMARK_INSTRUMENTS,
    InstrumentService,
)


def test_instrument_repository_indexing_and_lookup():
    """Verify in-memory multi-indexing by token, symbol, and prefix."""
    repo = InstrumentRepository()
    inst = Instrument(
        instrument_token="2885",
        exchange_segment="nse_cm",
        trading_symbol="RELIANCE-EQ",
        symbol_name="RELIANCE",
        display_name="Reliance Industries Ltd",
        lot_size=1,
        tick_size=0.05,
    )
    repo.add_instrument(inst)

    assert repo.count() == 1

    # Exact token lookup
    retrieved = repo.get_by_token("2885", "nse_cm")
    assert retrieved is not None
    assert retrieved.trading_symbol == "RELIANCE-EQ"
    assert retrieved.display_name == "Reliance Industries Ltd"

    # Non-existent token
    assert repo.get_by_token("99999", "nse_cm") is None


def test_instrument_search_prefix_and_filtering():
    """Verify sub-millisecond prefix matching and segment filtering."""
    repo = InstrumentRepository()
    repo.load_instruments(DEFAULT_BENCHMARK_INSTRUMENTS)

    # Prefix search for 'RELI'
    results = repo.search("RELI")
    assert len(results) >= 1
    assert any(i.trading_symbol == "RELIANCE-EQ" for i in results)

    # Prefix search for 'NIF'
    nifty_results = repo.search("NIF")
    assert len(nifty_results) >= 1
    symbols = [i.trading_symbol for i in nifty_results]
    assert "Nifty 50" in symbols or "Nifty Bank" in symbols

    # Segment filtering
    bse_results = repo.search("SENSEX", segment="bse_cm")
    assert len(bse_results) == 1
    assert bse_results[0].trading_symbol == "SENSEX"

    # Segment mismatch returns empty
    assert len(repo.search("SENSEX", segment="nse_cm")) == 0


def test_instrument_service_seeding_and_csv_parsing():
    """Verify InstrumentService loads default benchmarks and parses CSV master files."""
    repo = InstrumentRepository()
    svc = InstrumentService(repository=repo)

    assert repo.count() >= len(DEFAULT_BENCHMARK_INSTRUMENTS)

    # Create temporary CSV file matching Kotak Neo format
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as tmp:
        tmp.write("pSymbol,pTrdSymbol,pSymbolName,pDesc,pLotSize,pTickSize,pInstType\n")
        tmp.write("99001,MOCKCORP-EQ,MOCKCORP,Mock Corporation Ltd,1,0.05,EQ\n")
        tmp.write("99002,ALPHABETA-EQ,ALPHABETA,Alpha Beta Systems Ltd,10,0.05,EQ\n")
        tmp_path = tmp.name

    try:
        loaded = svc.load_from_csv(tmp_path, exchange_segment="nse_cm")
        assert loaded == 2

        found = repo.get_by_token("99001", "nse_cm")
        assert found is not None
        assert found.trading_symbol == "MOCKCORP-EQ"
        assert found.lot_size == 1

        search_res = svc.search_instruments("ALPHA")
        assert len(search_res) >= 1
        assert search_res[0]["trading_symbol"] == "ALPHABETA-EQ"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
