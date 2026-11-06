from dataclasses import dataclass
from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional

from app.core.exceptions import SubscriptionQuotaExceededException
from app.events.event_bus import publish
from app.events.event_types import (
    WS_SUBSCRIPTION_ADDED,
    WS_SUBSCRIPTION_REMOVED,
)
from app.logging.logger import get_logger

logger = get_logger("app.broker.services.subscription_manager")


@dataclass
class SubscriptionEntry:
    token_id: str
    exchange_segment: str
    ref_count: int
    subscribed_at: str


class SubscriptionManager:
    """
    Authoritative in-memory registry of instrument subscriptions.
    Enforces Kotak Neo's 3,000 scrip quota cap, implements reference counting,
    and stages batch resubscriptions upon reconnection.
    """

    MAX_QUOTA = 3000

    def __init__(self, max_quota: int = MAX_QUOTA) -> None:
        self.max_quota = max_quota
        self._lock = threading.RLock()
        self._registry: Dict[str, SubscriptionEntry] = {}

    def subscribe(self, token_id: str, exchange_segment: str) -> bool:
        """
        Register interest in an instrument.
        Returns True if a live socket wire call is required (ref_count: 0 -> 1).
        Returns False if already actively subscribed (ref_count incremented).
        Raises SubscriptionQuotaExceededException if quota limit would be breached.
        """
        token_id_str = str(token_id).strip()
        segment_str = exchange_segment.strip().lower()

        with self._lock:
            if token_id_str in self._registry:
                entry = self._registry[token_id_str]
                entry.ref_count += 1
                logger.debug(
                    f"Incremented subscription ref_count for {token_id_str} to {entry.ref_count}",
                    event="WS_SUB_REF_INCREMENT",
                    token=token_id_str,
                    ref_count=entry.ref_count,
                )
                return False

            # Check quota before registering new token
            if len(self._registry) >= self.max_quota:
                raise SubscriptionQuotaExceededException(
                    message=(
                        f"Cannot subscribe to token {token_id_str}: quota limit of "
                        f"{self.max_quota} scrips reached."
                    ),
                    details={
                        "current_count": len(self._registry),
                        "max_quota": self.max_quota,
                        "token": token_id_str,
                    },
                )

            # Register new entry
            now_iso = datetime.now(timezone.utc).isoformat()
            self._registry[token_id_str] = SubscriptionEntry(
                token_id=token_id_str,
                exchange_segment=segment_str,
                ref_count=1,
                subscribed_at=now_iso,
            )

            publish(
                WS_SUBSCRIPTION_ADDED,
                {
                    "token_id": token_id_str,
                    "exchange_segment": segment_str,
                    "total_subscribed": len(self._registry),
                },
            )
            logger.info(
                f"New instrument subscription registered: {segment_str}|{token_id_str}. Total: {len(self._registry)}",
                event="WS_SUB_NEW",
                token=token_id_str,
                segment=segment_str,
            )
            return True

    def unsubscribe(self, token_id: str) -> bool:
        """
        Deregister interest in an instrument.
        Returns True if a live socket wire call is required (ref_count: 1 -> 0, removed).
        Returns False if ref_count > 0 (other consumers still observing) or not found.
        """
        token_id_str = str(token_id).strip()

        with self._lock:
            if token_id_str not in self._registry:
                return False

            entry = self._registry[token_id_str]
            entry.ref_count -= 1

            if entry.ref_count <= 0:
                del self._registry[token_id_str]
                publish(
                    WS_SUBSCRIPTION_REMOVED,
                    {
                        "token_id": token_id_str,
                        "exchange_segment": entry.exchange_segment,
                        "total_subscribed": len(self._registry),
                    },
                )
                logger.info(
                    f"Instrument subscription purged: {entry.exchange_segment}|{token_id_str}. Remaining: {len(self._registry)}",
                    event="WS_SUB_PURGED",
                    token=token_id_str,
                )
                return True

            logger.debug(
                f"Decremented subscription ref_count for {token_id_str} to {entry.ref_count}",
                event="WS_SUB_REF_DECREMENT",
                token=token_id_str,
                ref_count=entry.ref_count,
            )
            return False

    def get_token_count(self) -> int:
        """Return count of unique active instruments in registry."""
        with self._lock:
            return len(self._registry)

    def get_ref_count(self, token_id: str) -> int:
        """Return current reference count for an instrument token."""
        token_id_str = str(token_id).strip()
        with self._lock:
            entry = self._registry.get(token_id_str)
            return entry.ref_count if entry else 0

    def get_active_tokens(self) -> List[Dict[str, str]]:
        """Return list of all registered tokens and segments."""
        with self._lock:
            return [
                {"token_id": e.token_id, "exchange_segment": e.exchange_segment}
                for e in self._registry.values()
            ]

    def get_token_batches(self, batch_size: int = 500) -> List[List[Dict[str, str]]]:
        """Return active tokens chunked into batch sizes for SFeed frame transmission."""
        all_tokens = self.get_active_tokens()
        return [all_tokens[i : i + batch_size] for i in range(0, len(all_tokens), batch_size)]

    def clear(self) -> None:
        """Clear all registered subscriptions (used during teardown or reset)."""
        with self._lock:
            self._registry.clear()


# Global singleton
subscription_manager = SubscriptionManager()
