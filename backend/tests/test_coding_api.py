"""Coding API integration tests: workflow, tenant isolation, RBAC, idempotency,
audit/redaction, and the AI transmission gates."""
import json

from sqlalchemy import select

from app.ai.mock import MockProvider
from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.audit import AuditEvent

TEST_PASSWORD = "correct-horse-battery-staple-123!"

NOTE = (
    "Patient presents with major depressive disorder. A 45 minute psychotherapy "
    "session was performed via telehealth."
)

MOCK_OUTPUT = json.dumps(
    {
        "diagnoses": [
            {
                "code": "F32.9",
                "code_type": "icd10cm",
                "description": "Major depressive disorder, recurrent, unspecified",
                "confidence": 0.9,
                "rationale": "documented",
                "evidence": [{"quote": "major depressive disorder", "start": 0, "end": 0}],
            }
        ],
        "procedures": [
            {
                "code": "90837",
                "code_type": "cpt",
                "description": "Psychotherapy, 60 minutes",
                "confidence": 0.8,
                "rationale": "time documented",
                "evidence": [{"quote": "45 minute psychotherapy session", "start": 0, "end": 0}],
            }
        ],
        "modifiers": [],
        "missing_documentation": ["Exact start/stop times not documented"],
        "contradictions": [],
    }
)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _patch_provider(monkeypatch, response_json=MOCK_OUTPUT):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(response_json=response_json))


def _create_encounter(client, token, note=NOTE):
    response = client.post(
        "/api/v1/encounters",
        json={"date_of_service": "2025-03-15", "note": note},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _import(client, token, code_type, codes):
    response = client.post(
        "/api/v1/code-references/import",
        json={
            "code_type": code_type,
            "source": "SYNTHETIC_TEST",
            "version": "2025.1",
            "codes": codes,
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _add_member(client, owner_token, org_id, email, role):
    response = client.post(
        f"/api/v1/organizations/{org_id}/users",
        json={"email": email, "full_name": "Member", "role": role},
        headers=_auth(owner_token),
    )
    assert response.status_code == 201, response.text


def _login_as(client, email, org_id):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_PASSWORD, "organization_id": org_id},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_encounter_and_coding_flow(client, register, monkeypatch):
    _patch_provider(monkeypatch)
    owner = register("owner@flow.example.com", "Flow Org")
    token = owner["access_token"]
    _import(client, token, "icd10cm", [{"code": "F32.9", "description": "MDD"}])
    _import(client, token, "cpt", [{"code": "90837", "description": "Psychotherapy 60 min"}])

    encounter = _create_encounter(client, token)
    job = client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=_auth(token)).json()
    assert job["status"] == "completed"
    assert job["schema_version"] == "1.0.0"

    suggestions = {s["code"]: s for s in job["suggestions"]}
    assert "F32.9" in suggestions
    assert suggestions["F32.9"]["code_type"] == "icd10cm"
    assert suggestions["F32.9"]["validation_status"] == "valid"
    assert suggestions["F32.9"]["evidence"][0]["quote"] == "major depressive disorder"
    assert "90837" in suggestions
    assert suggestions["90837"]["code_type"] == "cpt"

    fetched = client.get(f"/api/v1/coding-jobs/{job['id']}", headers=_auth(token))
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "completed"


def test_idempotency(client, register, monkeypatch):
    _patch_provider(monkeypatch)
    owner = register("owner@idem.example.com", "Idem Org")
    token = owner["access_token"]
    encounter = _create_encounter(client, token)

    headers = {**_auth(token), "Idempotency-Key": "req-123"}
    first = client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=headers)
    second = client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_tenant_isolation(client, register, monkeypatch):
    _patch_provider(monkeypatch)
    org_a = register("a@iso.example.com", "Org A")
    org_b = register("b@iso.example.com", "Org B")
    encounter_a = _create_encounter(client, org_a["access_token"])
    job_a = client.post(
        f"/api/v1/encounters/{encounter_a['id']}/code", headers=_auth(org_a["access_token"])
    ).json()

    assert client.get(f"/api/v1/encounters/{encounter_a['id']}", headers=_auth(org_b["access_token"])).status_code == 404
    assert client.get(f"/api/v1/coding-jobs/{job_a['id']}", headers=_auth(org_b["access_token"])).status_code == 404

    listing = client.get("/api/v1/encounters", headers=_auth(org_b["access_token"]))
    assert listing.status_code == 200
    assert all(item["id"] != encounter_a["id"] for item in listing.json()["items"])


