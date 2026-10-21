"""Tenant-scoped encounter and source-note repository."""
from datetime import date

from sqlalchemy import func, select

from ..core.errors import NotFoundError
from ..models.encounter import Encounter
from ..models.encounter_document import EncounterDocument
from .base import TenantScopedRepository


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

    def list(self, *, limit: int = 50, offset: int = 0) -> list[Encounter]:
        return self.db.execute(
            select(Encounter)
            .where(Encounter.organization_id == self.organization_id)
            .order_by(Encounter.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars().all()

    def count(self) -> int:
        return self.db.execute(
            select(func.count())
            .select_from(Encounter)
            .where(Encounter.organization_id == self.organization_id)
        ).scalar_one()

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
