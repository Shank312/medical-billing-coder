"""Real PostgreSQL integration tests (run with ``pytest integration_tests``)."""
import csv
import io
import json
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select, text

from app.ai.mock import MockProvider
from app.db.session import SessionLocal, engine
from app.models.coding_suggestion import CodingSuggestion
from app.services.coding import enqueue_coding_job, process_coding_job

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


class _NoopPublisher:
    def __call__(self, job_id: str) -> None:
        pass


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_encounter(client, token):
    response = client.post(
        "/api/v1/encounters",
        json={"date_of_service": "2025-03-15", "note": NOTE},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_migration_and_connectivity(migrated_database):
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1
        # migration created the core tables
        assert conn.execute(text("SELECT count(*) FROM organizations")).scalar() == 0


def test_transaction_rollback(migrated_database):
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        with session.begin():
            session.execute(text("CREATE TABLE IF NOT EXISTS _mbc_probe (id integer)"))
            session.execute(text("INSERT INTO _mbc_probe (id) VALUES (1)"))
        # explicit rollback via nested transaction
        trans = session.begin_nested()
        session.execute(text("INSERT INTO _mbc_probe (id) VALUES (2)"))
        trans.rollback()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM _mbc_probe")).scalar() == 1


def test_tenant_isolation(client, register):
    a = register("a@postgres.example.com", "Org A")
    b = register("b@postgres.example.com", "Org B")
    encounter = _create_encounter(client, a["access_token"])
    assert client.get(f"/api/v1/encounters/{encounter['id']}", headers=_auth(b["access_token"])).status_code == 404


def test_idempotency_key_uniqueness(client, register, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(response_json=MOCK_OUTPUT))
    a = register("c@postgres.example.com", "Org C")
    encounter = _create_encounter(client, a["access_token"])
    headers = {**_auth(a["access_token"]), "Idempotency-Key": "key-1"}
    first = client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=headers)
    second = client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=headers)
    assert first.status_code == 202
    assert first.json()["id"] == second.json()["id"]


def test_concurrent_coding_job_claim(client, register, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(response_json=MOCK_OUTPUT))
    a = register("d@postgres.example.com", "Org D")
    encounter = _create_encounter(client, a["access_token"])

    db = SessionLocal()
    try:
        job = enqueue_coding_job(
            db,
            organization_id=a["organization"]["id"],
            actor_user_id=a["user"]["id"],
            encounter_id=encounter["id"],
            publisher=_NoopPublisher(),
        )
        job_id = job.id
    finally:
        db.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(process_coding_job, [job_id] * 4, [1, 2, 3, 4]))

    db = SessionLocal()
    try:
        count = db.execute(
            select(func.count()).select_from(CodingSuggestion).where(CodingSuggestion.job_id == job_id)
        ).scalar_one()
        assert count == 1  # the atomic claim admits exactly one processor
    finally:
        db.close()


def test_export_filtering(client, register, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(response_json=MOCK_OUTPUT))
    a = register("e@postgres.example.com", "Org E")
    coded = _create_encounter(client, a["access_token"])
    client.post(f"/api/v1/encounters/{coded['id']}/code", headers=_auth(a["access_token"]))
    _create_encounter(client, a["access_token"])  # not coded

    response = client.get("/api/v1/encounters/export.csv?status=coded", headers=_auth(a["access_token"]))
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows and all(row["encounter_id"] == coded["id"] for row in rows)
