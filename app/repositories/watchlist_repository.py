from typing import Optional
from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository


class WatchlistRepository(BaseRepository):
    """Repository skeleton for Watchlist and Market Watch symbol sets."""

    def __init__(self, session: Optional[Session] = None) -> None:
        super().__init__(model_class=None, session=session)  # type: ignore

