"""Encounter model (tenant-scoped). Stores minimal context, never unnecessary PHI."""
from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base
from .base import TimestampMixin, UUIDPrimaryKeyMixin


class Encounter(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "encounters"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    date_of_service: Mapped[date] = mapped_column(Date, nullable=False)
    encounter_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    place_of_service: Mapped[str | None] = mapped_column(String(20), nullable=True)
    patient_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payer_context: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
