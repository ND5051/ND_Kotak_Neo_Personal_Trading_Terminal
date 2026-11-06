"""
Instrument Service & Scrip Master Synchronizer.
Phase 5: Market Watch Foundation.
Coordinates downloading, parsing, and in-memory indexing of Kotak Neo Scrip Master files.
"""

import csv
from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional

from app.core.audit import AuditCategory, audit_logger
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import SCRIP_MASTER_SYNCED
from app.logging.logger import get_logger
from app.market_watch.models.instrument import Instrument
from app.market_watch.repositories.instrument_repository import (
    InstrumentRepository,
    instrument_repository,
)

logger = get_logger("app.market_watch.services.instrument_service")


# Benchmark Core Instruments seeded automatically on startup
DEFAULT_BENCHMARK_INSTRUMENTS = [
    Instrument(
        instrument_token="26000",
        exchange_segment="nse_cm",
        trading_symbol="Nifty 50",
        symbol_name="NIFTY",
        display_name="Nifty 50 Index",
        instrument_type="INDEX",
    ),
    Instrument(
        instrument_token="26001",
        exchange_segment="nse_cm",
        trading_symbol="Nifty Bank",
        symbol_name="BANKNIFTY",
        display_name="Nifty Bank Index",
        instrument_type="INDEX",
    ),
    Instrument(
        instrument_token="1",
        exchange_segment="bse_cm",
        trading_symbol="SENSEX",
        symbol_name="SENSEX",
        display_name="BSE Sensex Index",
        instrument_type="INDEX",
    ),
    Instrument(
        instrument_token="2885",
        exchange_segment="nse_cm",
        trading_symbol="RELIANCE-EQ",
        symbol_name="RELIANCE",
        display_name="Reliance Industries Limited",
        lot_size=1,
        tick_size=0.05,
        instrument_type="EQ",
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
        instrument_token="1594",
        exchange_segment="nse_cm",
        trading_symbol="INFY-EQ",
        symbol_name="INFY",
        display_name="Infosys Limited",
        lot_size=1,
        tick_size=0.05,
        instrument_type="EQ",
    ),
    Instrument(
        instrument_token="1333",
        exchange_segment="nse_cm",
        trading_symbol="HDFCBANK-EQ",
        symbol_name="HDFCBANK",
        display_name="HDFC Bank Limited",
        lot_size=1,
        tick_size=0.05,
        instrument_type="EQ",
    ),
    Instrument(
        instrument_token="4963",
        exchange_segment="nse_cm",
        trading_symbol="ICICIBANK-EQ",
        symbol_name="ICICIBANK",
        display_name="ICICI Bank Limited",
        lot_size=1,
        tick_size=0.05,
        instrument_type="EQ",
    ),
    Instrument(
        instrument_token="3045",
        exchange_segment="nse_cm",
        trading_symbol="SBIN-EQ",
        symbol_name="SBIN",
        display_name="State Bank of India",
        lot_size=1,
        tick_size=0.05,
        instrument_type="EQ",
    ),
    Instrument(
        instrument_token="3456",
        exchange_segment="nse_cm",
        trading_symbol="TATAMOTORS-EQ",
        symbol_name="TATAMOTORS",
        display_name="Tata Motors Limited",
        lot_size=1,
        tick_size=0.05,
        instrument_type="EQ",
    ),
]


class InstrumentService:
    """
    Coordinates instrument indexing, CSV master parsing, and fuzzy symbol search.
    """

    def __init__(
        self, repository: Optional[InstrumentRepository] = None
    ) -> None:
        self.repository = repository or instrument_repository
        # Ensure benchmark instruments are seeded upon service creation
        if self.repository.count() == 0:
            self.seed_benchmarks()

    def seed_benchmarks(self) -> int:
        """Seed default benchmark indices and blue-chip equities."""
        count = self.repository.load_instruments(DEFAULT_BENCHMARK_INSTRUMENTS)
        logger.info(f"Seeded {count} core benchmark instruments", event="BENCHMARKS_SEEDED")
        return count

    def load_from_csv(
        self, file_path: str, exchange_segment: str
    ) -> int:
        """
        Parse Kotak Neo official CSV scrip master file and index into memory.
        Expected columns: pSymbol/token, pTrdSymbol/trading_symbol, pSymbolName, etc.
        """
        if not os.path.exists(file_path):
            logger.warning(f"Scrip master file not found: {file_path}", event="SCRIP_FILE_MISSING")
            return 0

        instruments: List[Instrument] = []
        try:
            with open(file_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    token = (
                        row.get("pSymbol")
                        or row.get("instrument_token")
                        or row.get("Token")
                        or ""
                    ).strip()
                    trd_symbol = (
                        row.get("pTrdSymbol")
                        or row.get("trading_symbol")
                        or row.get("TradingSymbol")
                        or ""
                    ).strip()
                    sym_name = (
                        row.get("pSymbolName")
                        or row.get("symbol_name")
                        or row.get("Symbol")
                        or trd_symbol
                    ).strip()
                    disp_name = (
                        row.get("pDesc")
                        or row.get("display_name")
                        or row.get("CompanyName")
                        or sym_name
                    ).strip()

                    if not token or not trd_symbol:
                        continue

                    try:
                        lot_size = int(row.get("pLotSize") or row.get("lot_size") or 1)
                    except ValueError:
                        lot_size = 1

                    try:
                        tick_size = float(row.get("pTickSize") or row.get("tick_size") or 0.05)
                    except ValueError:
                        tick_size = 0.05

                    inst_type = (row.get("pInstType") or row.get("instrument_type") or "EQ").strip()

                    instruments.append(
                        Instrument(
                            instrument_token=token,
                            exchange_segment=exchange_segment.lower(),
                            trading_symbol=trd_symbol,
                            symbol_name=sym_name,
                            display_name=disp_name,
                            lot_size=lot_size,
                            tick_size=tick_size,
                            instrument_type=inst_type,
                        )
                    )

            loaded = self.repository.load_instruments(instruments)

            # Audit and notify
            audit_logger.record(
                category=AuditCategory.BROKER,
                action="SCRIP_MASTER_DOWNLOAD",
                actor="instrument_service",
                correlation_id=get_correlation_id(),
                request_id=get_request_id(),
                details={"file": file_path, "segment": exchange_segment, "count": loaded},
            )

            publish(
                SCRIP_MASTER_SYNCED,
                {
                    "total_instruments": self.repository.count(),
                    "segment": exchange_segment,
                    "count": loaded,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            return loaded

        except Exception as e:
            logger.error(f"Error parsing scrip master file {file_path}: {str(e)}", exc_info=True)
            return 0

    def search_instruments(
        self,
        query: str,
        segment: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search instruments and return serialized dictionaries."""
        results = self.repository.search(query=query, segment=segment, limit=limit)
        return [inst.to_dict() for inst in results]

    def get_instrument(
        self, token: str, segment: str
    ) -> Optional[Instrument]:
        """Fetch instrument definition by token and segment."""
        return self.repository.get_by_token(token=token, segment=segment)


# Global Singleton Instrument Service
instrument_service = InstrumentService()
