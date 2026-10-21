"""Refresh token repository."""
from datetime import datetime

from sqlalchemy import select, update

from ..models.refresh_token import RefreshToken
from .base import BaseRepository


class RefreshTokenRepository(BaseRepository):
    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).scalar_one_or_none()

    def create(
        self,
        *,
        user_id: str,
        organization_id: str,
        token_hash: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            organization_id=organization_id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(token)
        self.db.flush()
        return token

    def revoke_all_for_user_org(
        self, user_id: str, organization_id: str, revoked_at: datetime
    ) -> None:
        self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.organization_id == organization_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
