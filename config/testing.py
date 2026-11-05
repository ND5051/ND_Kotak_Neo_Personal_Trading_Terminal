from config.base import BaseConfig


class TestingConfig(BaseConfig):
    """Configuration for automated test execution."""

    TESTING = True
    DEBUG = False
    APP_ENV = "testing"
    DATABASE_URL = "sqlite:///:memory:"
    LOG_LEVEL = "WARNING"

    FEATURE_FLAGS = {
        "PAPER_TRADING": True,
        "GTT": True,
        "SCANNER_ENGINE": True,
        "STRATEGY_ENGINE": True,
        "NOTIFICATIONS": True,
    }

