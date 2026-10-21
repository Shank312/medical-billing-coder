"""Response serializers that assemble suggestion/evidence/job/encounter objects."""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.coding_job import CodingJob
from ..models.coding_suggestion import CodingSuggestion, EvidenceSpan
from ..models.encounter import Encounter
from ..schemas.coding import (
    CodingJobDetailOut,
    CodingJobOut,
    EncounterDetailOut,
    EncounterOut,
    EvidenceOut,
    ReviewDecisionOut,
    SuggestionOut,
)


def parse_flags(flags_json: str | None) -> list[str]:
    if not flags_json:
        return []
    try:
        parsed = json.loads(flags_json)
    except (json.JSONDecodeError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _parse_str_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def suggestion_out(suggestion: CodingSuggestion, evidence: list[EvidenceSpan]) -> SuggestionOut:
    return SuggestionOut(
        id=suggestion.id,
        code_type=suggestion.code_type,
        code=suggestion.code,
        description=suggestion.description,
        confidence=suggestion.confidence,
        rationale=suggestion.rationale,
        applies_to=suggestion.applies_to,
        validation_status=suggestion.validation_status,
        review_status=suggestion.review_status,
        corrected_code=suggestion.corrected_code,
        flags=parse_flags(suggestion.flags_json),
        evidence=[
            EvidenceOut(quote=span.quote, start_offset=span.start_offset, end_offset=span.end_offset)
            for span in evidence
        ],
    )


def job_out(job: CodingJob) -> CodingJobOut:
    return CodingJobOut(
        id=job.id,
        encounter_id=job.encounter_id,
        status=job.status,
        error_code=job.error_code,
        code_set_version=job.code_set_version,
        schema_version=job.schema_version,
        prompt_version=job.prompt_version,
        created_at=job.created_at,
        completed_at=job.completed_at,
        missing_documentation=_parse_str_list(job.missing_documentation_json),
        contradictions=_parse_str_list(job.contradictions_json),
    )


def job_detail_out(db: Session, organization_id: str, job: CodingJob) -> CodingJobDetailOut:
    from ..repositories.coding import SuggestionRepository

    repo = SuggestionRepository(db, organization_id)
    base = job_out(job).model_dump()
    return CodingJobDetailOut(
        **base,
        suggestions=[suggestion_out(s, repo.list_evidence(s.id)) for s in repo.list_for_job(job.id)],
    )


def latest_job(db: Session, encounter_id: str) -> CodingJob | None:
    return db.execute(
        select(CodingJob)
        .where(CodingJob.encounter_id == encounter_id)
        .order_by(CodingJob.created_at.desc())
    ).scalars().first()


def review_status(db: Session, encounter_id: str) -> str | None:
    statuses = db.execute(
        select(CodingSuggestion.review_status).where(CodingSuggestion.encounter_id == encounter_id)
    ).scalars().all()
    if not statuses:
        return None
    return "pending" if "pending" in statuses else "reviewed"


def encounter_out(
    encounter: Encounter, coding_status: str | None = None, review: str | None = None
) -> EncounterOut:
    return EncounterOut(
        id=encounter.id,
        date_of_service=encounter.date_of_service,
        encounter_type=encounter.encounter_type,
        place_of_service=encounter.place_of_service,
        patient_reference=encounter.patient_reference,
        payer_context=encounter.payer_context,
        status=encounter.status,
        created_at=encounter.created_at,
        coding_status=coding_status,
        review_status=review,
    )


def encounter_summary(db: Session, encounter: Encounter) -> EncounterOut:
    job = latest_job(db, encounter.id)
    return encounter_out(encounter, job.status if job else None, review_status(db, encounter.id))


def encounter_detail_out(db: Session, organization_id: str, encounter: Encounter) -> EncounterDetailOut:
    from ..repositories.coding import SuggestionRepository
    from ..repositories.encounters import EncounterRepository

    suggestion_repo = SuggestionRepository(db, organization_id)
    suggestions = suggestion_repo.list_for_encounter(encounter.id)
    suggestion_outs = [suggestion_out(s, suggestion_repo.list_evidence(s.id)) for s in suggestions]
    review_outs = [ReviewDecisionOut.model_validate(r) for r in suggestion_repo.list_reviews(encounter.id)]

    job = latest_job(db, encounter.id)
    document = EncounterRepository(db, organization_id).get_document(encounter.id)

    base = encounter_out(
        encounter, job.status if job else None, review_status(db, encounter.id)
    ).model_dump()
    return EncounterDetailOut(
        **base,
        note=document.content if document else None,
        missing_documentation=_parse_str_list(job.missing_documentation_json) if job else [],
        contradictions=_parse_str_list(job.contradictions_json) if job else [],
        suggestions=suggestion_outs,
        reviews=review_outs,
    )
