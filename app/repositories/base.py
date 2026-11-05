from abc import ABC, abstractmethod
from typing import Generic, List, Optional, Type, TypeVar
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.base import BaseModel
from app.models.db import get_session

T = TypeVar("T", bound=BaseModel)


class AbstractRepository(ABC, Generic[T]):
    """
    Abstract Base Repository contract defining the domain persistence interface.
    All concrete repositories must adhere to this contract.
    """

    @abstractmethod
    def get_by_id(self, entity_id: int) -> Optional[T]:
        """Fetch a single record by its primary key."""
        pass

    @abstractmethod
    def list_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Fetch records with pagination."""
        pass

    @abstractmethod
    def add(self, entity: T) -> T:
        """Persist a new entity to storage."""
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        """Update and commit modifications to an existing entity."""
        pass

    @abstractmethod
    def delete(self, entity: T) -> None:
        """Remove an entity from storage."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Count total entities in storage."""
        pass


class BaseRepository(AbstractRepository[T]):
    """
    Concrete SQLAlchemy implementation of AbstractRepository
    providing standardized CRUD operations following the Data Mapper pattern.
    """

    def __init__(self, model_class: Type[T], session: Optional[Session] = None) -> None:
        self.model_class = model_class
        self._session_override = session

    @property
    def session(self) -> Session:
        """Obtain current active session (either custom or scoped session)."""
        if self._session_override is not None:
            return self._session_override
        return get_session()

    def get_by_id(self, entity_id: int) -> Optional[T]:
        stmt = select(self.model_class).where(self.model_class.id == entity_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        stmt = select(self.model_class).offset(offset).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def add(self, entity: T) -> T:
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def update(self, entity: T) -> T:
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def delete(self, entity: T) -> None:
        self.session.delete(entity)
        self.session.commit()

    def count(self) -> int:
        stmt = select(func.count()).select_from(self.model_class)
        return self.session.execute(stmt).scalar_one() or 0
