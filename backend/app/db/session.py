"""Database engine and session factory.

The engine is built once from ``Settings.database_url``. Tests set the
``DATABASE_URL`` environment variable before importing the app, which points the
engine at a SQLite file; production uses PostgreSQL.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..core.config import get_settings


def _build_engine(database_url: str):
    connect_args: dict = {}
    if database_url.startswith("sqlite"):
        # SQLite is used per-thread in tests; allow cross-thread access.
        connect_args["check_same_thread"] = False
    return create_engine(database_url, connect_args=connect_args, pool_pre_ping=True, future=True)


_settings = get_settings()
engine = _build_engine(_settings.database_url)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_db_session():
    """FastAPI dependency yielding a session and closing it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
