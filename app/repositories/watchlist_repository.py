from typing import Any, List, Optional
from app.repositories.base import AbstractRepository


class WatchlistRepository(AbstractRepository[Any]):
    """
    Repository contract for Watchlist and Market Watch symbol sets.
    Inherits from AbstractRepository without instantiating premature domain models.
    """

    def get_by_id(self, entity_id: int) -> Optional[Any]:
        raise NotImplementedError("Watchlist domain model and persistence deferred to Market Watch phase.")

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Any]:
        raise NotImplementedError("Watchlist domain model and persistence deferred to Market Watch phase.")

    def add(self, entity: Any) -> Any:
        raise NotImplementedError("Watchlist domain model and persistence deferred to Market Watch phase.")

    def update(self, entity: Any) -> Any:
        raise NotImplementedError("Watchlist domain model and persistence deferred to Market Watch phase.")

    def delete(self, entity: Any) -> None:
        raise NotImplementedError("Watchlist domain model and persistence deferred to Market Watch phase.")

    def count(self) -> int:
        raise NotImplementedError("Watchlist domain model and persistence deferred to Market Watch phase.")
