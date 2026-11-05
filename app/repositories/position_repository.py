from typing import Optional
from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository


class PositionRepository(BaseRepository):
    """Repository skeleton for Trading Position persistence and snapshot reconciliation."""

    def __init__(self, session: Optional[Session] = None) -> None:
        super().__init__(model_class=None, session=session)  # type: ignore

