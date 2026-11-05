import os
from typing import Type

from config.base import BaseConfig
from config.development import DevelopmentConfig
from config.testing import TestingConfig
from config.production import ProductionConfig

CONFIG_MAP = {
    "development": DevelopmentConfig,
    "dev": DevelopmentConfig,
    "testing": TestingConfig,
    "test": TestingConfig,
    "production": ProductionConfig,
    "prod": ProductionConfig,
}


def get_config(env_name: str | None = None) -> Type[BaseConfig]:
    """Retrieve the configuration class matching the requested environment."""
    target_env = (env_name or os.getenv("APP_ENV", "development")).lower()
    return CONFIG_MAP.get(target_env, DevelopmentConfig)


__all__ = [
    "BaseConfig",
    "DevelopmentConfig",
    "TestingConfig",
    "ProductionConfig",
    "get_config",
]

