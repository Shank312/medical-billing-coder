"""Coding suggestions (diagnoses, procedures, modifiers) and their evidence spans."""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base
from .base import TimestampMixin, UUIDPrimaryKeyMixin


class CodingSuggestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "coding_suggestions"

    encounter_id: Mapped[str] = mapped_column(
        ForeignKey("encounters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_id: Mapped[str] = mapped_column(
        ForeignKey("coding_jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code_type: Mapped[str] = mapped_column(String(30), nullable=False)  # icd10cm|cpt|hcpcs|modifier
    code: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    applies_to: Mapped[str | None] = mapped_column(String(20), nullable=True)
    parent_suggestion_id: Mapped[str | None] = mapped_column(
        ForeignKey("coding_suggestions.id", ondelete="SET NULL"), nullable=True
    )
    validation_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    review_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    corrected_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    flags_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class EvidenceSpan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evidence_spans"

    suggestion_id: Mapped[str] = mapped_column(
        ForeignKey("coding_suggestions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
