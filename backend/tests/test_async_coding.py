"""Async coding job tests (offline; eager Celery + direct task/service calls)."""
import json
from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from app.ai.mock import MockProvider
from app.core.config import Settings
from app.core.errors import AiDisabledError, PhiNotApprovedError, ServiceUnavailableError
from app.core.time import utcnow
from app.db.session import SessionLocal
from app.models.coding_job import CodingJob
from app.models.coding_suggestion import CodingSuggestion
from app.services.coding import (
    RetryableCodingError,
    enqueue_coding_job,
    mark_job_failed,
    process_coding_job,
    recover_stale_jobs,
)

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
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, job_id: str) -> None:
        self.calls.append(job_id)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, email):
    response = client.post(
        "/api/v1/auth/register",
        json={"organization_name": f"Org {email}", "full_name": "Person", "email": email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _setup(client, email):
    data = _register(client, email)
    token = data["access_token"]
    encounter = client.post(
        "/api/v1/encounters",
        json={"date_of_service": "2025-03-15", "note": NOTE},
        headers=_auth(token),
    )
    assert encounter.status_code == 201, encounter.text
    return data["organization"]["id"], data["user"]["id"], encounter.json()["id"], token


def _suggestion_count(job_id: str) -> int:
    db = SessionLocal()
    try:
        return db.execute(
            select(func.count()).select_from(CodingSuggestion).where(CodingSuggestion.job_id == job_id)
        ).scalar_one()
    finally:
        db.close()


def test_enqueue_creates_queued_job_and_publishes(client):
    org_id, user_id, encounter_id, _ = _setup(client, "owner@enqueue.example.com")
    publisher = _NoopPublisher()
    db = SessionLocal()
    try:
        job = enqueue_coding_job(
            db, organization_id=org_id, actor_user_id=user_id, encounter_id=encounter_id, publisher=publisher
        )
        assert job.status == "queued"
        assert publisher.calls == [job.id]
    finally:
        db.close()


def test_enqueue_idempotency(client):
    org_id, user_id, encounter_id, _ = _setup(client, "owner@idem.example.com")
    publisher = _NoopPublisher()
    db = SessionLocal()
    try:
        first = enqueue_coding_job(
            db, organization_id=org_id, actor_user_id=user_id, encounter_id=encounter_id,
            client_request_id="req-1", publisher=publisher,
        )
        second = enqueue_coding_job(
            db, organization_id=org_id, actor_user_id=user_id, encounter_id=encounter_id,
            client_request_id="req-1", publisher=publisher,
        )
        assert first.id == second.id
        assert len(publisher.calls) == 1
    finally:
        db.close()


def test_process_completes_job(client, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(response_json=MOCK_OUTPUT))
    org_id, user_id, encounter_id, _ = _setup(client, "owner@complete.example.com")
    db = SessionLocal()
    try:
        job = enqueue_coding_job(db, organization_id=org_id, actor_user_id=user_id, encounter_id=encounter_id, publisher=_NoopPublisher())
        job_id = job.id
    finally:
        db.close()

    processed = process_coding_job(job_id, 1)
    assert processed.status == "completed"
    assert _suggestion_count(job_id) == 1


def test_duplicate_delivery_is_idempotent(client, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(response_json=MOCK_OUTPUT))
    org_id, user_id, encounter_id, _ = _setup(client, "owner@dup.example.com")
    db = SessionLocal()
    try:
        job = enqueue_coding_job(db, organization_id=org_id, actor_user_id=user_id, encounter_id=encounter_id, publisher=_NoopPublisher())
        job_id = job.id
    finally:
        db.close()

    process_coding_job(job_id, 1)
    count_after_first = _suggestion_count(job_id)

    second = process_coding_job(job_id, 2)  # duplicate/redelivered delivery
    assert second is None  # already completed; skipped
    assert _suggestion_count(job_id) == count_after_first


def test_retryable_failure_requeues(client, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(fail_with="down", fail_code="provider_unavailable"))
    org_id, user_id, encounter_id, _ = _setup(client, "owner@retryable.example.com")
    db = SessionLocal()
    try:
        job = enqueue_coding_job(db, organization_id=org_id, actor_user_id=user_id, encounter_id=encounter_id, publisher=_NoopPublisher())
        job_id = job.id
    finally:
        db.close()

    with pytest.raises(RetryableCodingError):
        process_coding_job(job_id, 1)

    db = SessionLocal()
    try:
        assert db.get(CodingJob, job_id).status == "queued"
    finally:
        db.close()


def test_non_retryable_failure_marks_failed(client, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(fail_with="boom", fail_code="provider_error"))
    org_id, user_id, encounter_id, _ = _setup(client, "owner@nonretry.example.com")
    db = SessionLocal()
    try:
        job = enqueue_coding_job(db, organization_id=org_id, actor_user_id=user_id, encounter_id=encounter_id, publisher=_NoopPublisher())
        job_id = job.id
    finally:
        db.close()

    result = process_coding_job(job_id, 1)
    assert result.status == "failed"
    assert result.error_code == "provider_error"


def test_retry_exhaustion_marks_failed(client, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(fail_with="down", fail_code="provider_unavailable"))
    org_id, user_id, encounter_id, _ = _setup(client, "owner@exhaust.example.com")
    db = SessionLocal()
    try:
        job = enqueue_coding_job(db, organization_id=org_id, actor_user_id=user_id, encounter_id=encounter_id, publisher=_NoopPublisher())
        job_id = job.id
    finally:
        db.close()

    with pytest.raises(RetryableCodingError):
        process_coding_job(job_id, 1)

    mark_job_failed(job_id, "retry_exhausted")
    db = SessionLocal()
    try:
        refreshed = db.get(CodingJob, job_id)
        assert refreshed.status == "failed"
        assert refreshed.error_code == "retry_exhausted"
    finally:
        db.close()


def test_enqueue_publish_failure_marks_failed(client):
    org_id, user_id, encounter_id, _ = _setup(client, "owner@queuefail.example.com")

    def failing_publisher(job_id: str) -> None:
        raise RuntimeError("broker down")

    db = SessionLocal()
    try:
        with pytest.raises(ServiceUnavailableError):
            enqueue_coding_job(db, organization_id=org_id, actor_user_id=user_id, encounter_id=encounter_id, publisher=failing_publisher)
    finally:
        db.close()

    db = SessionLocal()
    try:
        job = db.execute(select(CodingJob).where(CodingJob.organization_id == org_id)).scalars().first()
        assert job.status == "failed"
        assert job.error_code == "queue_unavailable"
    finally:
        db.close()


def test_stale_job_recovery(client):
    org_id, user_id, encounter_id, _ = _setup(client, "owner@stale.example.com")
    db = SessionLocal()
    try:
        job = enqueue_coding_job(db, organization_id=org_id, actor_user_id=user_id, encounter_id=encounter_id, publisher=_NoopPublisher())
        db.execute(
            update(CodingJob)
            .where(CodingJob.id == job.id)
            .values(status="running", started_at=utcnow() - timedelta(hours=1))
        )
        db.commit()

        result = recover_stale_jobs(before=utcnow() - timedelta(minutes=10), publisher=_NoopPublisher())
        assert result["requeued"] == 1
        db.expire_all()
        assert db.get(CodingJob, job.id).status == "queued"
    finally:
        db.close()


def test_ai_disabled_gate(client, monkeypatch):
    org_id, user_id, encounter_id, _ = _setup(client, "owner@gate.example.com")
    monkeypatch.setattr("app.services.coding.get_settings", lambda: Settings(ai_enabled=False))
    db = SessionLocal()
    try:
        with pytest.raises(AiDisabledError):
            enqueue_coding_job(db, organization_id=org_id, actor_user_id=user_id, encounter_id=encounter_id, publisher=_NoopPublisher())
    finally:
        db.close()


def test_phi_approval_gate(client, monkeypatch):
    org_id, user_id, encounter_id, _ = _setup(client, "owner@phigate.example.com")
    monkeypatch.setattr("app.services.coding.get_settings", lambda: Settings(ai_enabled=True, ai_phi_approved=False))
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(transmits_phi=True))
    db = SessionLocal()
    try:
        with pytest.raises(PhiNotApprovedError):
            enqueue_coding_job(db, organization_id=org_id, actor_user_id=user_id, encounter_id=encounter_id, publisher=_NoopPublisher())
    finally:
        db.close()


def test_submit_and_poll_api(client, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(response_json=MOCK_OUTPUT))
    data = _register(client, "owner@api.example.com")
    token = data["access_token"]
    encounter = client.post("/api/v1/encounters", json={"date_of_service": "2025-03-15", "note": NOTE}, headers=_auth(token)).json()

    submitted = client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=_auth(token))
    assert submitted.status_code == 202
    job_id = submitted.json()["id"]

    polled = client.get(f"/api/v1/coding-jobs/{job_id}", headers=_auth(token))
    assert polled.status_code == 200
    assert polled.json()["status"] == "completed"


def test_job_tenant_isolation(client, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(response_json=MOCK_OUTPUT))
    a = _register(client, "a@jobiso.example.com")
    b = _register(client, "b@jobiso.example.com")
    enc_a = client.post("/api/v1/encounters", json={"date_of_service": "2025-03-15", "note": NOTE}, headers=_auth(a["access_token"])).json()
    job_a = client.post(f"/api/v1/encounters/{enc_a['id']}/code", headers=_auth(a["access_token"])).json()

    assert client.get(f"/api/v1/coding-jobs/{job_a['id']}", headers=_auth(b["access_token"])).status_code == 404

    listing = client.get("/api/v1/coding-jobs", headers=_auth(b["access_token"])).json()
    assert all(item["id"] != job_a["id"] for item in listing["items"])
