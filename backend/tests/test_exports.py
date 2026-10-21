"""Export tests: authorization, tenant isolation, content, and file safety."""
import csv
import io
import json

from app.ai.mock import MockProvider
from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.audit import AuditEvent
from app.services.exports import sanitize_cell

TEST_PASSWORD = "correct-horse-battery-staple-123!"
NOTE = (
    "Patient presents with major depressive disorder. A 45 minute psychotherapy "
    "session was performed via telehealth."
)

MOCK_OUTPUT = json.dumps(
    {
        "diagnoses": [
            {"code": "F32.9", "code_type": "icd10cm", "evidence": [{"quote": "major depressive disorder", "start": 0, "end": 0}]}
        ],
        "procedures": [
            {"code": "90837", "code_type": "cpt", "evidence": [{"quote": "45 minute psychotherapy session", "start": 0, "end": 0}]}
        ],
        "modifiers": [],
        "missing_documentation": ["Exact start/stop times not documented"],
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


def _patch_provider(monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(response_json=MOCK_OUTPUT))


def _create_and_code(client, token, monkeypatch, patient_reference=None):
    _patch_provider(monkeypatch)
    payload = {"date_of_service": "2025-03-15", "note": NOTE}
    if patient_reference:
        payload["patient_reference"] = patient_reference
    encounter = client.post("/api/v1/encounters", json=payload, headers=_auth(token)).json()
    submitted = client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=_auth(token))
    assert submitted.status_code == 202
    detail = client.get(f"/api/v1/encounters/{encounter['id']}", headers=_auth(token)).json()
    return encounter, detail


def test_sanitize_cell_formula_injection():
    assert sanitize_cell("=SUM(A1)") == "'=SUM(A1)"
    assert sanitize_cell("+SUM(A1)") == "'+SUM(A1)"
    assert sanitize_cell("-1+1") == "'-1+1"
    assert sanitize_cell("@cmd") == "'@cmd"
    assert sanitize_cell("  =SUM(A1)") == "'  =SUM(A1)"
    assert sanitize_cell("\t=SUM(A1)") == "'\t=SUM(A1)"
    assert sanitize_cell("normal text") == "normal text"
    assert sanitize_cell("") == ""
    assert sanitize_cell(None) == ""


def test_csv_export_content_and_review_distinction(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@csvexport.example.com")
    token = data["access_token"]
    encounter, detail = _create_and_code(client, token, monkeypatch)

    # approve the diagnosis, reject the procedure
    diag = next(s for s in detail["suggestions"] if s["code_type"] == "icd10cm")
    proc = next(s for s in detail["suggestions"] if s["code_type"] == "cpt")
    client.post(f"/api/v1/encounters/{encounter['id']}/suggestions/{diag['id']}/review", json={"decision": "approved"}, headers=_auth(token))
    client.post(f"/api/v1/encounters/{encounter['id']}/suggestions/{proc['id']}/review", json={"decision": "rejected"}, headers=_auth(token))

    response = client.get("/api/v1/encounters/export.csv", headers=_auth(token))
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]

    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 2
    by_code = {r["code"]: r for r in rows}
    assert by_code["F32.9"]["review_decision"] == "approved"
    assert by_code["F32.9"]["source"] == "ai_suggested"
    assert by_code["90837"]["review_decision"] == "rejected"
    assert by_code["F32.9"]["missing_documentation"] == "Exact start/stop times not documented"
    assert by_code["F32.9"]["evidence_quotes"] == "major depressive disorder"


def test_csv_formula_injection_neutralized(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@csvformula.example.com")
    token = data["access_token"]
    _create_and_code(client, token, monkeypatch, patient_reference="=cmd()'| /C calc'!'A1'")

    response = client.get("/api/v1/encounters/export.csv", headers=_auth(token))
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows[0]["patient_reference"].startswith("'=")


def test_xlsx_export(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@xlsxexport.example.com")
    token = data["access_token"]
    _create_and_code(client, token, monkeypatch)

    response = client.get("/api/v1/encounters/export.xlsx", headers=_auth(token))
    assert response.status_code == 200
    assert response.content[:2] == b"PK"  # zip/xlsx magic
    assert "spreadsheetml" in response.headers["content-type"]


def test_pdf_summary(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@pdfsummary.example.com")
    token = data["access_token"]
    encounter, _detail = _create_and_code(client, token, monkeypatch)

    response = client.get(f"/api/v1/encounters/{encounter['id']}/summary.pdf", headers=_auth(token))
    assert response.status_code == 200
    assert response.content[:5] == b"%PDF-"
    assert "application/pdf" in response.headers["content-type"]


def test_export_tenant_isolation(client, monkeypatch):
    _patch_provider(monkeypatch)
    a = _register(client, "a@exportiso.example.com")
    b = _register(client, "b@exportiso.example.com")
    encounter, _ = _create_and_code(client, a["access_token"], monkeypatch)

    assert client.get(f"/api/v1/encounters/{encounter['id']}/summary.pdf", headers=_auth(b["access_token"])).status_code == 404
    # collection export for org B must not contain org A's encounter
    csv_b = client.get("/api/v1/encounters/export.csv", headers=_auth(b["access_token"]))
    assert csv_b.status_code == 200
    assert encounter["id"] not in csv_b.text


def test_export_limit(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@exportlimit.example.com")
    token = data["access_token"]
    _create_and_code(client, token, monkeypatch)
    _create_and_code(client, token, monkeypatch)

    monkeypatch.setattr("app.services.exports.get_settings", lambda: Settings(max_export_rows=1))
    response = client.get("/api/v1/encounters/export.csv", headers=_auth(token))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "export_too_large"


def test_batch_export(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@batchexport.example.com")
    token = data["access_token"]
    batch = client.post("/api/v1/batches", json={}, headers=_auth(token)).json()

    csv_content = 'date_of_service,note\n2025-03-15,"Patient presents with major depressive disorder."\n'
    client.post(
        f"/api/v1/batches/{batch['id']}/documents",
        files=[("files", ("rows.csv", csv_content.encode(), "text/csv"))],
        headers=_auth(token),
    )

    response = client.get(f"/api/v1/batches/{batch['id']}/export.csv", headers=_auth(token))
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 1
    assert rows[0]["batch_id"] == batch["id"]
    assert rows[0]["extraction_status"] == "completed"


def test_export_audit_has_no_clinical_text(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@exportaudit.example.com")
    token = data["access_token"]
    _create_and_code(client, token, monkeypatch)

    client.get("/api/v1/encounters/export.csv", headers=_auth(token))

    from sqlalchemy import select

    db = SessionLocal()
    try:
        events = db.execute(select(AuditEvent).where(AuditEvent.action == "export.generated")).scalars().all()
        assert events
        for event in events:
            assert "major depressive disorder" not in (event.metadata_json or "")
            assert NOTE not in (event.metadata_json or "")
    finally:
        db.close()
