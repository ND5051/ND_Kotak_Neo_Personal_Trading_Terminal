from typing import Any, Dict, List, Optional
from app.broker.interfaces.broker_interface import IBrokerAdapter
from app.logging.logger import get_logger

logger = get_logger("app.broker.adapters.base")


class BaseBrokerAdapter(IBrokerAdapter):
    """Base abstract implementation providing logging and common safety primitives."""

    def __init__(self, name: str = "BaseAdapter") -> None:
        self.name = name
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def connect(self, credentials: Dict[str, Any]) -> bool:
        raise NotImplementedError("Connect must be implemented by concrete broker adapter")

    def disconnect(self) -> bool:
        self._connected = False
        return True

    def get_profile(self) -> Dict[str, Any]:
        raise NotImplementedError

    def get_margins(self) -> Dict[str, Any]:
        raise NotImplementedError

    def place_order(self, order_payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def modify_order(self, order_id: str, modification_payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_orders(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_positions(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_holdings(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

