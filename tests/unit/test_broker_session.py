from datetime import datetime, timedelta, timezone
import pytest

from app.auth.models.user import User
from app.broker.adapters.kotak_adapter import KotakBrokerAdapter
from app.broker.models.broker_session import BrokerSession
from app.broker.repositories.broker_session_repository import BrokerSessionRepository
from app.broker.services.broker_session_manager import BrokerSessionManager
from app.core.encryption import EncryptionService
from app.models.db import init_db, create_all_tables, get_db_session


@pytest.fixture(autouse=True)
def setup_db():
    init_db(database_url="sqlite:///:memory:")
    create_all_tables()


def test_broker_session_manager_create():
    """Verify broker session creation encrypts tokens and persists active record."""
    with get_db_session() as session:
        user = User(username="broker_trader", email="broker@dev.local")
        user.set_password("SecretPassword123!")
        session.add(user)
        session.commit()

        repo = BrokerSessionRepository(session)
        enc = EncryptionService(key="test-secure-encryption-key-12345")
        mgr = BrokerSessionManager(repository=repo, encryption=enc)

        token = "raw_plaintext_kotak_token_999"
        refresh = "raw_plaintext_refresh_token_888"

        b_sess = mgr.create_session(
            user_id=user.id,
            session_token=token,
            refresh_token=refresh,
            expiry_time=datetime.now(timezone.utc) + timedelta(hours=6),
            actor=user.username,
        )

        assert b_sess.id is not None
        assert b_sess.user_id == user.id
        assert b_sess.is_active is True
        # Ensure plaintext tokens are NEVER stored directly in DB fields
        assert b_sess.session_token_encrypted != token
        assert b_sess.refresh_token_encrypted != refresh
        # Ensure decryption recovers the original plaintext
        assert enc.decrypt(b_sess.session_token_encrypted) == token
        assert enc.decrypt(b_sess.refresh_token_encrypted) == refresh


def test_broker_session_recovery_valid():
    """Verify session recovery decrypts tokens and invokes adapter restore."""
    with get_db_session() as session:
        user = User(username="recover_trader", email="rec@dev.local")
        user.set_password("SecretPassword123!")
        session.add(user)
        session.commit()

        repo = BrokerSessionRepository(session)
        enc = EncryptionService(key="test-secure-encryption-key-12345")
        mgr = BrokerSessionManager(repository=repo, encryption=enc)

        b_sess = mgr.create_session(
            user_id=user.id,
            session_token="token_to_recover",
            refresh_token="refresh_to_recover",
            expiry_time=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        adapter = KotakBrokerAdapter()
        restored = mgr.restore_session(user_id=user.id, adapter=adapter)

        assert restored is True
        assert adapter.is_connected() is True
        assert adapter._session_token == "token_to_recover"


def test_broker_session_recovery_expired_rejected():
    """Verify expired broker sessions are rejected and marked inactive during recovery."""
    with get_db_session() as session:
        user = User(username="expired_broker_trader", email="expb@dev.local")
        user.set_password("SecretPassword123!")
        session.add(user)
        session.commit()

        repo = BrokerSessionRepository(session)
        enc = EncryptionService(key="test-secure-encryption-key-12345")
        mgr = BrokerSessionManager(repository=repo, encryption=enc)

        # Create session with past expiry
        b_sess = mgr.create_session(
            user_id=user.id,
            session_token="old_token",
            expiry_time=datetime.now(timezone.utc) - timedelta(minutes=10),
        )

        adapter = KotakBrokerAdapter()
        restored = mgr.restore_session(user_id=user.id, adapter=adapter)

        assert restored is False
        assert adapter.is_connected() is False


def test_broker_session_destroy():
    """Verify session destruction calls adapter logout and invalidates persistence record."""
    with get_db_session() as session:
        user = User(username="destroy_b_trader", email="desb@dev.local")
        user.set_password("SecretPassword123!")
        session.add(user)
        session.commit()

        repo = BrokerSessionRepository(session)
        enc = EncryptionService(key="test-secure-encryption-key-12345")
        mgr = BrokerSessionManager(repository=repo, encryption=enc)

        mgr.create_session(user_id=user.id, session_token="active_token_123")

        adapter = KotakBrokerAdapter()
        adapter.login({"consumer_key": "k", "consumer_secret": "s"})
        assert adapter.is_connected() is True

        destroyed = mgr.destroy_session(user_id=user.id, adapter=adapter)
        assert destroyed is True
        assert adapter.is_connected() is False
        assert repo.get_active_session(user_id=user.id) is None

