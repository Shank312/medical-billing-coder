"""Pytest configuration.

Environment is set BEFORE importing the app so the engine binds to a disposable
SQLite file. Tables are reset before each test for isolation.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend dir

_TEST_DB = Path(__file__).resolve().parent / ".test_mbc.db"
if _TEST_DB.exists():
    _TEST_DB.unlink()

os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef"
os.environ["AUDIT_HMAC_KEY"] = "test-audit-hmac-key-0123456789abcdef"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "15"
os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = "30"

from cryptography.fernet import Fernet  # noqa: E402

os.environ["MFA_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402

TEST_PASSWORD = "correct-horse-battery-staple-123!"


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def register(client):
    def _register(email: str, org_name: str, password: str = TEST_PASSWORD) -> dict:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": org_name,
                "full_name": "Test Person",
                "email": email,
                "password": password,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _register


@pytest.fixture()
def auth_headers():
    def _headers(access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    return _headers
