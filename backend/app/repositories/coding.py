"""Tenant-scoped coding job, suggestion, evidence, and review repositories."""
import json
from datetime import datetime

from sqlalchemy import func, select

from ..core.errors import NotFoundError
from ..models.coding_job import CodingAttempt, CodingJob
from ..models.coding_suggestion import CodingSuggestion, EvidenceSpan
from ..models.encounter import Encounter
from ..models.review_decision import ReviewDecision
from .base import TenantScopedRepository


class CodingJobRepository(TenantScopedRepository):
    def get(self, job_id: str) -> CodingJob:
        job = self.db.get(CodingJob, job_id)
        if job is None:
            raise NotFoundError("Coding job not found")
        self.require_tenant_match(job.organization_id)
        return job

    def get_by_client_request(self, client_request_id: str) -> CodingJob | None:
        return self.db.execute(
            select(CodingJob).where(
                CodingJob.organization_id == self.organization_id,
                CodingJob.client_request_id == client_request_id,
            )
        ).scalar_one_or_none()

    def create(
        self, *, encounter_id: str, client_request_id: str | None = None, created_by: str | None = None
    ) -> CodingJob:
        job = CodingJob(
            organization_id=self.organization_id,
            encounter_id=encounter_id,
            client_request_id=client_request_id,
            created_by=created_by,
            status="queued",
        )
        self.db.add(job)
        self.db.flush()
        return job

    def add_attempt(
        self,
        *,
        job_id: str,
        provider_name: str,
        model_name: str,
        prompt_version: str,
        schema_version: str,
        code_set_version: str | None,
        request_id: str | None,
        status: str,
        attempt_number: int = 1,
        started_at: datetime | None = None,
        latency_ms: int | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        error_code: str | None = None,
    ) -> CodingAttempt:
        attempt = CodingAttempt(
            job_id=job_id,
            attempt_number=attempt_number,
            started_at=started_at,
            provider_name=provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            schema_version=schema_version,
            code_set_version=code_set_version,
            request_id=request_id,
            status=status,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            error_code=error_code,
        )
        self.db.add(attempt)
        self.db.flush()
        return attempt

    def list_jobs(self, *, status: str | None = None, limit: int = 50, offset: int = 0) -> list[CodingJob]:
        stmt = select(CodingJob).where(CodingJob.organization_id == self.organization_id)
        if status:
            stmt = stmt.where(CodingJob.status == status)
        return self.db.execute(
            stmt.order_by(CodingJob.created_at.desc()).limit(limit).offset(offset)
        ).scalars().all()

    def count_jobs(self, status: str | None = None) -> int:
        stmt = select(func.count()).select_from(CodingJob).where(
            CodingJob.organization_id == self.organization_id
        )
        if status:
            stmt = stmt.where(CodingJob.status == status)
        return self.db.execute(stmt).scalar_one()


class SuggestionRepository(TenantScopedRepository):
    def _encounter(self, encounter_id: str) -> Encounter:
        encounter = self.db.get(Encounter, encounter_id)
        if encounter is None:
            raise NotFoundError("Encounter not found")
        self.require_tenant_match(encounter.organization_id)
        return encounter

    def get(self, suggestion_id: str) -> CodingSuggestion:
        suggestion = self.db.get(CodingSuggestion, suggestion_id)
        if suggestion is None:
            raise NotFoundError("Suggestion not found")
        self._encounter(suggestion.encounter_id)
        return suggestion

    def list_for_encounter(self, encounter_id: str) -> list[CodingSuggestion]:
        self._encounter(encounter_id)
        return self.db.execute(
            select(CodingSuggestion)
            .where(CodingSuggestion.encounter_id == encounter_id)
            .order_by(CodingSuggestion.created_at)
        ).scalars().all()

    def list_for_job(self, job_id: str) -> list[CodingSuggestion]:
        return self.db.execute(
            select(CodingSuggestion)
            .where(CodingSuggestion.job_id == job_id)
            .order_by(CodingSuggestion.created_at)
        ).scalars().all()

    def create(
        self,
        *,
        encounter_id: str,
        job_id: str,
        code_type: str,
        code: str,
        description: str | None = None,
        confidence: float | None = None,
        rationale: str | None = None,
        applies_to: str | None = None,
        parent_suggestion_id: str | None = None,
        validation_status: str | None = None,
        flags: list[str] | None = None,
    ) -> CodingSuggestion:
        suggestion = CodingSuggestion(
            encounter_id=encounter_id,
            job_id=job_id,
            code_type=code_type,
            code=code,
            description=description,
            confidence=confidence,
            rationale=rationale,
            applies_to=applies_to,
            parent_suggestion_id=parent_suggestion_id,
            validation_status=validation_status,
            flags_json=json.dumps(flags) if flags else None,
        )
        self.db.add(suggestion)
        self.db.flush()
        return suggestion

    def add_evidence(self, *, suggestion_id: str, quote: str, start_offset: int, end_offset: int) -> EvidenceSpan:
        span = EvidenceSpan(
            suggestion_id=suggestion_id, quote=quote, start_offset=start_offset, end_offset=end_offset
        )
        self.db.add(span)
        self.db.flush()
        return span

    def list_evidence(self, suggestion_id: str) -> list[EvidenceSpan]:
        return self.db.execute(
            select(EvidenceSpan).where(EvidenceSpan.suggestion_id == suggestion_id)
        ).scalars().all()

    def add_review(
        self,
        *,
        suggestion_id: str,
        encounter_id: str,
        reviewer_id: str | None,
        decision: str,
        corrected_code: str | None = None,
        note: str | None = None,
    ) -> ReviewDecision:
        row = ReviewDecision(
            suggestion_id=suggestion_id,
            encounter_id=encounter_id,
            reviewer_id=reviewer_id,
            decision=decision,
            corrected_code=corrected_code,
            note=note,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def list_reviews(self, encounter_id: str) -> list[ReviewDecision]:
        return self.db.execute(
            select(ReviewDecision)
            .where(ReviewDecision.encounter_id == encounter_id)
            .order_by(ReviewDecision.created_at)
        ).scalars().all()
