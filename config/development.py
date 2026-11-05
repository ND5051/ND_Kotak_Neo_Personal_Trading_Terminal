from config.base import BaseConfig


class DevelopmentConfig(BaseConfig):
    """Configuration for local development."""

    DEBUG = True
    APP_ENV = "development"
    LOG_LEVEL = "DEBUG"

