"""Batch ingestion tests (offline; synthetic PDFs/CSVs, eager Celery)."""
import io
import json

from pypdf import PdfWriter

from app.ai.mock import MockProvider
from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.encounter import Encounter
from app.models.ingestion import IngestionDocument

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

VALID_CSV = "date_of_service,note,encounter_type\n2025-03-15,\"Patient presents with major depressive disorder.\",outpatient\n"


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


def _make_text_pdf(text: str) -> bytes:
    """Build a minimal valid PDF with a text content stream."""
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    return bytes(out)


def _make_encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("user", "owner")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _create_batch(client, token, date=None):
    payload = {"date_of_service": date} if date else {}
    response = client.post("/api/v1/batches", json=payload, headers=_auth(token))
    assert response.status_code == 201, response.text
    return response.json()


def _upload(client, token, batch_id, files):
    return client.post(f"/api/v1/batches/{batch_id}/documents", files=files, headers=_auth(token))


def test_batch_and_pdf_upload_creates_encounter_and_job(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@batch.example.com")
    token = data["access_token"]
    batch = _create_batch(client, token, date="2025-03-15")

    response = _upload(
        client,
        token,
        batch["id"],
        [("files", ("note.pdf", _make_text_pdf(NOTE), "application/pdf"))],
    )
    assert response.status_code == 201, response.text
    document = response.json()[0]
    assert document["extraction_status"] == "completed"
    assert document["encounter_id"]
    assert document["coding_job_id"]

    db = SessionLocal()
    try:
        from app.repositories.encounters import EncounterRepository

        encounter = db.get(Encounter, document["encounter_id"])
        assert encounter is not None
        note = EncounterRepository(db, data["organization"]["id"]).get_document(document["encounter_id"])
        assert note and "major depressive disorder" in note.content
    finally:
        db.close()


def test_upload_rejects_unsupported_type(client):
    data = _register(client, "owner@unsupported.example.com")
    token = data["access_token"]
    batch = _create_batch(client, token, date="2025-03-15")
    response = _upload(client, token, batch["id"], [("files", ("malware.exe", b"MZ...", "application/octet-stream"))])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_type"


def test_upload_rejects_empty_file(client):
    data = _register(client, "owner@empty.example.com")
    token = data["access_token"]
    batch = _create_batch(client, token, date="2025-03-15")
    response = _upload(client, token, batch["id"], [("files", ("empty.pdf", b"", "application/pdf"))])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_file"


def test_upload_rejects_mismatched_content(client):
    data = _register(client, "owner@mismatch.example.com")
    token = data["access_token"]
    batch = _create_batch(client, token, date="2025-03-15")
    response = _upload(client, token, batch["id"], [("files", ("fake.pdf", b"not a pdf at all", "application/pdf"))])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_type"


def test_upload_rejects_oversized_file(client, monkeypatch):
    data = _register(client, "owner@oversize.example.com")
    token = data["access_token"]
    batch = _create_batch(client, token, date="2025-03-15")
    monkeypatch.setattr("app.services.batches.get_settings", lambda: Settings(max_upload_file_size=10))
    response = _upload(client, token, batch["id"], [("files", ("big.pdf", b"%PDF-" + b"x" * 100, "application/pdf"))])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "file_too_large"


def test_pdf_no_text_requires_manual(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@notext.example.com")
    token = data["access_token"]
    batch = _create_batch(client, token, date="2025-03-15")
    response = _upload(client, token, batch["id"], [("files", ("blank.pdf", _make_text_pdf(""), "application/pdf"))])
    assert response.status_code == 201
    assert response.json()[0]["extraction_status"] == "requires_manual"
    assert response.json()[0]["error_code"] == "no_text"


def test_pdf_encrypted_fails(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@encrypted.example.com")
    token = data["access_token"]
    batch = _create_batch(client, token, date="2025-03-15")
    response = _upload(client, token, batch["id"], [("files", ("enc.pdf", _make_encrypted_pdf(), "application/pdf"))])
    assert response.status_code == 201
    assert response.json()[0]["extraction_status"] == "failed"
    assert response.json()[0]["error_code"] == "encrypted_pdf"


def test_csv_import_creates_encounters(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@csv.example.com")
    token = data["access_token"]
    batch = _create_batch(client, token)
    response = _upload(client, token, batch["id"], [("files", ("rows.csv", VALID_CSV.encode(), "text/csv"))])
    assert response.status_code == 201, response.text
    document = response.json()[0]
    assert document["extraction_status"] == "completed"

    db = SessionLocal()
    try:
        from sqlalchemy import func, select

        count = db.execute(select(func.count()).select_from(Encounter)).scalar_one()
        assert count >= 1
    finally:
        db.close()


def test_csv_invalid_date_records_row_error(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@csvbad.example.com")
    token = data["access_token"]
    batch = _create_batch(client, token)
    csv_text = "date_of_service,note\nnot-a-date,Some note here\n2025-03-15,Valid note here\n"
    response = _upload(client, token, batch["id"], [("files", ("rows.csv", csv_text.encode(), "text/csv"))])
    assert response.status_code == 201
    document = response.json()[0]
    assert document["extraction_status"] == "completed"  # one valid row accepted
    db = SessionLocal()
    try:
        row = db.get(IngestionDocument, document["id"])
        results = json.loads(row.row_results_json)
        assert len(results["errors"]) == 1
        assert results["errors"][0]["errors"] == ["invalid_date"]
    finally:
        db.close()


def test_csv_missing_columns_fails(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@csvmissing.example.com")
    token = data["access_token"]
    batch = _create_batch(client, token)
    response = _upload(client, token, batch["id"], [("files", ("bad.csv", b"foo,bar\n1,2\n", "text/csv"))])
    assert response.status_code == 201
    assert response.json()[0]["extraction_status"] == "failed"
    assert response.json()[0]["error_code"] == "csv_schema_invalid"


def test_duplicate_upload_dedupes(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@dedup.example.com")
    token = data["access_token"]
    batch = _create_batch(client, token, date="2025-03-15")
    pdf = _make_text_pdf(NOTE)
    first = _upload(client, token, batch["id"], [("files", ("a.pdf", pdf, "application/pdf"))])
    second = _upload(client, token, batch["id"], [("files", ("b.pdf", pdf, "application/pdf"))])
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()[0]["id"] == second.json()[0]["id"]


def test_batch_tenant_isolation(client):
    a = _register(client, "a@batchiso.example.com")
    b = _register(client, "b@batchiso.example.com")
    batch_a = _create_batch(client, a["access_token"], date="2025-03-15")

    assert client.get(f"/api/v1/batches/{batch_a['id']}", headers=_auth(b["access_token"])).status_code == 404
    listing = client.get("/api/v1/batches", headers=_auth(b["access_token"])).json()
    assert all(item["id"] != batch_a["id"] for item in listing["items"])


def test_batch_status_aggregation(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@agg.example.com")
    token = data["access_token"]
    batch = _create_batch(client, token, date="2025-03-15")
    _upload(client, token, batch["id"], [("files", ("ok.pdf", _make_text_pdf(NOTE), "application/pdf"))])
    _upload(client, token, batch["id"], [("files", ("bad.pdf", b"junk", "application/pdf"))])
    # bad.pdf rejected at upload; ok.pdf completed
    detail = client.get(f"/api/v1/batches/{batch['id']}", headers=_auth(token)).json()
    assert detail["total_documents"] == 1
    assert detail["processed_documents"] == 1


def test_retry_failed_document(client, monkeypatch):
    _patch_provider(monkeypatch)
    data = _register(client, "owner@retrydoc.example.com")
    token = data["access_token"]
    batch = _create_batch(client, token, date="2025-03-15")
    # an encrypted PDF fails non-retryably at extraction
    response = _upload(client, token, batch["id"], [("files", ("enc.pdf", _make_encrypted_pdf(), "application/pdf"))])
    document = response.json()[0]
    assert document["extraction_status"] == "failed"
    retry = client.post(f"/api/v1/batches/{batch['id']}/documents/{document['id']}/retry", headers=_auth(token))
    assert retry.status_code == 200
    assert retry.json()["extraction_status"] == "failed"  # re-fails (still encrypted)
