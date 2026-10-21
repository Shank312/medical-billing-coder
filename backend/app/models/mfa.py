"""TOTP MFA configuration (secret stored encrypted)."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base
from .base import TimestampMixin


class MfaConfig(Base, TimestampMixin):
    __tablename__ = "mfa_configs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    secret_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
