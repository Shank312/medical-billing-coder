"""Infrastructure integration tests (Phase 7).

These tests are SKIPPED unless real infrastructure is provided via environment
variables. They are never run against SQLite or eager Celery — a skip here is an
honest signal that real PostgreSQL/Redis verification did not happen in this run.

To run them:
    $env:TEST_POSTGRES_URL = "postgresql+psycopg2://user:pass@localhost:5432/mbc_test"
    $env:TEST_REDIS_URL = "redis://localhost:6379/0"
    python -m pytest tests/test_integration_infra.py -v
"""
import os

import pytest
from sqlalchemy import create_engine, text

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")
REDIS_URL = os.environ.get("TEST_REDIS_URL")

needs_postgres = pytest.mark.skipif(POSTGRES_URL is None, reason="TEST_POSTGRES_URL not set")
needs_redis = pytest.mark.skipif(REDIS_URL is None, reason="TEST_REDIS_URL not set")


@needs_postgres
def test_postgres_connectivity():
    engine = create_engine(POSTGRES_URL)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1


@needs_postgres
def test_postgres_transaction_rollback():
    engine = create_engine(POSTGRES_URL)
    with engine.connect() as conn:
        trans = conn.begin()
        conn.execute(text("CREATE TABLE IF NOT EXISTS _mbc_probe (id integer)"))
        conn.execute(text("INSERT INTO _mbc_probe (id) VALUES (1)"))
        trans.rollback()
        # rolled-back insert must not be visible
        result = conn.execute(text("SELECT count(*) FROM _mbc_probe")).scalar()
        assert result == 0


@needs_redis
def test_redis_ping_and_ttl():
    import redis

    client = redis.Redis.from_url(REDIS_URL)
    assert client.ping()
    client.set("_mbc_probe", "1", ex=10)
    assert client.get("_mbc_probe") == b"1"
    assert client.ttl("_mbc_probe") > 0
    client.delete("_mbc_probe")
