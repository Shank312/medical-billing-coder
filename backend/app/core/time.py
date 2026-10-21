"""Consistent time helpers.

All persisted timestamps use naive UTC (no ``tzinfo``). A single representation
avoids the SQLite vs PostgreSQL aware/naive datetime mismatch: SQLite returns
timezone-aware columns as naive datetimes, while PostgreSQL returns them aware.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return the current time as a naive UTC datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
