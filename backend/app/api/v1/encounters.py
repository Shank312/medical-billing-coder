"""Encounter endpoints: create, list, detail, submit-for-coding, and review."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ...constants.roles import ENCOUNTER_WRITE_ROLES, REVIEW_ROLES
from ...core.rate_limit import configured_rate_limit_dependency
from ...db.session import get_db_session
from ...repositories.coding import SuggestionRepository
from ...repositories.encounters import EncounterRepository
from ...schemas.coding import (
    CodingJobDetailOut,
    EncounterCreate,
    EncounterDetailOut,
    EncounterListOut,
    EncounterOut,
    ReviewDecisionOut,
    ReviewRequest,
    SuggestionOut,
)
from ...services.serializers import job_detail_out, suggestion_out
from ..deps import AuthContext, get_auth_context, request_info, require_roles

router = APIRouter(prefix="/encounters", tags=["encounters"])

_default_rate_limit = Depends(configured_rate_limit_dependency("rate_limit_default", key_prefix="encounters"))


@router.post("", response_model=EncounterOut, status_code=201, dependencies=[_default_rate_limit])
def create_encounter(
    body: EncounterCreate,
    request: Request,
    auth: AuthContext = Depends(require_roles(*ENCOUNTER_WRITE_ROLES)),
    db: Session = Depends(get_db_session),
):
    ip, ua = request_info(request)
    from ...services import encounters as encounters_service

    try:
        encounter = encounters_service.create_encounter(
            db,
            organization_id=auth.organization_id,
            actor_user_id=auth.user_id,
            date_of_service=body.date_of_service,
            note=body.note,
            encounter_type=body.encounter_type,
            place_of_service=body.place_of_service,
            patient_reference=body.patient_reference,
            payer_context=body.payer_context,
            ip_address=ip,
            user_agent=ua,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return EncounterOut.model_validate(encounter)


@router.get("", response_model=EncounterListOut, dependencies=[_default_rate_limit])
def list_encounters(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    repo = EncounterRepository(db, auth.organization_id)
    items = repo.list(limit=limit, offset=offset)
    total = repo.count()
    return EncounterListOut(
        items=[EncounterOut.model_validate(e) for e in items], total=total, limit=limit, offset=offset
    )


@router.get("/{encounter_id}", response_model=EncounterDetailOut, dependencies=[_default_rate_limit])
def get_encounter(
    encounter_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    encounter = EncounterRepository(db, auth.organization_id).get(encounter_id)
    suggestion_repo = SuggestionRepository(db, auth.organization_id)
    suggestions = suggestion_repo.list_for_encounter(encounter_id)
    suggestion_outs = [suggestion_out(s, suggestion_repo.list_evidence(s.id)) for s in suggestions]
    review_outs = [ReviewDecisionOut.model_validate(r) for r in suggestion_repo.list_reviews(encounter_id)]

    base = EncounterOut.model_validate(encounter).model_dump()
    return EncounterDetailOut(**base, suggestions=suggestion_outs, reviews=review_outs)


@router.post("/{encounter_id}/code", response_model=CodingJobDetailOut, dependencies=[_default_rate_limit])
def submit_for_coding(
    encounter_id: str,
    request: Request,
    auth: AuthContext = Depends(require_roles(*ENCOUNTER_WRITE_ROLES)),
    db: Session = Depends(get_db_session),
):
    ip, ua = request_info(request)
    client_request_id = request.headers.get("Idempotency-Key")
    from ...services import coding as coding_service

    try:
        job = coding_service.submit_coding(
            db,
            organization_id=auth.organization_id,
            actor_user_id=auth.user_id,
            encounter_id=encounter_id,
            client_request_id=client_request_id,
            ip_address=ip,
            user_agent=ua,
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return job_detail_out(db, auth.organization_id, job)


@router.post(
    "/{encounter_id}/suggestions/{suggestion_id}/review",
    response_model=SuggestionOut,
    dependencies=[_default_rate_limit],
)
def review_suggestion(
    encounter_id: str,
    suggestion_id: str,
    body: ReviewRequest,
    request: Request,
    auth: AuthContext = Depends(require_roles(*REVIEW_ROLES)),
    db: Session = Depends(get_db_session),
):
    ip, ua = request_info(request)
    from ...services import coding as coding_service

    try:
        suggestion = coding_service.review_suggestion(
            db,
            organization_id=auth.organization_id,
            actor_user_id=auth.user_id,
            encounter_id=encounter_id,
            suggestion_id=suggestion_id,
            decision=body.decision,
            corrected_code=body.corrected_code,
            note=body.note,
            ip_address=ip,
            user_agent=ua,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    repo = SuggestionRepository(db, auth.organization_id)
    return suggestion_out(suggestion, repo.list_evidence(suggestion.id))
