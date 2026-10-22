"""Real Redis/Celery integration tests (require the compose ``worker-test`` running)."""
import time

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.coding_suggestion import CodingSuggestion
from app.services.coding import process_coding_job

TEST_PASSWORD = "correct-horse-battery-staple-123!"
NOTE = "Patient presents with major depressive disorder."


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


def _wait_for_terminal(client, token, job_id: str, timeout: float = 30.0) -> str:
    deadline = time.time() + timeout
    status = None
    while time.time() < deadline:
        polled = client.get(f"/api/v1/coding-jobs/{job_id}", headers=_auth(token))
        status = polled.json()["status"]
        if status in ("completed", "failed"):
            return status
        time.sleep(0.5)
    return status or "unknown"


def test_coding_job_executes_via_real_worker(client, register):
    a = register("a@redis.example.com", "Org A")
    encounter = _create_encounter(client, a["access_token"])

    submitted = client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=_auth(a["access_token"]))
    assert submitted.status_code == 202
    job_id = submitted.json()["id"]

    assert _wait_for_terminal(client, a["access_token"], job_id) == "completed"


def test_duplicate_delivery_idempotent(client, register):
    a = register("b@redis.example.com", "Org B")
    encounter = _create_encounter(client, a["access_token"])

    submitted = client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=_auth(a["access_token"]))
    job_id = submitted.json()["id"]
    assert _wait_for_terminal(client, a["access_token"], job_id) == "completed"

    # a redelivered task must be skipped by the atomic claim (no duplicate suggestions)
    assert process_coding_job(job_id, 2) is None
    db = SessionLocal()
    try:
        count = db.execute(
            select(func.count()).select_from(CodingSuggestion).where(CodingSuggestion.job_id == job_id)
        ).scalar_one()
    finally:
        db.close()
    assert count == 1
