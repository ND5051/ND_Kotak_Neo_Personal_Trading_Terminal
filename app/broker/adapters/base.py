from typing import Any, Dict
from app.broker.interfaces.broker_interface import BrokerInterface
from app.logging.logger import get_logger

logger = get_logger("app.broker.adapters.base")


class BaseBrokerAdapter(BrokerInterface):
    """
    Base abstract implementation of BrokerInterface providing logging
    and lifecycle templates.
    """

    def __init__(self, name: str = "BaseAdapter") -> None:
        self.name = name
        self._connected = False
        self._authenticated = False

    def is_connected(self) -> bool:
        return self._connected and self._authenticated

    def login(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Login must be implemented by concrete broker adapter")

    def logout(self) -> bool:
        self._connected = False
        self._authenticated = False
        return True

    def validate_session(self) -> bool:
        raise NotImplementedError("Validate session must be implemented by concrete broker adapter")

    def restore_session(self, session_data: Dict[str, Any]) -> bool:
        raise NotImplementedError("Restore session must be implemented by concrete broker adapter")

    def health_check(self) -> Dict[str, Any]:
        raise NotImplementedError("Health check must be implemented by concrete broker adapter")

    def get_capabilities(self) -> Dict[str, Any]:
        raise NotImplementedError("Get capabilities must be implemented by concrete broker adapter")
