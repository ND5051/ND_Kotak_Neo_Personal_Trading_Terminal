from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional
from flask import Flask, g
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, Session

from app.models.base import Base
from app.logging.logger import get_logger

logger = get_logger("app.models.db")

engine = None
SessionFactory = None
db_session = None


def get_engine():
    """Retrieve the global SQLAlchemy engine instance."""
    return engine


def get_session() -> Session:
    """Retrieve the active scoped database session."""
    if db_session is None:
        raise RuntimeError("Database session not initialized. Call init_db() first.")
    return db_session()


def init_db(app: Optional[Flask] = None, database_url: Optional[str] = None) -> None:
    """Initialize the database engine and scoped session."""
    global engine, SessionFactory, db_session

    if app is not None:
        db_uri = app.config.get("DATABASE_URL")
    else:
        db_uri = database_url

    if not db_uri:
        db_uri = "sqlite:///data/kotak_terminal.db"

    # Ensure SQLite directory exists if file-based
    if db_uri.startswith("sqlite:///") and not db_uri.startswith("sqlite:///:memory:"):
        db_file = db_uri.replace("sqlite:///", "")
        db_path = Path(db_file)
        db_path.parent.mkdir(parents=True, exist_ok=True)

    connect_args = {}
    engine_kwargs = {"future": True, "echo": False}

    if db_uri.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if db_uri == "sqlite:///:memory:":
            from sqlalchemy.pool import StaticPool
            engine_kwargs["poolclass"] = StaticPool

    engine = create_engine(
        db_uri,
        connect_args=connect_args,
        **engine_kwargs,
    )

    SessionFactory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        future=True,
    )
    db_session = scoped_session(SessionFactory)

    logger.info(
        f"Database initialized with URI: {db_uri}",
        event="DATABASE_INITIALIZED",
        db_uri=db_uri,
    )

    if app is not None:
        # Register teardown to remove scoped session at the end of each request
        @app.teardown_appcontext
        def shutdown_session(exception=None):
            if db_session is not None:
                db_session.remove()


def create_all_tables() -> None:
    """Create all registered tables. Intended for development / test environments."""
    if engine is None:
        raise RuntimeError("Database engine is not initialized. Call init_db() first.")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema tables checked/created", event="DATABASE_SCHEMA_SYNC")


def drop_all_tables() -> None:
    """Drop all tables. Intended for test cleanup."""
    if engine is not None:
        Base.metadata.drop_all(bind=engine)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    if SessionFactory is None:
        raise RuntimeError("Database engine is not initialized. Call init_db() first.")
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
