"""Integration test configuration — requires real PostgreSQL and Redis.

These tests live OUTSIDE ``tests/`` so they are never collected by the offline
``pytest tests`` run and can never silently fall back to SQLite or eager Celery.
Set ``TEST_POSTGRES_URL`` and ``TEST_REDIS_URL`` to run them:

    $env:TEST_POSTGRES_URL = "postgresql+psycopg2://mbc_test:mbc_test_password@localhost:5433/mbc_test"
    $env:TEST_REDIS_URL   = "redis://localhost:6380/0"
    python -m pytest integration_tests -v
"""
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")
REDIS_URL = os.environ.get("TEST_REDIS_URL")

# Fail closed: a sqlite:// URL must never be accepted as integration infrastructure.
_HAVE_INFRA = (
    bool(POSTGRES_URL)
    and bool(REDIS_URL)
    and POSTGRES_URL.startswith("postgresql")
)

if _HAVE_INFRA:
    os.environ["DATABASE_URL"] = POSTGRES_URL
    os.environ["CELERY_BROKER_URL"] = REDIS_URL
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "false"
    os.environ["APP_ENV"] = "testing"
    os.environ["SECRET_KEY"] = os.environ.get("TEST_SECRET_KEY", "test-secret-key-0123456789abcdef")
    os.environ["AUDIT_HMAC_KEY"] = os.environ.get("TEST_AUDIT_HMAC_KEY", "test-audit-hmac-key-0123456789abcdef")
    os.environ["MFA_ENCRYPTION_KEY"] = os.environ.get("TEST_MFA_ENCRYPTION_KEY", "test-mfa-key-0123456789abcdef=")
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["AI_ENABLED"] = "true"
    os.environ["AI_PROVIDER"] = "mock"
    os.environ["AI_PHI_APPROVED"] = "false"
    # Deterministic mock output so both the in-process API and the external worker
    # produce the same single suggestion (F32.9) without any external AI call.
    os.environ["MOCK_PROVIDER_RESPONSE"] = (
        '{"diagnoses":[{"code":"F32.9","code_type":"icd10cm",'
        '"evidence":[{"quote":"major depressive disorder","start":0,"end":0}]}],'
        '"procedures":[],"modifiers":[],"missing_documentation":[],"contradictions":[]}'
    )


def pytest_collection_modifyitems(config, items):
    if not _HAVE_INFRA:
        skip = pytest.mark.skip(
            reason="TEST_POSTGRES_URL (postgresql://) and TEST_REDIS_URL are required"
        )
        for item in items:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def migrated_database():
    """Run migrations against the real PostgreSQL test database (fresh, disposable)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture()
def client(migrated_database):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def register(client):
    def _register(email: str, org_name: str) -> dict:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": org_name,
                "full_name": "Test Person",
                "email": email,
                "password": "correct-horse-battery-staple-123!",
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _register
