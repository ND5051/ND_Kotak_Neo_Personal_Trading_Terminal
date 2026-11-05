from typing import Any, Optional, Type, Union
from flask import Flask

from config import BaseConfig, get_config
from app.logging.logger import setup_logging, get_logger
from app.models.db import init_db, create_all_tables
from app.core.feature_flags import feature_flags
from app.core.audit import audit_logger, AuditCategory
from app.events.event_bus import event_bus, publish
from app.events.event_types import SYSTEM_INITIALIZED
from app.middleware.error_handler import register_error_handlers
from app.middleware.request_logger import register_request_logging
from app.websocket.socket_manager import socket_manager

# Import Blueprints
from app.dashboard import dashboard_bp
from app.auth import auth_bp
from app.market_watch import market_watch_bp
from app.orders import orders_bp
from app.basket import basket_bp
from app.positions import positions_bp
from app.holdings import holdings_bp
from app.option_chain import option_chain_bp
from app.settings import settings_bp
from app.paper_trading import paper_trading_bp

logger = get_logger("app.factory")


def create_app(
    config_input: Optional[Union[Type[BaseConfig], str]] = None
) -> Flask:
    """
    Application Factory for Kotak Neo Personal Trading Terminal.
    Initializes environment configuration, logging, database, event bus,
    exception handlers, and blueprints with no business or trading logic.
    """
    # 1. Resolve Configuration
    if isinstance(config_input, str):
        config_class = get_config(config_input)
    elif config_input is not None and issubclass(config_input, BaseConfig):
        config_class = config_input
    else:
        config_class = get_config()

    # 2. Instantiate Flask Application
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(config_class)

    # 3. Initialize Structured Logging
    setup_logging(
        log_level=app.config.get("LOG_LEVEL", "INFO"),
        log_dir=app.config.get("LOG_DIR"),
    )
    logger.info(
        f"Creating application in '{app.config.get('APP_ENV')}' environment",
        event="APP_CREATE",
        environment=app.config.get("APP_ENV"),
    )

    # 4. Initialize Feature Flags
    flags = app.config.get("FEATURE_FLAGS", {})
    if isinstance(flags, dict):
        feature_flags.load(flags)

    # 5. Initialize Database Framework
    init_db(app)
    if app.config.get("DEBUG") or app.config.get("TESTING"):
        create_all_tables()

    # 6. Initialize WebSocket Framework
    socket_manager.init_app(app)

    # 7. Register Middleware & Error Handlers
    register_request_logging(app)
    register_error_handlers(app)

    # 8. Register Blueprints
    _register_blueprints(app)

    # 9. Initialize Event Bus and Notify Startup
    publish(
        SYSTEM_INITIALIZED,
        {"env": app.config.get("APP_ENV"), "status": "initialized"},
    )

    # 10. Audit Record System Initialization
    audit_logger.record(
        category=AuditCategory.SYSTEM,
        action="APPLICATION_INITIALIZED",
        actor="system",
        details={"env": app.config.get("APP_ENV")},
    )

    return app


def _register_blueprints(app: Flask) -> None:
    """Register all domain blueprints cleanly."""
    blueprints = [
        dashboard_bp,
        auth_bp,
        market_watch_bp,
        orders_bp,
        basket_bp,
        positions_bp,
        holdings_bp,
        option_chain_bp,
        settings_bp,
        paper_trading_bp,
    ]
    for bp in blueprints:
        app.register_blueprint(bp)
        logger.debug(
            f"Registered blueprint: {bp.name} (prefix: {bp.url_prefix})",
            event="BLUEPRINT_REGISTERED",
            blueprint=bp.name,
        )

