"""Structured coding workflow (Phase 2).

The note is treated strictly as untrusted data. The model returns candidate
suggestions only; deterministic evidence validation, code-set validation, and
human review are separate and never conflated with model output. Expected
provider/parse failures are persisted as a *failed* job (returned, not raised).
"""
import json
import time
import uuid
from datetime import date

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..ai import get_provider
from ..ai.base import AIProvider, ChatMessage, ProviderRequest
from ..ai.prompts import SYSTEM_PROMPT, build_user_prompt
from ..ai.quality import validate_evidence
from ..ai.schemas import PROMPT_VERSION, SCHEMA_VERSION, CodingOutput
from ..core.config import get_settings
from ..core.errors import AiDisabledError, BadRequestError, NotFoundError, PhiNotApprovedError, ProviderError
from ..core.time import utcnow
from ..models.coding_job import CodingJob
from ..models.coding_suggestion import CodingSuggestion
from ..repositories.coding import CodingJobRepository, SuggestionRepository
from ..repositories.encounters import EncounterRepository
from .audit import AuditService
from .reference_data import latest_set_version, validate_code


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


def _mark_failed(
    *,
    db: Session,
    job: CodingJob,
    job_repo: CodingJobRepository,
    provider: AIProvider,
    code_set_version: str | None,
    request_id: str,
    started: float,
    error_code: str,
    organization_id: str,
    actor_user_id: str,
    encounter_id: str,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    job.status = "failed"
    job.error_code = error_code
    job.completed_at = utcnow()
    job_repo.add_attempt(
        job_id=job.id,
        provider_name=provider.name,
        model_name=provider.model or provider.name,
        prompt_version=PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
        code_set_version=code_set_version,
        request_id=request_id,
        status="failed",
        latency_ms=int((time.monotonic() - started) * 1000),
        error_code=error_code,
    )
    AuditService.append(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="coding.failed",
        resource_type="coding_job",
        resource_id=job.id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"encounter_id": encounter_id, "error_code": error_code},
    )


def submit_coding(
    db: Session,
    *,
    organization_id: str,
    actor_user_id: str,
    encounter_id: str,
    client_request_id: str | None = None,
    provider: AIProvider | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> CodingJob:
    """Run the coding workflow synchronously and return the (completed/failed) job.

    Idempotency: when ``client_request_id`` is provided and a job already exists for
    it, that job is returned without re-running or re-auditing. Expected provider or
    output-parse failures mark the job ``failed`` and return it; the PHI/gate and
    input errors are raised before any job exists.
    """
    settings = get_settings()
    provider = provider or get_provider()
    _check_gate(settings, provider)

    encounter_repo = EncounterRepository(db, organization_id)
    encounter = encounter_repo.get(encounter_id)
    document = encounter_repo.get_document(encounter_id)
    if document is None:
        raise BadRequestError("Encounter has no source note", code="note_required")

    job_repo = CodingJobRepository(db, organization_id)
    if client_request_id:
        existing = job_repo.get_by_client_request(client_request_id)
        if existing is not None:
            return existing

    job = job_repo.create(encounter_id=encounter_id, client_request_id=client_request_id, created_by=actor_user_id)
    job.schema_version = SCHEMA_VERSION
    job.prompt_version = PROMPT_VERSION
    job.status = "running"
    db.flush()

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
    code_set_version: str | None = None

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
        latency_ms = int((time.monotonic() - started) * 1000)

        output = parse_output(response.content)
        output = validate_evidence(document.content, output)

        code_set_version = (
            latest_set_version(db, "icd10cm")
            or latest_set_version(db, "cpt")
            or latest_set_version(db, "hcpcs")
        )
        _persist_suggestions(
            db,
            organization_id=organization_id,
            encounter_id=encounter_id,
            job_id=job.id,
            output=output,
            dos=encounter.date_of_service,
        )

        job.status = "completed"
        job.code_set_version = code_set_version
        job.missing_documentation_json = json.dumps(output.missing_documentation)
        job.contradictions_json = json.dumps(output.contradictions)
        job.completed_at = utcnow()
        job_repo.add_attempt(
            job_id=job.id,
            provider_name=provider.name,
            model_name=response.model,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            code_set_version=code_set_version,
            request_id=request_id,
            status="success",
            latency_ms=latency_ms,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
        )
        AuditService.append(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="coding.completed",
            resource_type="coding_job",
            resource_id=job.id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"encounter_id": encounter_id, "provider": provider.name, "model": response.model},
        )
    except ProviderError as exc:
        _mark_failed(
            db=db,
            job=job,
            job_repo=job_repo,
            provider=provider,
            code_set_version=code_set_version,
            request_id=request_id,
            started=started,
            error_code=exc.code,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            encounter_id=encounter_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return job
    except Exception:
        _mark_failed(
            db=db,
            job=job,
            job_repo=job_repo,
            provider=provider,
            code_set_version=code_set_version,
            request_id=request_id,
            started=started,
            error_code="coding_failed",
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            encounter_id=encounter_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise
    return job


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
