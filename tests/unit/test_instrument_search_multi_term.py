import pytest
from app.market_watch.models.instrument import Instrument
from app.market_watch.repositories.instrument_repository import InstrumentRepository

@pytest.fixture
def repo():
    r = InstrumentRepository()
    test_instruments = [
        Instrument(
            instrument_token="55406",
            exchange_segment="nse_fo",
            trading_symbol="NIFTY27DEC3000CE",
            symbol_name="NIFTY",
            display_name="NIFTY 30-DEC-27 3000 CE",
            lot_size=65,
            tick_size=0.05,
            instrument_type="OPTIDX",
        ),
        Instrument(
            instrument_token="35346",
            exchange_segment="nse_fo",
            trading_symbol="NIFTY27DEC30000CE",
            symbol_name="NIFTY",
            display_name="NIFTY 30-DEC-27 30000 CE",
            lot_size=65,
            tick_size=0.05,
            instrument_type="OPTIDX",
        ),
        Instrument(
            instrument_token="64298",
            exchange_segment="nse_fo",
            trading_symbol="NIFTY26DEC27900PE",
            symbol_name="NIFTY",
            display_name="NIFTY 31-DEC-26 27900 PE",
            lot_size=65,
            tick_size=0.05,
            instrument_type="OPTIDX",
        ),
        Instrument(
            instrument_token="11536",
            exchange_segment="nse_cm",
            trading_symbol="TCS-EQ",
            symbol_name="TCS",
            display_name="Tata Consultancy Services Ltd",
            lot_size=1,
            tick_size=0.05,
            instrument_type="EQ",
        ),
        Instrument(
            instrument_token="99999",
            exchange_segment="nse_fo",
            trading_symbol="TCS26DECFUT",
            symbol_name="TCS",
            display_name="TCS 31-DEC-26 FUT",
            lot_size=175,
            tick_size=0.05,
            instrument_type="FUTSTK",
        ),
        Instrument(
            instrument_token="588364",
            exchange_segment="mcx_fo",
            trading_symbol="GOLD31AUG27149500PE",
            symbol_name="GOLD",
            display_name="GOLD 31-AUG-27 149500 PE",
            lot_size=1,
            tick_size=1.0,
            instrument_type="OPTFUT",
        ),
        Instrument(
            instrument_token="590789",
            exchange_segment="mcx_fo",
            trading_symbol="SILVERM23APR27167000CE",
            symbol_name="SILVERM",
            display_name="SILVERM 23-APR-27 167000 CE",
            lot_size=5,
            tick_size=1.0,
            instrument_type="OPTFUT",
        ),
    ]
    r.load_instruments(test_instruments)
    return r

def test_multi_term_search_nifty_dec_2027(repo):
    results = repo.search("nifty dec 2027")
    assert len(results) >= 2
    # The Dec 2027 instruments must be ranked first
    symbols = [x.trading_symbol for x in results]
    assert "NIFTY27DEC30000CE" in symbols
    assert "NIFTY27DEC3000CE" in symbols
    # NIFTY27DEC should be ranked before NIFTY26DEC
    assert symbols[0].startswith("NIFTY27DEC")

def test_multi_term_search_tcs_fut(repo):
    results = repo.search("tcs fut")
    assert len(results) == 1
    assert results[0].trading_symbol == "TCS26DECFUT"

def test_segment_filter(repo):
    results_cm = repo.search("tcs", segment="nse_cm")
    assert len(results_cm) == 1
    assert results_cm[0].trading_symbol == "TCS-EQ"

    results_fo = repo.search("tcs", segment="nse_fo")
    assert len(results_fo) == 1
    assert results_fo[0].trading_symbol == "TCS26DECFUT"

def test_mcx_commodity_search(repo):
    results_gold = repo.search("gold")
    assert len(results_gold) == 1
    assert results_gold[0].trading_symbol == "GOLD31AUG27149500PE"
    assert results_gold[0].exchange_segment == "mcx_fo"

    results_mcx = repo.search("silver", segment="mcx_fo")
    assert len(results_mcx) == 1
    assert results_mcx[0].trading_symbol == "SILVERM23APR27167000CE"
