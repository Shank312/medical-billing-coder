"""MFA configuration repository."""
from sqlalchemy import select

from ..models.mfa import MfaConfig
from .base import BaseRepository


class MfaRepository(BaseRepository):
    def get_for_user(self, user_id: str) -> MfaConfig | None:
        return self.db.execute(
            select(MfaConfig).where(MfaConfig.user_id == user_id)
        ).scalar_one_or_none()

    def create(self, *, user_id: str, secret_encrypted: str) -> MfaConfig:
        config = MfaConfig(user_id=user_id, secret_encrypted=secret_encrypted, enabled=False)
        self.db.add(config)
        self.db.flush()
        return config
