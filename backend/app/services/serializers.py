"""Response serializers that assemble suggestion/evidence/job objects."""
import json

from sqlalchemy.orm import Session

from ..models.coding_job import CodingJob
from ..models.coding_suggestion import CodingSuggestion, EvidenceSpan
from ..schemas.coding import CodingJobDetailOut, CodingJobOut, EvidenceOut, SuggestionOut


def parse_flags(flags_json: str | None) -> list[str]:
    if not flags_json:
        return []
    try:
        parsed = json.loads(flags_json)
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


def job_detail_out(db: Session, organization_id: str, job: CodingJob) -> CodingJobDetailOut:
    from ..repositories.coding import SuggestionRepository

    repo = SuggestionRepository(db, organization_id)
    base = CodingJobOut.model_validate(job).model_dump()
    return CodingJobDetailOut(
        **base,
        suggestions=[suggestion_out(s, repo.list_evidence(s.id)) for s in repo.list_for_job(job.id)],
    )
