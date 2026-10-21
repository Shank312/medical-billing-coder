"""Code-reference endpoints: import datasets, lookup, and list."""
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ...constants.roles import REFERENCE_ADMIN_ROLES
from ...core.rate_limit import configured_rate_limit_dependency
from ...db.session import get_db_session
from ...repositories.references import ReferenceRepository
from ...schemas.reference import CodeLookupOut, CodeReferenceImport, CodeReferenceSetOut
from ..deps import AuthContext, get_auth_context, request_info, require_roles

router = APIRouter(prefix="/code-references", tags=["code-references"])

_default_rate_limit = Depends(configured_rate_limit_dependency("rate_limit_default", key_prefix="references"))


@router.post("/import", response_model=CodeReferenceSetOut, status_code=201, dependencies=[_default_rate_limit])
def import_code_set(
    body: CodeReferenceImport,
    request: Request,
    auth: AuthContext = Depends(require_roles(*REFERENCE_ADMIN_ROLES)),
    db: Session = Depends(get_db_session),
):
    ip, ua = request_info(request)
    from ...services import reference_data as reference_service

    try:
        ref_set = reference_service.import_code_set(
            db,
            code_type=body.code_type,
            source=body.source,
            version=body.version,
            effective_start=body.effective_start,
            effective_end=body.effective_end,
            codes=[item.model_dump() for item in body.codes],
            imported_by=auth.user_id,
            organization_id=auth.organization_id,
            ip_address=ip,
            user_agent=ua,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return CodeReferenceSetOut.model_validate(ref_set)


@router.get("/lookup", response_model=CodeLookupOut, dependencies=[_default_rate_limit])
def lookup_code(
    code_type: str = Query(..., pattern="^(icd10cm|cpt|hcpcs)$"),
    code: str = Query(..., min_length=1, max_length=20),
    date_of_service: date | None = Query(None),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    from ...services import reference_data as reference_service

    result = reference_service.lookup_code(db, code_type=code_type, code=code, date_of_service=date_of_service)
    return CodeLookupOut(**result)


@router.get("/sets", response_model=list[CodeReferenceSetOut], dependencies=[_default_rate_limit])
def list_sets(
    code_type: str | None = Query(None),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    sets = ReferenceRepository(db).list_sets(code_type)
    return [CodeReferenceSetOut.model_validate(s) for s in sets]
