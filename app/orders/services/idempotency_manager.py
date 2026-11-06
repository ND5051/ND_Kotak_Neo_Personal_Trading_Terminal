import threading
import time
from typing import Dict


class IdempotencyManager:
    """
    Thread-safe in-memory idempotency deduplication cache.
    Prevents duplicate wire submissions from UI double-clicks,
    network retries, or algorithmic loops.
    """

    def __init__(self, default_ttl_seconds: int = 300) -> None:
        self.default_ttl = default_ttl_seconds
        self._cache: Dict[str, float] = {}
        self._lock = threading.RLock()

    def check_and_acquire(self, client_order_id: str, ttl_seconds: int = 300) -> bool:
        """
        Atomically inspect and register client_order_id.
        Returns True if acquired (new request), False if already active (duplicate).
        """
        with self._lock:
            now = time.time()
            self._purge_expired(now)

            if client_order_id in self._cache:
                return False

            self._cache[client_order_id] = now + ttl_seconds
            return True

    def is_duplicate(self, client_order_id: str) -> bool:
        """Check if client_order_id is currently registered."""
        with self._lock:
            now = time.time()
            expiry = self._cache.get(client_order_id)
            if expiry is None:
                return False
            if expiry <= now:
                del self._cache[client_order_id]
                return False
            return True

    def release(self, client_order_id: str) -> None:
        """Release client_order_id if an early pre-flight validation error occurs."""
        with self._lock:
            self._cache.pop(client_order_id, None)

    def clear(self) -> None:
        """Clear all registered keys."""
        with self._lock:
            self._cache.clear()

    def _purge_expired(self, now: float) -> None:
        """Internal cleanup of expired keys."""
        expired = [k for k, exp in self._cache.items() if exp <= now]
        for k in expired:
            del self._cache[k]


# Global singleton instance
idempotency_manager = IdempotencyManager()

