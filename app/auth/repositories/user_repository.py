from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository handling persistence and lookup for User entities."""

    def __init__(self, session: Optional[DbSession] = None) -> None:
        super().__init__(model_class=User, session=session)

    def get_by_username(self, username: str) -> Optional[User]:
        """Fetch user by case-insensitive matching username."""
        stmt = select(User).where(User.username == username.strip())
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> Optional[User]:
        """Fetch user by case-insensitive matching email."""
        stmt = select(User).where(User.email == email.strip().lower())
        return self.session.execute(stmt).scalar_one_or_none()
