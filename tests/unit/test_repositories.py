from sqlalchemy import Column, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel
from app.repositories.base import BaseRepository
from app.models.db import init_db, create_all_tables, get_db_session


class SampleEntity(BaseModel):
    """Test model for repository framework verification."""
    __tablename__ = "sample_test_entities"

    name: Mapped[str] = mapped_column(String(50), nullable=False)


def test_base_repository_crud():
    """Verify BaseRepository CRUD operations on in-memory SQLite."""
    init_db(database_url="sqlite:///:memory:")
    create_all_tables()

    with get_db_session() as session:
        repo = BaseRepository(SampleEntity, session=session)

        # 1. Create / Add
        entity = SampleEntity(name="RELIANCE")
        persisted = repo.add(entity)
        assert persisted.id is not None
        assert persisted.name == "RELIANCE"

        # 2. Read by ID
        fetched = repo.get_by_id(persisted.id)
        assert fetched is not None
        assert fetched.name == "RELIANCE"

        # 3. Count & List
        assert repo.count() == 1
        all_entities = repo.list_all()
        assert len(all_entities) == 1

        # 4. Update
        fetched.name = "TCS"
        updated = repo.update(fetched)
        assert updated.name == "TCS"

        # 5. Delete
        repo.delete(updated)
        assert repo.count() == 0
        assert repo.get_by_id(persisted.id) is None

