from typing import Optional
from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository


class HoldingRepository(BaseRepository):
    """Repository skeleton for Demat / Long-term Holding portfolio storage."""

    def __init__(self, session: Optional[Session] = None) -> None:
        super().__init__(model_class=None, session=session)  # type: ignore

