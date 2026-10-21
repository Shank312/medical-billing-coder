"""Coding-job endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...core.rate_limit import configured_rate_limit_dependency
from ...db.session import get_db_session
from ...repositories.coding import CodingJobRepository
from ...schemas.coding import CodingJobDetailOut
from ...services.serializers import job_detail_out
from ..deps import AuthContext, get_auth_context

router = APIRouter(prefix="/coding-jobs", tags=["coding-jobs"])

_default_rate_limit = Depends(configured_rate_limit_dependency("rate_limit_default", key_prefix="coding"))


@router.get("/{job_id}", response_model=CodingJobDetailOut, dependencies=[_default_rate_limit])
def get_job(
    job_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    job = CodingJobRepository(db, auth.organization_id).get(job_id)
    return job_detail_out(db, auth.organization_id, job)
