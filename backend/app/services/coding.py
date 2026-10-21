"""Structured coding workflow with asynchronous job processing (Phase 4).

The database is the authoritative source of job state and results. Enqueueing
creates a durable ``queued`` job and publishes only its id to the broker; the
worker re-fetches and verifies the job/encounter from the database before
processing. Processing is idempotent under duplicate delivery via an atomic
``queued -> running`` claim. No clinical content is placed in task arguments.
"""
import json
import time
import uuid
from datetime import date, timedelta
from typing import Callable

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..ai import get_provider
from ..ai.base import AIProvider, ChatMessage, ProviderRequest
from ..ai.prompts import SYSTEM_PROMPT, build_user_prompt
from ..ai.quality import validate_evidence
from ..ai.schemas import PROMPT_VERSION, SCHEMA_VERSION, CodingOutput
from ..core.config import get_settings
from ..core.errors import (
    AiDisabledError,
    BadRequestError,
    NotFoundError,
    PhiNotApprovedError,
    ProviderError,
    ServiceUnavailableError,
)
from ..core.time import utcnow
from ..db.session import SessionLocal
from ..models.coding_job import CodingJob
from ..models.coding_suggestion import CodingSuggestion
from ..repositories.coding import CodingJobRepository, SuggestionRepository
from ..repositories.encounters import EncounterRepository
from .audit import AuditService
from .reference_data import latest_set_version, validate_code

# Provider error codes that are transient and may be retried.
RETRYABLE_CODES = {"provider_unavailable", "provider_timeout"}


class RetryableCodingError(Exception):
    """Raised for transient failures that should be retried with backoff."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _check_gate(settings, provider: AIProvider) -> None:
    if not settings.ai_enabled:
        raise AiDisabledError("AI coding is disabled", code="ai_disabled")
    if provider.transmits_phi and not settings.ai_phi_approved:
        raise PhiNotApprovedError(
            "PHI transmission to an external AI provider is not approved", code="phi_not_approved"
        )


def parse_output(content: str) -> CodingOutput:
    """Parse and validate the model's JSON into a ``CodingOutput``."""
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError("Model returned invalid JSON", code="invalid_model_output") from exc
    try:
        return CodingOutput.model_validate(data)
    except ValidationError as exc:
        raise ProviderError("Model output failed schema validation", code="invalid_model_output") from exc


def _persist_suggestions(
    db: Session,
    *,
    organization_id: str,
    encounter_id: str,
    job_id: str,
    output: CodingOutput,
    dos: date,
) -> None:
    repo = SuggestionRepository(db, organization_id)
    procedure_ids: dict[str, str] = {}

    def add_evidence(suggestion_id: str, spans) -> None:
        for span in spans:
            repo.add_evidence(
                suggestion_id=suggestion_id,
                quote=span.quote,
                start_offset=span.start,
                end_offset=span.end,
            )

    for suggestion in output.procedures:
        code_type = suggestion.code_type if suggestion.code_type in ("cpt", "hcpcs") else "cpt"
        status = validate_code(db, code_type=code_type, code=suggestion.code, date_of_service=dos)
        row = repo.create(
            encounter_id=encounter_id,
            job_id=job_id,
            code_type=code_type,
            code=suggestion.code,
            description=suggestion.description,
            confidence=suggestion.confidence,
            rationale=suggestion.rationale,
            validation_status=status,
            flags=suggestion.flags,
        )
        procedure_ids[suggestion.code] = row.id
        add_evidence(row.id, suggestion.evidence)

    for suggestion in output.diagnoses:
        status = validate_code(db, code_type="icd10cm", code=suggestion.code, date_of_service=dos)
        row = repo.create(
            encounter_id=encounter_id,
            job_id=job_id,
            code_type="icd10cm",
            code=suggestion.code,
            description=suggestion.description,
            confidence=suggestion.confidence,
            rationale=suggestion.rationale,
            validation_status=status,
            flags=suggestion.flags,
        )
        add_evidence(row.id, suggestion.evidence)

    for suggestion in output.modifiers:
        parent_id = procedure_ids.get(suggestion.applies_to) if suggestion.applies_to else None
        row = repo.create(
            encounter_id=encounter_id,
            job_id=job_id,
            code_type="modifier",
            code=suggestion.code,
            description=suggestion.description,
            confidence=suggestion.confidence,
            rationale=suggestion.rationale,
            applies_to=suggestion.applies_to,
            parent_suggestion_id=parent_id,
            validation_status=None,
            flags=suggestion.flags,
        )
        add_evidence(row.id, suggestion.evidence)


def _default_publisher(job_id: str) -> None:
    from ..tasks.coding import process_coding_job_task

    process_coding_job_task.delay(job_id)


