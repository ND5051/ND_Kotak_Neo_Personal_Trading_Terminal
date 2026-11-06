"""
Watchlist Persistence Repository.
Phase 5: Market Watch Foundation.
Provides database access for Watchlist and WatchlistItem entities.
"""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.market_watch.models.watchlist import Watchlist, WatchlistItem
from app.repositories.base import BaseRepository


class WatchlistRepository(BaseRepository[Watchlist]):
    """
    Repository handling persistence and relational queries for Watchlists and WatchlistItems.
    """

    def __init__(self, session: Optional[DbSession] = None) -> None:
        super().__init__(model_class=Watchlist, session=session)

    def get_by_user(self, user_id: int) -> List[Watchlist]:
        """Fetch all watchlists belonging to a user ordered by display position."""
        stmt = (
            select(Watchlist)
            .where(Watchlist.user_id == user_id)
            .order_by(Watchlist.position.asc(), Watchlist.id.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_default(self, user_id: int) -> Optional[Watchlist]:
        """Fetch default watchlist for a user."""
        stmt = (
            select(Watchlist)
            .where(Watchlist.user_id == user_id, Watchlist.is_default == True)
        )
        return self.session.execute(stmt).scalars().first()

    def find_by_name(self, user_id: int, name: str) -> Optional[Watchlist]:
        """Look up watchlist by exact name for a user."""
        stmt = (
            select(Watchlist)
            .where(Watchlist.user_id == user_id, Watchlist.name == name.strip())
        )
        return self.session.execute(stmt).scalars().first()

    def count_by_user(self, user_id: int) -> int:
        """Count total watchlists owned by a user."""
        stmt = select(Watchlist).where(Watchlist.user_id == user_id)
        return len(list(self.session.execute(stmt).scalars().all()))

    # WatchlistItem Operations
    def add_item(self, item: WatchlistItem) -> WatchlistItem:
        """Add and persist a new item to a watchlist."""
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def get_item_by_id(self, item_id: int) -> Optional[WatchlistItem]:
        """Retrieve a specific watchlist item by primary key."""
        stmt = select(WatchlistItem).where(WatchlistItem.id == item_id)
        return self.session.execute(stmt).scalars().first()

    def find_item(
        self, watchlist_id: int, token: str, segment: str
    ) -> Optional[WatchlistItem]:
        """Check if an instrument token and segment already exist in the watchlist."""
        stmt = select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.instrument_token == str(token).strip(),
            WatchlistItem.exchange_segment == str(segment).strip().lower(),
        )
        return self.session.execute(stmt).scalars().first()

    def count_items(self, watchlist_id: int) -> int:
        """Count total items currently in a watchlist."""
        stmt = select(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist_id)
        return len(list(self.session.execute(stmt).scalars().all()))

    def delete_item(self, item: WatchlistItem) -> None:
        """Remove a watchlist item."""
        self.session.delete(item)
        self.session.commit()


# Global Singleton Watchlist Repository
watchlist_repository = WatchlistRepository()
