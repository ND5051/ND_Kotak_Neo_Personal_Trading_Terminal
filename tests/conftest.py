import pytest
from typing import Generator
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from config.testing import TestingConfig
from app.models.db import init_db, create_all_tables, drop_all_tables, db_session
from app.events.event_bus import event_bus


@pytest.fixture(scope="session")
def app() -> Generator[Flask, None, None]:
    """Provide application configured for automated testing."""
    test_app = create_app(TestingConfig)
    with test_app.app_context():
        create_all_tables()
        yield test_app
        drop_all_tables()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Provide Flask test client for HTTP requests."""
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_event_bus():
    """Ensure event bus subscriptions do not leak across test cases."""
    event_bus.clear()
    yield
    event_bus.clear()

