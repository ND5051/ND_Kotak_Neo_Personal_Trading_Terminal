from enum import Enum
from typing import Any, Dict, Optional

from app.broker.cache.broker_cache import BrokerCache, broker_cache
from app.broker.interfaces.broker_interface import BrokerInterface
from app.core.audit import audit_logger, AuditCategory, BROKER_HEALTH_CHECK
from app.core.request_context import get_correlation_id, get_request_id
from app.logging.logger import get_logger

logger = get_logger("app.broker.services.broker_health_service")


class BrokerStatus(str, Enum):
    """Normalized broker operational states."""

    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    AUTHENTICATED = "AUTHENTICATED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"


class BrokerHealthService:
    """
    Monitors health, connectivity states, and validation timestamps
    between the trading terminal and the Kotak Neo broker platform.
    """

    def __init__(
        self,
        adapter: Optional[BrokerInterface] = None,
        cache: Optional[BrokerCache] = None,
    ) -> None:
        self.adapter = adapter
        self.cache = cache or broker_cache

    def set_adapter(self, adapter: BrokerInterface) -> None:
        """Bind or update the active broker adapter."""
        self.adapter = adapter

    def is_connected(self) -> bool:
        """Check if network connectivity to broker is active."""
        if self.adapter is not None:
            return self.adapter.is_connected()
        status = self.cache.get_status()
        return status in (BrokerStatus.CONNECTED.value, BrokerStatus.AUTHENTICATED.value)

    def is_authenticated(self) -> bool:
        """Check if an active, authenticated broker session is established."""
        if self.adapter is not None:
            return self.adapter.is_connected()
        return self.cache.get_status() == BrokerStatus.AUTHENTICATED.value

    def last_validation(self) -> Optional[str]:
        """Retrieve timestamp of last successful session heartbeat."""
        return self.cache.get_last_validation()

    def broker_status(self) -> str:
        """Evaluate and return normalized broker status string."""
        if self.adapter is not None:
            if not self.adapter.is_connected():
                cached_status = self.cache.get_status()
                return (
                    cached_status
                    if cached_status in [s.value for s in BrokerStatus]
                    else BrokerStatus.DISCONNECTED.value
                )
            return BrokerStatus.AUTHENTICATED.value
        return self.cache.get_status()

    def perform_health_check(self, actor: str = "system") -> Dict[str, Any]:
        """Perform active diagnostic check and record audit trail."""
        if self.adapter is not None:
            result = self.adapter.health_check()
        else:
            result = {
                "status": self.cache.get_status(),
                "connected": False,
                "authenticated": False,
                "latency_ms": 0.0,
                "last_validation": self.cache.get_last_validation(),
            }

        # Sync cache status
        self.cache.set_status(result["status"])

        audit_logger.record(
            category=AuditCategory.BROKER,
            action=BROKER_HEALTH_CHECK,
            actor=actor,
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details=result,
        )

        return result


# Global Singleton
broker_health_service = BrokerHealthService()

