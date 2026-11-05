from datetime import datetime, timezone
import threading
from typing import Any, Dict, Optional


class BrokerCache:
    """
    Thread-safe in-memory cache for broker capabilities, session metadata,
    and connectivity health states.
    Strictly prohibited from caching market data ticks or quotes.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._capabilities: Optional[Dict[str, Any]] = None
        self._capabilities_cached_at: Optional[datetime] = None
        self._session_meta: Dict[str, Any] = {}
        self._status: str = "DISCONNECTED"
        self._last_validation: Optional[str] = None

    def set_capabilities(self, capabilities: Dict[str, Any]) -> None:
        """Store discovered broker capabilities."""
        with self._lock:
            self._capabilities = dict(capabilities)
            self._capabilities_cached_at = datetime.now(timezone.utc)

    def get_capabilities(self) -> Optional[Dict[str, Any]]:
        """Retrieve cached capabilities."""
        with self._lock:
            if self._capabilities is not None:
                return dict(self._capabilities)
            return None

    def set_session_meta(self, meta: Dict[str, Any]) -> None:
        """Store non-sensitive session metadata (e.g. login time, server time, user ID)."""
        with self._lock:
            self._session_meta = dict(meta)

    def get_session_meta(self) -> Dict[str, Any]:
        """Retrieve cached session metadata."""
        with self._lock:
            return dict(self._session_meta)

    def clear_session_meta(self) -> None:
        """Clear cached session metadata upon logout or expiration."""
        with self._lock:
            self._session_meta.clear()

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
            self._capabilities = None
            self._capabilities_cached_at = None
            self._session_meta.clear()
            self._status = "DISCONNECTED"
            self._last_validation = None


# Global singleton
broker_cache = BrokerCache()

