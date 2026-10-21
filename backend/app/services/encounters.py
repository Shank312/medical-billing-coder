"""Encounter creation and source-note storage."""
import hashlib
from datetime import date

from sqlalchemy.orm import Session

from ..models.encounter import Encounter
from ..repositories.encounters import EncounterRepository
from .audit import AuditService


def create_encounter(
    db: Session,
    *,
    organization_id: str,
    actor_user_id: str,
    date_of_service: date,
    note: str,
    encounter_type: str | None = None,
    place_of_service: str | None = None,
    patient_reference: str | None = None,
    payer_context: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Encounter:
    repo = EncounterRepository(db, organization_id)
    encounter = repo.create(
        date_of_service=date_of_service,
        encounter_type=encounter_type,
        place_of_service=place_of_service,
        patient_reference=patient_reference,
        payer_context=payer_context,
        created_by=actor_user_id,
    )
    content_hash = hashlib.sha256(note.encode("utf-8")).hexdigest()
    repo.add_document(encounter_id=encounter.id, content=note, content_hash=content_hash)

    # Audit metadata only — never the note text.
    AuditService.append(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="encounter.created",
        resource_type="encounter",
        resource_id=encounter.id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"date_of_service": date_of_service.isoformat(), "content_hash": content_hash},
    )
    return encounter
