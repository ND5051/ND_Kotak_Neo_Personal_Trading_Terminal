from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IBrokerAdapter(ABC):
    """
    Formal broker adapter interface.
    All broker SDK communications (Kotak Neo, Paper Simulator, Mock)
    must implement this interface exclusively. (Project Constitution Rule 1 & Rule 10)
    """

    @abstractmethod
    def connect(self, credentials: Dict[str, Any]) -> bool:
        """Establish session with broker API."""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Terminate active session."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Return connectivity status."""
        pass

    @abstractmethod
    def get_profile(self) -> Dict[str, Any]:
        """Fetch trader profile and account privileges."""
        pass

    @abstractmethod
    def get_margins(self) -> Dict[str, Any]:
        """Fetch available funds and margin utilization."""
        pass

    @abstractmethod
    def place_order(self, order_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a single order to the broker."""
        pass

    @abstractmethod
    def modify_order(self, order_id: str, modification_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Modify an existing open order."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an open order."""
        pass

    @abstractmethod
    def get_orders(self) -> List[Dict[str, Any]]:
        """Fetch order book from broker."""
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Fetch live trading positions."""
        pass

    @abstractmethod
    def get_holdings(self) -> List[Dict[str, Any]]:
        """Fetch long-term portfolio holdings."""
        pass

