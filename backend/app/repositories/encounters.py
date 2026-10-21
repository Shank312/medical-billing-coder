"""Tenant-scoped encounter and source-note repository."""
from datetime import date

from sqlalchemy import exists, func, or_, select

from ..core.errors import NotFoundError
from ..models.coding_job import CodingJob
from ..models.coding_suggestion import CodingSuggestion
from ..models.encounter import Encounter
from ..models.encounter_document import EncounterDocument
from .base import TenantScopedRepository

# Allowlisted sort fields (actual encounter columns) and workflow status filters.
SORT_FIELDS = ("date_of_service", "created_at", "patient_reference", "encounter_type")
STATUS_FILTERS = ("all", "coded", "pending", "not_coded")


class EncounterRepository(TenantScopedRepository):
    def get(self, encounter_id: str) -> Encounter:
        encounter = self.db.get(Encounter, encounter_id)
        if encounter is None:
            raise NotFoundError("Encounter not found")
        self.require_tenant_match(encounter.organization_id)
        return encounter

    def create(
        self,
        *,
        date_of_service: date,
        encounter_type: str | None = None,
        place_of_service: str | None = None,
        patient_reference: str | None = None,
        payer_context: str | None = None,
        created_by: str | None = None,
    ) -> Encounter:
        encounter = Encounter(
            organization_id=self.organization_id,
            date_of_service=date_of_service,
            encounter_type=encounter_type,
            place_of_service=place_of_service,
            patient_reference=patient_reference,
            payer_context=payer_context,
            created_by=created_by,
        )
        self.db.add(encounter)
        self.db.flush()
        return encounter

    def _apply_filters(self, stmt, search: str | None, status: str):
        """Apply tenant scoping plus search/status filters to a select statement.

        All filtering happens in the database; the note text and any field beyond
        ``patient_reference``/``encounter_type`` is never searchable.
        """
        stmt = stmt.where(Encounter.organization_id == self.organization_id)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Encounter.patient_reference.ilike(pattern),
                    Encounter.encounter_type.ilike(pattern),
                )
            )
        if status == "coded":
            stmt = stmt.where(
                exists().where(
                    CodingJob.encounter_id == Encounter.id,
                    CodingJob.status == "completed",
                )
            )
        elif status == "pending":
            stmt = stmt.where(
                exists().where(
                    CodingSuggestion.encounter_id == Encounter.id,
                    CodingSuggestion.review_status == "pending",
                )
            )
        elif status == "not_coded":
            stmt = stmt.where(~exists().where(CodingJob.encounter_id == Encounter.id))
        return stmt

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        status: str = "all",
        sort: str = "created_at",
        order: str = "desc",
    ) -> list[Encounter]:
        stmt = self._apply_filters(select(Encounter), search, status)
        column = getattr(Encounter, sort)  # validated against SORT_FIELDS upstream
        stmt = stmt.order_by(column.desc() if order == "desc" else column.asc())
        stmt = stmt.limit(limit).offset(offset)
        return self.db.execute(stmt).scalars().all()

    def count(self, search: str | None = None, status: str = "all") -> int:
        stmt = self._apply_filters(select(func.count()).select_from(Encounter), search, status)
        return self.db.execute(stmt).scalar_one()

    def add_document(
        self, *, encounter_id: str, content: str, content_hash: str, document_type: str = "clinical_note"
    ) -> EncounterDocument:
        document = EncounterDocument(
            encounter_id=encounter_id,
            content=content,
            content_hash=content_hash,
            document_type=document_type,
        )
        self.db.add(document)
        self.db.flush()
        return document

    def get_document(self, encounter_id: str) -> EncounterDocument | None:
        return self.db.execute(
            select(EncounterDocument)
            .where(EncounterDocument.encounter_id == encounter_id)
            .order_by(EncounterDocument.created_at.desc())
        ).scalars().first()
