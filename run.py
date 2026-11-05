import os
from app import create_app
from app.websocket.socket_manager import socket_manager
from app.logging.logger import get_logger

logger = get_logger("run")

app = create_app()

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 5000))
    debug = app.config.get("DEBUG", False)

    logger.info(
        f"Starting Kotak Neo Personal Trading Terminal on http://{host}:{port}",
        event="SERVER_START",
        host=host,
        port=port,
        debug=debug,
    )

    if socket_manager.socketio is not None:
        socket_manager.socketio.run(app, host=host, port=port, debug=debug)
    else:
        app.run(host=host, port=port, debug=debug)

