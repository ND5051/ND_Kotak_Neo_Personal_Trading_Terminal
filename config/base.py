import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env")


class BaseConfig:
    """Base Configuration with default settings and environment fallbacks."""

    APP_ENV = os.getenv("APP_ENV", "development").lower()
    SECRET_KEY = os.getenv("SECRET_KEY", "insecure-default-key-change-in-prod")

    # Paths
    BASE_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / "data"
    LOG_DIR = BASE_DIR / os.getenv("LOG_DIR", "logs")

    # Database
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'data' / 'kotak_terminal.db'}"
    )

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    # Feature Flags Framework Defaults
    FEATURE_FLAGS = {
        "PAPER_TRADING": os.getenv("FEATURE_PAPER_TRADING", "true").lower() in ("true", "1", "yes"),
        "GTT": os.getenv("FEATURE_GTT", "false").lower() in ("true", "1", "yes"),
        "SCANNER_ENGINE": os.getenv("FEATURE_SCANNER_ENGINE", "false").lower() in ("true", "1", "yes"),
        "STRATEGY_ENGINE": os.getenv("FEATURE_STRATEGY_ENGINE", "false").lower() in ("true", "1", "yes"),
        "NOTIFICATIONS": os.getenv("FEATURE_NOTIFICATIONS", "false").lower() in ("true", "1", "yes"),
    }

    # Security & Server defaults
    TESTING = False
    DEBUG = False
    JSON_SORT_KEYS = False

