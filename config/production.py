import os
from config.base import BaseConfig


class ProductionConfig(BaseConfig):
    """Configuration for production environment."""

    DEBUG = False
    TESTING = False
    APP_ENV = "production"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

