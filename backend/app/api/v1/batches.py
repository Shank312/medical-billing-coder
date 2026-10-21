"""Batch ingestion endpoints (Phase 5)."""
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.errors import BadRequestError
from ...core.rate_limit import configured_rate_limit_dependency
from ...db.session import get_db_session
from ...repositories.ingestion import BatchRepository, DocumentRepository
from ...schemas.ingestion import BatchCreateIn, BatchDetailOut, BatchListOut, BatchOut, DocumentOut
from ...services import batches as batches_service
from ..deps import AuthContext, get_auth_context

router = APIRouter(prefix="/batches", tags=["batches"])

_default_rate_limit = Depends(configured_rate_limit_dependency("rate_limit_default", key_prefix="batches"))


@router.post("", response_model=BatchOut, status_code=201, dependencies=[_default_rate_limit])
def create_batch(
    payload: BatchCreateIn | None = None,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    batch = batches_service.create_batch(
        db,
        organization_id=auth.organization_id,
        actor_user_id=auth.user_id,
        date_of_service=payload.date_of_service if payload else None,
    )
    db.commit()
    return batch


@router.post("/{batch_id}/documents", response_model=list[DocumentOut], status_code=201, dependencies=[_default_rate_limit])
def upload_documents(
    batch_id: str,
    files: list[UploadFile] = File(...),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    settings = get_settings()
    if len(files) > settings.max_upload_files_per_batch:
        raise BadRequestError(
            f"A batch may contain at most {settings.max_upload_files_per_batch} files",
            code="too_many_files",
        )
    BatchRepository(db, auth.organization_id).get(batch_id)  # tenant check

    documents = []
    for upload in files:
        document = batches_service.add_document(
            db,
            organization_id=auth.organization_id,
            batch_id=batch_id,
            filename=upload.filename or "unnamed",
            media_type=upload.content_type or "",
            source=upload.file,
        )
        documents.append(document)
    db.commit()

    for document in documents:
        batches_service.publish_document(document.id)

    # Eager mode (tests) may have processed documents in a separate session;
    # refresh so the response reflects the authoritative persisted state.
    for document in documents:
        db.refresh(document)
    return documents


@router.get("", response_model=BatchListOut, dependencies=[_default_rate_limit])
def list_batches(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    repo = BatchRepository(db, auth.organization_id)
    return BatchListOut(
        items=[BatchOut.model_validate(b) for b in repo.list(limit=limit, offset=offset)],
        total=repo.count(),
        limit=limit,
        offset=offset,
    )


@router.get("/{batch_id}", response_model=BatchDetailOut, dependencies=[_default_rate_limit])
def get_batch(
    batch_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    batch = BatchRepository(db, auth.organization_id).get(batch_id)
    documents = DocumentRepository(db, auth.organization_id).list_for_batch(batch_id)
    return BatchDetailOut(
        **BatchOut.model_validate(batch).model_dump(),
        documents=[DocumentOut.model_validate(d) for d in documents],
    )


@router.post("/{batch_id}/documents/{document_id}/retry", response_model=DocumentOut, dependencies=[_default_rate_limit])
def retry_document(
    batch_id: str,
    document_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    document = DocumentRepository(db, auth.organization_id).get(document_id)
    if document.batch_id != batch_id:
        raise BadRequestError("Document is not in this batch", code="not_in_batch")
    if document.extraction_status != "failed":
        raise BadRequestError("Only failed documents can be retried", code="not_retryable")
    document.extraction_status = "pending"
    document.error_code = None
    db.commit()
    batches_service.publish_document(document.id)
    db.refresh(document)
    return document
