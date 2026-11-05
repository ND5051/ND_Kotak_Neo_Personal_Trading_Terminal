from typing import Generic, List, Optional, Type, TypeVar
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.base import BaseModel
from app.models.db import db_session

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """
    Generic Base Repository providing standardized CRUD operations
    following the Repository Pattern and Data Mapper architecture.
    """

    def __init__(self, model_class: Type[T], session: Optional[Session] = None) -> None:
        self.model_class = model_class
        self._session_override = session

    @property
    def session(self) -> Session:
        """Obtain current active session (either custom or scoped session)."""
        if self._session_override is not None:
            return self._session_override
        if db_session is None:
            raise RuntimeError("Database session not initialized. Call init_db() first.")
        return db_session()

    def get_by_id(self, entity_id: int) -> Optional[T]:
        """Fetch a single record by its primary key."""
        stmt = select(self.model_class).where(self.model_class.id == entity_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Fetch records with pagination."""
        stmt = select(self.model_class).offset(offset).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def add(self, entity: T) -> T:
        """Persist a new entity to the database."""
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def update(self, entity: T) -> T:
        """Update and commit modifications to an existing entity."""
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def delete(self, entity: T) -> None:
        """Remove an entity from the database."""
        self.session.delete(entity)
        self.session.commit()

    def count(self) -> int:
        """Count total entities in table."""
        stmt = select(func.count()).select_from(self.model_class)
        return self.session.execute(stmt).scalar_one() or 0

