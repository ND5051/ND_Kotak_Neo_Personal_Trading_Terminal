"""
Instrument In-Memory Repository & Prefix Search Index.
Phase 5: Market Watch Foundation.
Provides sub-millisecond search across tokens, trading symbols, and company names.
"""

from collections import defaultdict
import threading
from typing import Dict, List, Optional, Set, Tuple

from app.market_watch.models.instrument import Instrument
from app.logging.logger import get_logger

logger = get_logger("app.market_watch.repositories.instrument_repository")


class InstrumentRepository:
    """
    High-performance in-memory registry and multi-index for Scrip Master instruments.
    Supports sub-millisecond lookup by token, symbol, and prefix queries.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Primary lookup: (token, segment) -> Instrument
        self._by_token: Dict[Tuple[str, str], Instrument] = {}
        # Symbol lookup: uppercase trading_symbol -> List[Instrument]
        self._by_symbol: Dict[str, List[Instrument]] = defaultdict(list)
        # Name lookup: uppercase symbol_name -> List[Instrument]
        self._by_name: Dict[str, List[Instrument]] = defaultdict(list)
        # Prefix Index: prefix -> Set[(token, segment)]
        self._prefix_index: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)

    def add_instrument(self, instrument: Instrument) -> None:
        """Index a single instrument across all search tables."""
        key = (instrument.instrument_token.strip(), instrument.exchange_segment.strip().lower())
        sym = instrument.trading_symbol.strip().upper()
        name = instrument.symbol_name.strip().upper()
        token = instrument.instrument_token.strip()

        with self._lock:
            self._by_token[key] = instrument
            self._by_symbol[sym].append(instrument)
            if name:
                self._by_name[name].append(instrument)

            # Build prefix index for token, symbol, and name
            self._index_prefixes(token, key)
            self._index_prefixes(sym, key)
            if name:
                self._index_prefixes(name, key)

    def load_instruments(self, instruments: List[Instrument]) -> int:
        """Bulk load a collection of instruments with batch indexing."""
        with self._lock:
            for inst in instruments:
                self.add_instrument(inst)
            total = len(self._by_token)
            logger.info(
                f"Loaded {len(instruments)} instruments. Total in-memory: {total}",
                event="SCRIP_INDEX_UPDATED",
                loaded_count=len(instruments),
                total_count=total,
            )
            return len(instruments)

    def get_by_token(self, token: str, segment: str) -> Optional[Instrument]:
        """Fetch instrument by exact token and exchange segment."""
        key = (str(token).strip(), str(segment).strip().lower())
        with self._lock:
            return self._by_token.get(key)

    def search(
        self,
        query: str,
        segment: Optional[str] = None,
        limit: int = 20,
    ) -> List[Instrument]:
        """
        Fast prefix and keyword search across trading symbols, tokens, and names.
        Returns ranked matching instruments up to the specified limit.
        """
        q = str(query).strip().upper()
        if not q:
            return []

        seg_filter = segment.strip().lower() if segment else None
        results: List[Instrument] = []
        seen_keys: Set[Tuple[str, str]] = set()

        with self._lock:
            # 1. Exact token match check
            for (t, s), inst in self._by_token.items():
                if t == q:
                    if seg_filter is None or s == seg_filter:
                        results.append(inst)
                        seen_keys.add((t, s))

            # 2. Exact symbol matches
            if q in self._by_symbol:
                for inst in self._by_symbol[q]:
                    k = (inst.instrument_token, inst.exchange_segment)
                    if k not in seen_keys:
                        if seg_filter is None or inst.exchange_segment == seg_filter:
                            results.append(inst)
                            seen_keys.add(k)

            # 3. Prefix matching from Trie / prefix index
            matching_keys = self._prefix_index.get(q, set())
            for k in matching_keys:
                if len(results) >= limit:
                    break
                if k not in seen_keys:
                    inst = self._by_token.get(k)
                    if inst:
                        if seg_filter is None or inst.exchange_segment == seg_filter:
                            results.append(inst)
                            seen_keys.add(k)

            # 4. Fallback substring search if prefix returns fewer than limit
            if len(results) < limit:
                for (t, s), inst in self._by_token.items():
                    if len(results) >= limit:
                        break
                    if (t, s) not in seen_keys:
                        if q in inst.trading_symbol.upper() or q in inst.symbol_name.upper():
                            if seg_filter is None or s == seg_filter:
                                results.append(inst)
                                seen_keys.add((t, s))

        return results[:limit]

    def count(self) -> int:
        """Total instruments indexed."""
        with self._lock:
            return len(self._by_token)

    def clear(self) -> None:
        """Clear all in-memory indexes."""
        with self._lock:
            self._by_token.clear()
            self._by_symbol.clear()
            self._by_name.clear()
            self._prefix_index.clear()

    def _index_prefixes(self, text: str, key: Tuple[str, str]) -> None:
        """Internal helper to index prefixes (min 2 chars, max 10 chars)."""
        clean = text.upper()
        for i in range(2, min(len(clean) + 1, 11)):
            prefix = clean[:i]
            self._prefix_index[prefix].add(key)


# Global Singleton Instrument Repository
instrument_repository = InstrumentRepository()
