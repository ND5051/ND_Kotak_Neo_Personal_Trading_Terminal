"""
Unit tests for WatchlistService and SubscriptionManager Integration.
Phase 5: Market Watch Foundation.
Validates multi-watchlist CRUD, quota enforcement, and automated wire subscription hooks.
"""

import pytest

from app.auth.models.user import User
from app.broker.services.subscription_manager import SubscriptionManager
from app.core.exceptions import ValidationException
from app.market_watch.models.watchlist import Watchlist, WatchlistItem
from app.market_watch.repositories.watchlist_repository import WatchlistRepository
from app.market_watch.services.price_engine import MarketWatchPriceEngine
from app.market_watch.services.watchlist_service import (
    WatchlistQuotaExceededException,
    WatchlistService,
)
from app.models.db import init_db, create_all_tables, get_db_session


@pytest.fixture(autouse=True)
def setup_db():
    """Initialize in-memory SQLite database and test users."""
    init_db(database_url="sqlite:///:memory:")
    create_all_tables()
    with get_db_session() as session:
        for uid in [99991, 99992, 99993]:
            u = User(id=uid, username=f"user_{uid}", email=f"user_{uid}@example.com")
            u.set_password("SecurePass123!")
            session.add(u)
        session.commit()


@pytest.fixture
def mock_sub_manager():
    """Isolated subscription manager instance for testing."""
    return SubscriptionManager()


@pytest.fixture
def wl_service(mock_sub_manager):
    """Isolated WatchlistService attached to active database session."""
    repo = WatchlistRepository()
    pe = MarketWatchPriceEngine()
    return WatchlistService(repository=repo, sub_manager=mock_sub_manager, prices=pe)


def test_ensure_default_watchlist(wl_service, mock_sub_manager):
    """Verify automatic creation of Default Watchlist and benchmark subscriptions."""
    test_user_id = 99991
    wl = wl_service.ensure_default_watchlist(test_user_id)

    assert wl is not None
    assert wl.name == "Default Watchlist"
    assert wl.is_default is True
    assert len(wl.items) == 4

    # Verify SubscriptionManager registered all 4 benchmark scrips
    assert mock_sub_manager.get_token_count() == 4

    # Calling again returns same instance without duplicate items
    wl2 = wl_service.ensure_default_watchlist(test_user_id)
    assert wl2.id == wl.id
    assert len(wl2.items) == 4


def test_watchlist_crud_and_subscription_lifecycle(wl_service, mock_sub_manager):
    """Verify creating, adding items, removing items, and deleting watchlists."""
    test_user_id = 99992

    # 1. Create watchlist
    wl = wl_service.create_watchlist(test_user_id, "Tech Momentum")
    assert wl.id is not None
    assert wl.name == "Tech Momentum"

    # 2. Add instrument -> triggers subscription
    item = wl_service.add_item(
        user_id=test_user_id,
        watchlist_id=wl.id,
        instrument_token="1594",
        exchange_segment="nse_cm",
        trading_symbol="INFY-EQ",
        display_name="Infosys Ltd",
    )
    assert item.id is not None
    assert mock_sub_manager.get_token_count() == 1

    # 3. Duplicate rejection
    with pytest.raises(ValidationException):
        wl_service.add_item(
            user_id=test_user_id,
            watchlist_id=wl.id,
            instrument_token="1594",
            exchange_segment="nse_cm",
            trading_symbol="INFY-EQ",
        )

    # 4. Remove item -> decrements subscription
    removed = wl_service.remove_item(test_user_id, wl.id, item.id)
    assert removed is True
    assert mock_sub_manager.get_token_count() == 0

    # 5. Add another item and delete watchlist -> cleans up subscription
    item2 = wl_service.add_item(
        user_id=test_user_id,
        watchlist_id=wl.id,
        instrument_token="11536",
        exchange_segment="nse_cm",
        trading_symbol="TCS-EQ",
    )
    assert mock_sub_manager.get_token_count() == 1

    deleted = wl_service.delete_watchlist(test_user_id, wl.id)
    assert deleted is True
    assert mock_sub_manager.get_token_count() == 0


def test_watchlist_quotas(wl_service):
    """Verify maximum 10 watchlists per user and maximum 50 scrips per watchlist."""
    test_user_id = 99993

    # Create up to MAX_WATCHLISTS_PER_USER (10)
    created_lists = []
    for i in range(10):
        wl = wl_service.create_watchlist(test_user_id, f"Watchlist_{i}")
        created_lists.append(wl)

    # 11th should raise WatchlistQuotaExceededException
    with pytest.raises(WatchlistQuotaExceededException):
        wl_service.create_watchlist(test_user_id, "Watchlist_11")

    # Test scrip quota on first list (50 max)
    target_wl = created_lists[0]
    for j in range(50):
        wl_service.add_item(
            user_id=test_user_id,
            watchlist_id=target_wl.id,
            instrument_token=f"TOK_{j}",
            exchange_segment="nse_cm",
            trading_symbol=f"SCRIP_{j}",
        )

    # 51st should raise WatchlistQuotaExceededException
    with pytest.raises(WatchlistQuotaExceededException):
        wl_service.add_item(
            user_id=test_user_id,
            watchlist_id=target_wl.id,
            instrument_token="TOK_OVERFLOW",
            exchange_segment="nse_cm",
            trading_symbol="SCRIP_OVERFLOW",
        )
