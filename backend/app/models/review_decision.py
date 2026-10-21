"""Append-only human review decisions for coding suggestions."""
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base
from .base import TimestampMixin, UUIDPrimaryKeyMixin


class ReviewDecision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "review_decisions"

    suggestion_id: Mapped[str] = mapped_column(
        ForeignKey("coding_suggestions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    encounter_id: Mapped[str] = mapped_column(
        ForeignKey("encounters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reviewer_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[str] = mapped_column(String(30), nullable=False)  # approved|rejected|corrected|reverted
    corrected_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
