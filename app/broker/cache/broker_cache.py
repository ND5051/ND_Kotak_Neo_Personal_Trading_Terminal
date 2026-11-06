from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import threading
from typing import Any, Dict, Optional

from app.logging.logger import get_logger

logger = get_logger("app.broker.cache")


@dataclass
class CacheEntry:
    """Timestamped cache envelope enforcing time-to-live expiration."""

    value: Any
    created_at: datetime
    expires_at: Optional[datetime]

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        if self.expires_at is None:
            return False
        current_time = now or datetime.now(timezone.utc)
        return current_time > self.expires_at


class BrokerCache:
    """
    Thread-safe in-memory cache for broker capabilities, session metadata,
    and connectivity health states with automated Time-To-Live (TTL) expiration.
    Strictly prohibited from caching market data ticks or quotes.
    """

    # Default TTL horizons (seconds)
    TTL_CAPABILITIES = 86400    # 24 Hours
    TTL_SESSION_META = 28800    # 8 Hours (matches broker session)
    TTL_HEALTH_STATS = 5        # 5 Seconds (near real-time)

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._store: Dict[str, CacheEntry] = {}
        self._status: str = "DISCONNECTED"
        self._last_validation: Optional[str] = None

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store value with optional TTL expiration."""
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(seconds=ttl_seconds)) if ttl_seconds is not None else None

        with self._lock:
            self._store[key] = CacheEntry(
                value=value,
                created_at=now,
                expires_at=expires_at,
            )

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve value, performing lazy eviction if TTL has elapsed.
        Returns None if missing or expired.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None

            if entry.is_expired():
                del self._store[key]
                logger.debug(f"Cache key '{key}' expired and lazily evicted", event="CACHE_TTL_EXPIRED")
                return None

            # Return a copy if it's a dict to prevent caller mutations
            if isinstance(entry.value, dict):
                return dict(entry.value)
            return entry.value

    def delete(self, key: str) -> bool:
        """Explicitly remove key from cache."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def purge_expired(self) -> int:
        """Active sweeper removing all expired cache entries."""
        now = datetime.now(timezone.utc)
        purged = 0
        with self._lock:
            keys_to_delete = [
                k for k, v in self._store.items() if v.is_expired(now)
            ]
            for k in keys_to_delete:
                del self._store[k]
                purged += 1
        return purged

    # Dedicated Partitioned Helpers
    def set_capabilities(self, capabilities: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Store discovered broker capabilities with 24-hour default TTL."""
        self.set("capabilities", dict(capabilities), ttl_seconds=ttl or self.TTL_CAPABILITIES)

    def get_capabilities(self) -> Optional[Dict[str, Any]]:
        """Retrieve cached capabilities if not expired."""
        return self.get("capabilities")

    def set_session_meta(self, meta: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Store session metadata with 8-hour default TTL."""
        self.set("session_meta", dict(meta), ttl_seconds=ttl or self.TTL_SESSION_META)

    def get_session_meta(self) -> Dict[str, Any]:
        """Retrieve cached session metadata or empty dict."""
        val = self.get("session_meta")
        return val if isinstance(val, dict) else {}

    def clear_session_meta(self) -> None:
        """Clear cached session metadata."""
        self.delete("session_meta")

    def set_status(self, status: str) -> None:
        """Set current broker operational status."""
        with self._lock:
            self._status = status

    def get_status(self) -> str:
        """Retrieve current broker operational status."""
        with self._lock:
            return self._status

    def set_last_validation(self, timestamp: Optional[str] = None) -> None:
        """Record the timestamp of the last successful session validation check."""
        with self._lock:
            self._last_validation = (
                timestamp or datetime.now(timezone.utc).isoformat()
            )

    def get_last_validation(self) -> Optional[str]:
        """Retrieve timestamp of last validation."""
        with self._lock:
            return self._last_validation

    def clear(self) -> None:
        """Purge all cache contents (used in teardown and reset)."""
        with self._lock:
            self._store.clear()
            self._status = "DISCONNECTED"
            self._last_validation = None


# Global singleton
broker_cache = BrokerCache()