def test_rbac_review(client, register, monkeypatch):
    _patch_provider(monkeypatch)
    owner = register("owner@rbac.example.com", "Rbac Org")
    token = owner["access_token"]
    org_id = owner["organization"]["id"]

    register("ro@rbac.example.com", "RO Org")
    register("coder@rbac.example.com", "Coder Org")
    _add_member(client, token, org_id, "ro@rbac.example.com", "read_only")
    _add_member(client, token, org_id, "coder@rbac.example.com", "coder")

    ro_token = _login_as(client, "ro@rbac.example.com", org_id)
    coder_token = _login_as(client, "coder@rbac.example.com", org_id)

    encounter = _create_encounter(client, token)
    job = client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=_auth(token)).json()
    suggestion_id = job["suggestions"][0]["id"]

    denied = client.post(
        f"/api/v1/encounters/{encounter['id']}/suggestions/{suggestion_id}/review",
        json={"decision": "approved"},
        headers=_auth(ro_token),
    )
    assert denied.status_code == 403

    approved = client.post(
        f"/api/v1/encounters/{encounter['id']}/suggestions/{suggestion_id}/review",
        json={"decision": "approved"},
        headers=_auth(coder_token),
    )
    assert approved.status_code == 200
    assert approved.json()["review_status"] == "approved"


def test_reference_import_rbac(client, register):
    owner = register("owner@refrbac.example.com", "Ref Rbac Org")
    org_id = owner["organization"]["id"]
    register("ro@refrbac.example.com", "RO Org")
    _add_member(client, owner["access_token"], org_id, "ro@refrbac.example.com", "read_only")
    ro_token = _login_as(client, "ro@refrbac.example.com", org_id)

    response = client.post(
        "/api/v1/code-references/import",
        json={
            "code_type": "icd10cm",
            "source": "SYNTHETIC",
            "version": "2025.1",
            "codes": [{"code": "F32.9", "description": "MDD"}],
        },
        headers=_auth(ro_token),
    )
    assert response.status_code == 403


def test_reference_lookup_and_date_validity(client, register):
    owner = register("owner@ref.example.com", "Ref Org")
    token = owner["access_token"]

    before = client.get(
        "/api/v1/code-references/lookup",
        params={"code_type": "icd10cm", "code": "F32.9"},
        headers=_auth(token),
    )
    assert before.json()["status"] == "reference_data_unavailable"

    imported = client.post(
        "/api/v1/code-references/import",
        json={
            "code_type": "icd10cm",
            "source": "SYNTHETIC_TEST",
            "version": "2025.1",
            "codes": [{"code": "F32.9", "description": "MDD", "effective_start": "2025-01-01"}],
        },
        headers=_auth(token),
    )
    assert imported.status_code == 201

    valid = client.get(
        "/api/v1/code-references/lookup",
        params={"code_type": "icd10cm", "code": "F32.9", "date_of_service": "2025-06-01"},
        headers=_auth(token),
    )
    assert valid.json()["status"] == "valid"

    invalid = client.get(
        "/api/v1/code-references/lookup",
        params={"code_type": "icd10cm", "code": "F32.9", "date_of_service": "2024-06-01"},
        headers=_auth(token),
    )
    assert invalid.json()["status"] == "date_invalid"


def test_ai_disabled_gate(client, register, monkeypatch):
    owner = register("owner@gate.example.com", "Gate Org")
    token = owner["access_token"]
    encounter = _create_encounter(client, token)

    monkeypatch.setattr("app.services.coding.get_settings", lambda: Settings(ai_enabled=False))
    response = client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=_auth(token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ai_disabled"


def test_phi_approval_gate(client, register, monkeypatch):
    owner = register("owner@phi.example.com", "Phi Org")
    token = owner["access_token"]
    encounter = _create_encounter(client, token)

    monkeypatch.setattr(
        "app.services.coding.get_settings",
        lambda: Settings(ai_enabled=True, ai_phi_approved=False),
    )
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(transmits_phi=True))

    response = client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=_auth(token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "phi_not_approved"


def test_provider_failure_produces_failed_job(client, register, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(fail_with="boom"))
    owner = register("owner@fail.example.com", "Fail Org")
    token = owner["access_token"]
    encounter = _create_encounter(client, token)

    job = client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=_auth(token)).json()
    assert job["status"] == "failed"
    assert job["error_code"] == "provider_error"


def test_audit_events_and_redaction(client, register, monkeypatch):
    _patch_provider(monkeypatch)
    owner = register("owner@audit.example.com", "Audit Org")
    token = owner["access_token"]
    encounter = _create_encounter(client, token)
    job = client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=_auth(token)).json()
    suggestion_id = job["suggestions"][0]["id"]
    client.post(
        f"/api/v1/encounters/{encounter['id']}/suggestions/{suggestion_id}/review",
        json={"decision": "approved"},
        headers=_auth(token),
    )

    db = SessionLocal()
    try:
        actions = [e.action for e in db.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars()]
        assert "encounter.created" in actions
        assert "coding.completed" in actions
        assert "suggestion.reviewed" in actions

        for event in db.execute(select(AuditEvent)).scalars():
            metadata = event.metadata_json or ""
            assert "major depressive disorder" not in metadata
            assert "psychotherapy" not in metadata
    finally:
        db.close()