def enqueue_coding_job(
    db: Session,
    *,
    organization_id: str,
    actor_user_id: str,
    encounter_id: str,
    client_request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    publisher: Callable[[str], None] | None = None,
) -> CodingJob:
    """Durably record a ``queued`` job and publish it; return the job.

    The job is committed before publication so a crash between commit and publish
    leaves a recoverable ``queued`` job. If publication fails (broker down), the
    job is marked ``failed`` and a 503 is raised — never a false success.
    """
    settings = get_settings()
    _check_gate(settings, get_provider())

    encounter_repo = EncounterRepository(db, organization_id)
    encounter_repo.get(encounter_id)  # tenant-scoped lookup
    if encounter_repo.get_document(encounter_id) is None:
        raise BadRequestError("Encounter has no source note", code="note_required")

    job_repo = CodingJobRepository(db, organization_id)
    if client_request_id:
        existing = job_repo.get_by_client_request(client_request_id)
        if existing is not None:
            return existing

    job = job_repo.create(encounter_id=encounter_id, client_request_id=client_request_id, created_by=actor_user_id)
    job.schema_version = SCHEMA_VERSION
    job.prompt_version = PROMPT_VERSION
    job.status = "queued"
    AuditService.append(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="coding.queued",
        resource_type="coding_job",
        resource_id=job.id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"encounter_id": encounter_id},
    )
    db.commit()

    try:
        (publisher or _default_publisher)(job.id)
    except Exception:
        mark_job_failed(job.id, "queue_unavailable")
        raise ServiceUnavailableError("Coding queue is unavailable", code="queue_unavailable") from None
    return job


def _claim_job(db: Session, job_id: str) -> CodingJob | None:
    """Atomically transition ``queued -> running``; return None if not claimable."""
    result = db.execute(
        update(CodingJob)
        .where(CodingJob.id == job_id, CodingJob.status == "queued")
        .values(status="running", started_at=utcnow())
    )
    if result.rowcount == 0:
        return None
    db.commit()
    return db.get(CodingJob, job_id)


def process_coding_job(job_id: str, attempt_number: int = 1) -> CodingJob | None:
    """Process one attempt of a coding job (the worker's entrypoint).

    Idempotent: a job that is not ``queued`` is skipped, so duplicate delivery or
    a delayed worker cannot create duplicate suggestions or review history.
    """
    db = SessionLocal()
    try:
        job = _claim_job(db, job_id)
        if job is None:
            return None
        return _run_workflow(db, job, attempt_number)
    finally:
        db.close()


def _run_workflow(db: Session, job: CodingJob, attempt_number: int) -> CodingJob:
    settings = get_settings()
    provider = get_provider()
    job_repo = CodingJobRepository(db, job.organization_id)
    encounter_repo = EncounterRepository(db, job.organization_id)
    encounter = encounter_repo.get(job.encounter_id)
    document = encounter_repo.get_document(job.encounter_id)

    context_parts = []
    if encounter.encounter_type:
        context_parts.append(f"encounter_type: {encounter.encounter_type}")
    if encounter.place_of_service:
        context_parts.append(f"place_of_service: {encounter.place_of_service}")
    if encounter.payer_context:
        context_parts.append(f"payer: {encounter.payer_context}")
    context = "; ".join(context_parts) or None

    request_id = str(uuid.uuid4())
    started = time.monotonic()
    started_at = utcnow()
    code_set_version: str | None = None

    def record_attempt(status: str, error_code: str | None = None, **extra) -> None:
        job_repo.add_attempt(
            job_id=job.id,
            attempt_number=attempt_number,
            started_at=started_at,
            provider_name=provider.name,
            model_name=provider.model or provider.name,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            code_set_version=code_set_version,
            request_id=request_id,
            status=status,
            latency_ms=int((time.monotonic() - started) * 1000),
            error_code=error_code,
            **extra,
        )

    try:
        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=build_user_prompt(
                    note=document.content,
                    encounter_date=encounter.date_of_service.isoformat(),
                    context=context,
                ),
            ),
        ]
        response = provider.complete(
            ProviderRequest(
                messages=messages,
                model=provider.model or provider.name,
                max_tokens=settings.ai_max_tokens,
                temperature=settings.ai_temperature,
                request_id=request_id,
            )
        )
        output = parse_output(response.content)
        output = validate_evidence(document.content, output)

        code_set_version = (
            latest_set_version(db, "icd10cm")
            or latest_set_version(db, "cpt")
            or latest_set_version(db, "hcpcs")
        )
        _persist_suggestions(
            db,
            organization_id=job.organization_id,
            encounter_id=job.encounter_id,
            job_id=job.id,
            output=output,
            dos=encounter.date_of_service,
        )

        job.status = "completed"
        job.code_set_version = code_set_version
        job.missing_documentation_json = json.dumps(output.missing_documentation)
        job.contradictions_json = json.dumps(output.contradictions)
        job.completed_at = utcnow()
        record_attempt(
            "success",
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
        )
        AuditService.append(
            db,
            organization_id=job.organization_id,
            actor_user_id=job.created_by,
            action="coding.completed",
            resource_type="coding_job",
            resource_id=job.id,
            metadata={"encounter_id": job.encounter_id, "provider": provider.name, "model": response.model},
        )
        db.commit()
        return job
    except ProviderError as exc:
        record_attempt("failed", error_code=exc.code)
        if exc.code in RETRYABLE_CODES:
            job.status = "queued"
            job.started_at = None
            db.commit()
            raise RetryableCodingError(exc.code, "Transient provider failure") from exc
        job.status = "failed"
        job.error_code = exc.code
        job.completed_at = utcnow()
        AuditService.append(
            db,
            organization_id=job.organization_id,
            actor_user_id=job.created_by,
            action="coding.failed",
            resource_type="coding_job",
            resource_id=job.id,
            metadata={"encounter_id": job.encounter_id, "error_code": exc.code},
        )
        db.commit()
        return job
    except Exception:  # noqa: BLE001 - unexpected failures fail the job, never retry-storm
        record_attempt("failed", error_code="coding_failed")
        job.status = "failed"
        job.error_code = "coding_failed"
        job.completed_at = utcnow()
        AuditService.append(
            db,
            organization_id=job.organization_id,
            actor_user_id=job.created_by,
            action="coding.failed",
            resource_type="coding_job",
            resource_id=job.id,
            metadata={"encounter_id": job.encounter_id, "error_code": "coding_failed"},
        )
        db.commit()
        return job


