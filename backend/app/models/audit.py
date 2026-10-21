"""Append-only audit events with a tamper-evident hash chain.

``occurred_at`` is stored as an ISO-8601 UTC string (not a DB datetime) so the
value participates in the hash deterministically across SQLite and PostgreSQL.
The chain is global within a deployment; ``organization_id`` scopes queries.
"""
from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base

# BigInteger on PostgreSQL (BIGSERIAL), Integer on SQLite (INTEGER PRIMARY KEY
# autoincrement — SQLite only autoincrements exact "INTEGER PRIMARY KEY").
_AUDIT_ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(_AUDIT_ID_TYPE, primary_key=True, autoincrement=True)
    organization_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    occurred_at: Mapped[str] = mapped_column(String(40), index=True, nullable=False)


class AuditChainState(Base):
    """Singleton row (id=1) holding the head hash of the audit chain."""

    __tablename__ = "audit_chain_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)
