import pytest
from app.auth.models.user import User
from app.auth.services.auth_service import AuthService
from app.auth.repositories.user_repository import UserRepository
from app.core.exceptions import ValidationException
from app.models.db import init_db, create_all_tables, get_db_session


@pytest.fixture(autouse=True)
def setup_db():
    init_db(database_url="sqlite:///:memory:")
    create_all_tables()


def test_create_user_and_salted_password_hash():
    """Verify user creation with salted password hashing and no plaintext storage."""
    with get_db_session() as session:
        auth = AuthService(user_repository=UserRepository(session))
        user = auth.register_user(
            username="trader_alpha",
            email="alpha@terminal.local",
            password="StrongPassword123!",
        )

        assert user.id is not None
        assert user.username == "trader_alpha"
        assert user.email == "alpha@terminal.local"
        assert user.is_active is True
        assert user.password_hash != "StrongPassword123!"
        assert user.password_hash.startswith("scrypt:") or user.password_hash.startswith("pbkdf2:")


def test_password_validation():
    """Verify positive and negative password verification."""
    user = User(username="test_user", email="test@local.dev")
    user.set_password("MySecurePass#456")

    assert user.check_password("MySecurePass#456") is True
    assert user.check_password("WrongPassword") is False
    assert user.check_password("") is False


def test_failed_login_bad_credentials():
    """Verify that nonexistent user or bad password raises ValidationException."""
    with get_db_session() as session:
        auth = AuthService(user_repository=UserRepository(session))
        auth.register_user("trader_beta", "beta@terminal.local", "BetaPassword123")

        # Wrong password
        with pytest.raises(ValidationException) as exc_info:
            auth.authenticate_user("trader_beta", "WrongPassword!")
        assert "Invalid credentials" in str(exc_info.value)

        # Nonexistent user
        with pytest.raises(ValidationException) as exc_info:
            auth.authenticate_user("nonexistent_user", "AnyPassword123")
        assert "Invalid credentials" in str(exc_info.value)


def test_disabled_user_login_rejection():
    """Verify that disabled users cannot authenticate."""
    with get_db_session() as session:
        from app.auth.repositories.session_repository import SessionRepository
        from app.auth.services.session_manager import SessionManager

        user_repo = UserRepository(session)
        sess_repo = SessionRepository(session)
        sess_mgr = SessionManager(session_repository=sess_repo)
        auth = AuthService(user_repository=user_repo, sess_manager=sess_mgr)
        user = auth.register_user("disabled_trader", "disabled@terminal.local", "SecretPass123!")

        # Disable user
        auth.disable_user(user.id)

        with pytest.raises(ValidationException) as exc_info:
            auth.authenticate_user("disabled_trader", "SecretPass123!")
        assert "disabled" in str(exc_info.value).lower()

        # Re-enable user
        auth.enable_user(user.id)
        user_auth, sess = auth.authenticate_user("disabled_trader", "SecretPass123!")
        assert user_auth.id == user.id
        assert sess is not None
