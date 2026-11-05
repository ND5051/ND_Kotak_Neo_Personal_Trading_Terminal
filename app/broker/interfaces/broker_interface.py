from abc import ABC, abstractmethod
from typing import Any, Dict


class BrokerInterface(ABC):
    """
    Formal broker adapter interface defining session lifecycle,
    health monitoring, and capability discovery.
    Strictly excludes order placement, modification, or market feed streaming.
    (Project Constitution Rule 1 & Phase 3 Specification)
    """

    @abstractmethod
    def login(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Authenticate with the broker using credentials.
        Returns session tokens and metadata upon success.
        """
        pass

    @abstractmethod
    def logout(self) -> bool:
        """Terminate the active broker session."""
        pass

    @abstractmethod
    def validate_session(self) -> bool:
        """Validate if the active broker session token is alive and functional."""
        pass

    @abstractmethod
    def restore_session(self, session_data: Dict[str, Any]) -> bool:
        """Restore broker connectivity using previously persisted and decrypted session credentials."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Perform connectivity and latency diagnostic check against broker API."""
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Discover supported exchanges, products, order types, and segments."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Return boolean indicating whether client is currently connected and authenticated."""
        pass
