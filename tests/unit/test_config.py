from config import get_config, BaseConfig, DevelopmentConfig, TestingConfig, ProductionConfig


def test_config_resolution():
    """Verify that get_config resolves correct classes."""
    assert get_config("development") == DevelopmentConfig
    assert get_config("testing") == TestingConfig
    assert get_config("production") == ProductionConfig


def test_base_config_defaults():
    """Verify default configurations have required keys."""
    assert hasattr(BaseConfig, "SECRET_KEY")
    assert hasattr(BaseConfig, "DATABASE_URL")
    assert hasattr(BaseConfig, "APP_ENV")
    assert hasattr(BaseConfig, "LOG_LEVEL")
    assert hasattr(BaseConfig, "FEATURE_FLAGS")
    assert isinstance(BaseConfig.FEATURE_FLAGS, dict)


def test_testing_config_overrides():
    """Verify TestingConfig enforces memory DB and testing mode."""
    assert TestingConfig.TESTING is True
    assert TestingConfig.DEBUG is False
    assert TestingConfig.DATABASE_URL == "sqlite:///:memory:"

