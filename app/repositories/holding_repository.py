from typing import Any, List, Optional
from app.repositories.base import AbstractRepository


class HoldingRepository(AbstractRepository[Any]):
    """
    Repository contract for Demat / Long-term Holding portfolio storage.
    Inherits from AbstractRepository without instantiating premature domain models.
    """

    def get_by_id(self, entity_id: int) -> Optional[Any]:
        raise NotImplementedError("Holding domain model and persistence deferred to Portfolio Engine phase.")

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Any]:
        raise NotImplementedError("Holding domain model and persistence deferred to Portfolio Engine phase.")

    def add(self, entity: Any) -> Any:
        raise NotImplementedError("Holding domain model and persistence deferred to Portfolio Engine phase.")

    def update(self, entity: Any) -> Any:
        raise NotImplementedError("Holding domain model and persistence deferred to Portfolio Engine phase.")

    def delete(self, entity: Any) -> None:
        raise NotImplementedError("Holding domain model and persistence deferred to Portfolio Engine phase.")

    def count(self) -> int:
        raise NotImplementedError("Holding domain model and persistence deferred to Portfolio Engine phase.")
