"""Versioned code-reference datasets (global, not tenant-scoped)."""
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base
from .base import TimestampMixin, UUIDPrimaryKeyMixin


class CodeReferenceSet(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "code_reference_sets"
    __table_args__ = (
        UniqueConstraint("code_type", "source", "version", name="uq_code_ref_set_type_source_version"),
    )

    code_type: Mapped[str] = mapped_column(String(30), nullable=False)  # icd10cm|cpt|hcpcs
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    effective_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class CodeReference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "code_references"
    __table_args__ = (UniqueConstraint("set_id", "code", name="uq_code_reference_set_code"),)

    set_id: Mapped[str] = mapped_column(
        ForeignKey("code_reference_sets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    effective_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_billable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
