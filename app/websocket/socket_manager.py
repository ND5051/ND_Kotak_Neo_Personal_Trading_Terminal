from typing import Any, Dict, Optional
from flask import Flask
from flask_socketio import SocketIO
from app.logging.logger import get_logger

logger = get_logger("app.websocket.socket_manager")


class SocketManager:
    """
    Manages WebSocket lifecycle and real-time streaming to the browser frontend.
    Initializes Flask-SocketIO without business logic during Phase 1.
    """

    def __init__(self) -> None:
        self.socketio: Optional[SocketIO] = None

    def init_app(self, app: Flask) -> SocketIO:
        """Initialize Flask-SocketIO with the application instance."""
        self.socketio = SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode="threading",
            logger=False,
            engineio_logger=False,
        )
        self._register_handlers()
        logger.info("WebSocket manager initialized", event="WEBSOCKET_INITIALIZED")
        return self.socketio

    def _register_handlers(self) -> None:
        """Register base lifecycle handlers for browser clients."""
        if self.socketio is None:
            return

        @self.socketio.on("connect")
        def handle_connect():
            logger.debug("Client connected via WebSocket", event="WS_CLIENT_CONNECTED")

        @self.socketio.on("disconnect")
        def handle_disconnect():
            logger.debug("Client disconnected from WebSocket", event="WS_CLIENT_DISCONNECTED")

    def broadcast(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Broadcast payload to all connected frontend clients."""
        if self.socketio is not None:
            self.socketio.emit(event_name, payload)


# Global singleton
socket_manager = SocketManager()

