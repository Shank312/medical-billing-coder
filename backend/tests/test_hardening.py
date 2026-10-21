"""Security and hardening tests (Phase 7)."""
import json
import os
import tempfile

import pytest

from app.ai.mock import MockProvider
from app.core.config import Settings
from app.storage import LocalFileStorage, StorageError, generate_storage_key

TEST_PASSWORD = "correct-horse-battery-staple-123!"
NOTE = "Patient presents with major depressive disorder."

MOCK_OUTPUT = json.dumps(
    {
        "diagnoses": [
            {"code": "F32.9", "code_type": "icd10cm", "evidence": [{"quote": "major depressive disorder", "start": 0, "end": 0}]}
        ],
        "procedures": [],
        "modifiers": [],
        "missing_documentation": [],
        "contradictions": [],
    }
)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, email):
    response = client.post(
        "/api/v1/auth/register",
        json={"organization_name": f"Org {email}", "full_name": "Person", "email": email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _prod_settings(**overrides):
    base = dict(
        app_env="production",
        secret_key="real-secret-key-0123456789abcdef",
        audit_hmac_key="real-audit-hmac-0123456789abcdef",
        mfa_encryption_key="real-mfa-key-0123456789abcdef=",
        cookie_secure=True,
        cors_origins=["https://app.example.com"],
    )
    base.update(overrides)
    return Settings(**base)


def test_production_config_accepts_secure_values():
    settings = _prod_settings()
    assert settings.is_production


def test_production_config_rejects_dev_secret():
    with pytest.raises(ValueError):
        _prod_settings(secret_key="dev-only-insecure-secret-change-me")


def test_production_config_rejects_empty_mfa_key():
    with pytest.raises(ValueError):
        _prod_settings(mfa_encryption_key="")


def test_production_config_requires_cookie_secure():
    with pytest.raises(ValueError):
        _prod_settings(cookie_secure=False)


def test_production_config_rejects_wildcard_cors():
    with pytest.raises(ValueError):
        _prod_settings(cors_origins=["*"])


def test_security_headers_present(client):
    response = client.get("/health/live")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_health_endpoints(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_storage_path_traversal_rejected():
    storage = LocalFileStorage(os.path.join(tempfile.gettempdir(), "mbc_path_test"))
    key = generate_storage_key()
    assert len(key) == 64
    assert storage._path(key).name == key
    with pytest.raises(StorageError):
        storage._path("../../etc/passwd")
    with pytest.raises(StorageError):
        storage._path("a/b/c")


def test_formula_injection_control_characters():
    from app.services.exports import sanitize_cell

    assert sanitize_cell("\t=SUM(A1)") == "'\t=SUM(A1)"
    assert sanitize_cell("\r=SUM(A1)") == "'\r=SUM(A1)"
    assert sanitize_cell("\n=SUM(A1)") == "'\n=SUM(A1)"
    assert sanitize_cell("   +SUM(A1)") == "'   +SUM(A1)"
    assert sanitize_cell("-normal") == "'-normal"


def test_export_does_not_invoke_ai_provider(client, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(response_json=MOCK_OUTPUT))
    data = _register(client, "owner@exportnoai.example.com")
    token = data["access_token"]
    encounter = client.post("/api/v1/encounters", json={"date_of_service": "2025-03-15", "note": NOTE}, headers=_auth(token)).json()
    client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=_auth(token))

    def boom():
        raise AssertionError("AI provider must not be invoked during export")

    monkeypatch.setattr("app.services.coding.get_provider", boom)
    response = client.get("/api/v1/encounters/export.csv", headers=_auth(token))
    assert response.status_code == 200


def test_cross_tenant_review_forbidden(client, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(response_json=MOCK_OUTPUT))
    a = _register(client, "a@reviewiso.example.com")
    b = _register(client, "b@reviewiso.example.com")
    encounter = client.post("/api/v1/encounters", json={"date_of_service": "2025-03-15", "note": NOTE}, headers=_auth(a["access_token"])).json()
    client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=_auth(a["access_token"]))
    detail = client.get(f"/api/v1/encounters/{encounter['id']}", headers=_auth(a["access_token"])).json()
    suggestion_id = detail["suggestions"][0]["id"]

    response = client.post(
        f"/api/v1/encounters/{encounter['id']}/suggestions/{suggestion_id}/review",
        json={"decision": "approved"},
        headers=_auth(b["access_token"]),
    )
    assert response.status_code == 404
