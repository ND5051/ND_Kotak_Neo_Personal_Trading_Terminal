from typing import Any, List, Optional
from app.repositories.base import AbstractRepository


class OrderRepository(AbstractRepository[Any]):
    """
    Repository contract for Order persistence and state recovery.
    Inherits from AbstractRepository without instantiating premature domain models.
    """

    def get_by_id(self, entity_id: int) -> Optional[Any]:
        raise NotImplementedError("Order domain model and persistence deferred to Order Engine phase.")

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Any]:
        raise NotImplementedError("Order domain model and persistence deferred to Order Engine phase.")

    def add(self, entity: Any) -> Any:
        raise NotImplementedError("Order domain model and persistence deferred to Order Engine phase.")

    def update(self, entity: Any) -> Any:
        raise NotImplementedError("Order domain model and persistence deferred to Order Engine phase.")

    def delete(self, entity: Any) -> None:
        raise NotImplementedError("Order domain model and persistence deferred to Order Engine phase.")

    def count(self) -> int:
        raise NotImplementedError("Order domain model and persistence deferred to Order Engine phase.")
