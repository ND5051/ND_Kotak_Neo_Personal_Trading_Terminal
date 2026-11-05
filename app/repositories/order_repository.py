from typing import Optional
from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository


class OrderRepository(BaseRepository):
    """Repository skeleton for Order persistence and state recovery."""

    def __init__(self, session: Optional[Session] = None) -> None:
        # Model class will be injected in Phase 2 / Phase 3 once domain models are defined
        super().__init__(model_class=None, session=session)  # type: ignore

