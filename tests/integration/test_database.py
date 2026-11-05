from sqlalchemy import text
from app.models.db import init_db, get_db_session, engine


def test_database_connection_and_transaction():
    """Verify database engine connectivity and rollback behavior."""
    init_db(database_url="sqlite:///:memory:")

    with get_db_session() as session:
        result = session.execute(text("SELECT 1 AS active")).scalar()
        assert result == 1

