from datetime import datetime, timedelta, timezone
import pytest

from app.auth.services.session_manager import SessionManager
from app.auth.repositories.session_repository import SessionRepository
from app.models.db import init_db, create_all_tables, get_db_session
from app.auth.models.user import User


@pytest.fixture(autouse=True)
def setup_db():
    init_db(database_url="sqlite:///:memory:")
    create_all_tables()


def test_session_creation():
    """Verify session creation produces active session with valid expiration."""
    with get_db_session() as session:
        user = User(username="sess_trader", email="sess@dev.local")
        user.set_password("ValidPassword123")
        session.add(user)
        session.commit()

        mgr = SessionManager(session_repository=SessionRepository(session))
        sess = mgr.create_session(user_id=user.id, duration_hours=12)

        assert sess.id is not None
        assert len(sess.session_id) >= 32
        assert sess.user_id == user.id
        assert sess.is_active is True
        assert sess.is_expired() is False


def test_session_validation_and_touch():
    """Verify session validation touches last activity."""
    with get_db_session() as session:
        user = User(username="touch_user", email="touch@dev.local")
        user.set_password("ValidPassword123")
        session.add(user)
        session.commit()

        mgr = SessionManager(session_repository=SessionRepository(session))
        sess = mgr.create_session(user_id=user.id, duration_hours=24)
        original_activity = sess.last_activity

        validated = mgr.validate_session(sess.session_id)
        assert validated is not None
        assert validated.session_id == sess.session_id
        assert validated.is_active is True


def test_session_expiry():
    """Verify expired session cannot be validated and becomes deactivated."""
    with get_db_session() as session:
        user = User(username="expired_trader", email="expired@dev.local")
        user.set_password("ValidPassword123")
        session.add(user)
        session.commit()

        repo = SessionRepository(session)
        mgr = SessionManager(session_repository=repo)
        sess = mgr.create_session(user_id=user.id, duration_hours=1)

        # Manually force expires_at into the past
        sess.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        repo.update(sess)

        # Validation must return None
        validated = mgr.validate_session(sess.session_id)
        assert validated is None

        # Session should now be marked inactive
        reloaded = repo.get_by_session_id(sess.session_id)
        assert reloaded.is_active is False
        assert reloaded.is_expired() is True


def test_session_destroy():
    """Verify manual destruction marks session inactive."""
    with get_db_session() as session:
        user = User(username="destroy_trader", email="destroy@dev.local")
        user.set_password("ValidPassword123")
        session.add(user)
        session.commit()

        mgr = SessionManager(session_repository=SessionRepository(session))
        sess = mgr.create_session(user_id=user.id, duration_hours=24)

        assert mgr.destroy_session(sess.session_id) is True
        assert mgr.validate_session(sess.session_id) is None
