"""User repository."""
from sqlalchemy import select

from ..models.user import User
from .base import BaseRepository


class UserRepository(BaseRepository):
    def get(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    def create(
        self, *, email: str, full_name: str, password_hash: str, is_active: bool = True
    ) -> User:
        user = User(
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            is_active=is_active,
        )
        self.db.add(user)
        self.db.flush()
        return user
