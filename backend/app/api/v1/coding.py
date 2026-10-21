"""Coding-job endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.errors import BadRequestError
from ...core.rate_limit import configured_rate_limit_dependency
from ...db.session import get_db_session
from ...repositories.coding import CodingJobRepository
from ...schemas.coding import CodingJobDetailOut, CodingJobListOut
from ...services.serializers import job_detail_out, job_out
from ..deps import AuthContext, get_auth_context

router = APIRouter(prefix="/coding-jobs", tags=["coding-jobs"])

_default_rate_limit = Depends(configured_rate_limit_dependency("rate_limit_default", key_prefix="coding"))

JOB_STATUSES = ("queued", "running", "completed", "failed")


@router.get("", response_model=CodingJobListOut, dependencies=[_default_rate_limit])
def list_jobs(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    if status is not None and status not in JOB_STATUSES:
        raise BadRequestError("Invalid status filter", code="invalid_status")

    repo = CodingJobRepository(db, auth.organization_id)
    jobs = repo.list_jobs(status=status, limit=limit, offset=offset)
    total = repo.count_jobs(status=status)
    return CodingJobListOut(
        items=[job_out(job) for job in jobs], total=total, limit=limit, offset=offset
    )


@router.get("/{job_id}", response_model=CodingJobDetailOut, dependencies=[_default_rate_limit])
def get_job(
    job_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    job = CodingJobRepository(db, auth.organization_id).get(job_id)
    return job_detail_out(db, auth.organization_id, job)
