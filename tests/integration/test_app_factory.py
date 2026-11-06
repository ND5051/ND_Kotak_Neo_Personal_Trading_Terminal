from app import create_app
from config.testing import TestingConfig
from app.models.db import get_engine


def test_app_factory_creation():
    """Verify create_app instantiates Flask app with proper config and blueprints."""
    app = create_app(TestingConfig)

    assert app is not None
    assert app.config["TESTING"] is True
    assert app.config["APP_ENV"] == "testing"

    expected_blueprints = [
        "dashboard",
        "auth",
        "market_watch",
        "orders",
        "basket",
        "baskets",
        "positions",
        "holdings",
        "option_chain",
        "settings",
        "paper_trading",
        "broker",
    ]
    for bp in expected_blueprints:
        assert bp in app.blueprints, f"Blueprint '{bp}' should be registered"

    assert get_engine() is not None