def mark_job_failed(job_id: str, error_code: str) -> None:
    """Mark a job failed using a fresh session (safe from worker or request)."""
    db = SessionLocal()
    try:
        db.execute(
            update(CodingJob)
            .where(CodingJob.id == job_id)
            .values(status="failed", error_code=error_code, completed_at=utcnow())
        )
        db.commit()
    finally:
        db.close()


def recover_stale_jobs(
    *, before=None, publisher: Callable[[str], None] | None = None
) -> dict:
    """Re-queue stale ``running`` jobs and re-publish stale ``queued`` jobs.

    Re-publishing a ``queued`` job is safe under at-least-once delivery because the
    atomic claim ensures only one worker processes it. Returns counts.
    """
    db = SessionLocal()
    try:
        cutoff = before or (utcnow() - timedelta(seconds=get_settings().coding_stale_after_seconds))
        requeued = db.execute(
            update(CodingJob)
            .where(CodingJob.status == "running", CodingJob.started_at < cutoff)
            .values(status="queued", started_at=None)
        ).rowcount
        stale_queued = db.execute(
            select(CodingJob.id).where(CodingJob.status == "queued", CodingJob.created_at < cutoff)
        ).scalars().all()
        db.commit()

        republished = 0
        for job_id in stale_queued:
            try:
                (publisher or _default_publisher)(job_id)
                republished += 1
            except Exception:
                break  # broker unavailable; stop republishing
        return {"requeued": requeued, "republished": republished}
    finally:
        db.close()


def review_suggestion(
    db: Session,
    *,
    organization_id: str,
    actor_user_id: str,
    encounter_id: str,
    suggestion_id: str,
    decision: str,
    corrected_code: str | None = None,
    note: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> CodingSuggestion:
    """Record a human review decision (approved/rejected/corrected) on a suggestion."""
    repo = SuggestionRepository(db, organization_id)
    suggestion = repo.get(suggestion_id)
    if suggestion.encounter_id != encounter_id:
        raise NotFoundError("Suggestion not found in this encounter")

    if decision == "corrected" and not corrected_code:
        raise BadRequestError("corrected_code is required when decision is 'corrected'", code="corrected_code_required")

    suggestion.review_status = decision
    suggestion.reviewed_by = actor_user_id
    suggestion.reviewed_at = utcnow()
    if corrected_code:
        suggestion.corrected_code = corrected_code

    repo.add_review(
        suggestion_id=suggestion_id,
        encounter_id=encounter_id,
        reviewer_id=actor_user_id,
        decision=decision,
        corrected_code=corrected_code,
        note=note,
    )
    AuditService.append(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="suggestion.reviewed",
        resource_type="coding_suggestion",
        resource_id=suggestion_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"decision": decision, "code": suggestion.code},
    )
    return suggestion
