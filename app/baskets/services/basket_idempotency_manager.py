import hashlib
import json
import threading
import time
from typing import Any, Dict, List, Optional

from app.baskets.repositories.basket_repository import (
    BasketRepositoryInterface,
    basket_repository,
)


class BasketIdempotencyManager:
    """
    Two-Tier Basket Idempotency Deduplication Manager.
    Level 1 Basket protection preventing duplicate multi-leg strategy container submissions
    from rapid double-clicks, UI retries, or network storms.
    """

    def __init__(
        self,
        repository: Optional[BasketRepositoryInterface] = None,
        default_ttl_seconds: int = 120,
    ) -> None:
        self.repository = repository or basket_repository
        self.default_ttl = default_ttl_seconds
        self._cache: Dict[str, float] = {}
        self._lock = threading.RLock()

    @staticmethod
    def compute_basket_hash(user_id: int, strategy_type: str, legs: List[Dict[str, Any]]) -> str:
        """
        Compute deterministic SHA-256 idempotency signature for a basket payload.
        """
        canonical_legs = []
        for leg in legs:
            canonical_legs.append(
                f"{leg.get('trading_symbol', '')}:{str(leg.get('side', '')).upper()}:{leg.get('quantity', 0)}:{leg.get('price', 0.0)}"
            )
        raw_signature = f"{user_id}|{str(strategy_type).upper()}|{'#'.join(canonical_legs)}"
        return hashlib.sha256(raw_signature.encode("utf-8")).hexdigest()

    def check_and_acquire(
        self, client_basket_id: str, idempotency_key: str = "", ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Atomically inspect and register client_basket_id.
        Returns True if acquired (new request), False if already active or exists in DB.
        """
        with self._lock:
            now = time.time()
            ttl = ttl_seconds or self.default_ttl
            self._purge_expired(now)

            # 1. In-memory deduplication check
            if client_basket_id in self._cache:
                return False

            if idempotency_key and idempotency_key in self._cache:
                return False

            # 2. Database deduplication check
            existing = self.repository.get_basket_by_client_id(client_basket_id)
            if existing is not None:
                return False

            # Acquire lock
            self._cache[client_basket_id] = now + ttl
            if idempotency_key:
                self._cache[idempotency_key] = now + ttl

            return True

    def acquire_execution(
        self, client_basket_id: str, idempotency_key: str = "", ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Atomically acquire execution lock for an existing basket.
        Rejects if an active execution lock is already held in-memory or if
        the basket in the database is already EXECUTING, EXECUTED, PARTIALLY_EXECUTED, or RECONCILING.
        """
        with self._lock:
            now = time.time()
            ttl = ttl_seconds or self.default_ttl
            self._purge_expired(now)

            exec_key = f"exec_{client_basket_id}"
            if exec_key in self._cache:
                return False

            if idempotency_key:
                exec_hash_key = f"exec_hash_{idempotency_key}"
                if exec_hash_key in self._cache:
                    return False

            existing = self.repository.get_basket_by_client_id(client_basket_id)
            if existing is not None:
                from app.baskets.models.basket import BasketState

                if existing.status in (
                    BasketState.EXECUTING,
                    BasketState.EXECUTED,
                    BasketState.PARTIALLY_EXECUTED,
                    BasketState.RECONCILING,
                    BasketState.CANCELLED,
                ):
                    return False

            self._cache[exec_key] = now + ttl
            if idempotency_key:
                self._cache[f"exec_hash_{idempotency_key}"] = now + ttl

            return True

    def release_execution(self, client_basket_id: str, idempotency_key: str = "") -> None:
        """Release in-memory execution lock."""
        with self._lock:
            self._cache.pop(f"exec_{client_basket_id}", None)
            if idempotency_key:
                self._cache.pop(f"exec_hash_{idempotency_key}", None)

    def is_duplicate(self, client_basket_id: str) -> bool:
        """Check if client_basket_id is registered or already saved in DB."""
        with self._lock:
            now = time.time()
            expiry = self._cache.get(client_basket_id)
            if expiry is not None:
                if expiry > now:
                    return True
                else:
                    del self._cache[client_basket_id]

            existing = self.repository.get_basket_by_client_id(client_basket_id)
            return existing is not None

    def release(self, client_basket_id: str, idempotency_key: str = "") -> None:
        """Release keys upon pre-flight syntax failure before wire dispatch."""
        with self._lock:
            self._cache.pop(client_basket_id, None)
            if idempotency_key:
                self._cache.pop(idempotency_key, None)

    def clear(self) -> None:
        """Clear in-memory cache."""
        with self._lock:
            self._cache.clear()

    def _purge_expired(self, now: float) -> None:
        """Purge expired tokens."""
        expired = [k for k, exp in self._cache.items() if exp <= now]
        for k in expired:
            del self._cache[k]


# Global singleton
basket_idempotency_manager = BasketIdempotencyManager()
