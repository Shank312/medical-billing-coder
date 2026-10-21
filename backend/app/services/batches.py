"""Batch ingestion orchestration (Phase 5).

Documents are uploaded to storage and processed by the Celery worker. Each stage
is idempotent under at-least-once delivery: documents are claimed atomically
(``pending -> processing``) and terminal states are never overwritten.
"""
import hashlib
import json
from datetime import date
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.errors import BadRequestError
from ..core.time import utcnow
from ..db.session import SessionLocal
from ..models.ingestion import IngestionBatch, IngestionDocument
from ..storage import LocalFileStorage, Storage, generate_storage_key
from .audit import AuditService
from .documents import (
    SUPPORTED_EXTENSIONS,
    DocumentProcessingError,
    extract_pdf_text,
    parse_csv_rows,
    sniff_type,
)


def _get_storage() -> Storage:
    return LocalFileStorage(get_settings().storage_dir)


def publish_document(document_id: str) -> None:
    from ..tasks.documents import process_batch_document_task

    process_batch_document_task.delay(document_id)


def create_batch(
    db: Session,
    *,
    organization_id: str,
    actor_user_id: str,
    date_of_service: date | None = None,
) -> IngestionBatch:
    batch = IngestionBatch(
        organization_id=organization_id, created_by=actor_user_id, date_of_service=date_of_service
    )
    db.add(batch)
    db.flush()
    AuditService.append(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="batch.created",
        resource_type="ingestion_batch",
        resource_id=batch.id,
    )
    return batch


def add_document(
    db: Session,
    *,
    organization_id: str,
    batch_id: str,
    filename: str,
    media_type: str,
    source,
) -> IngestionDocument:
    """Stream an upload to storage, compute hash, and record a document.

    Rejects unsupported/oversized/empty/mismatched files; deduplicates by content
    hash within the batch (idempotent on retry).
    """
    settings = get_settings()
    storage = _get_storage()
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise BadRequestError("Unsupported file type", code="unsupported_type")

    key = generate_storage_key(ext)
    hasher = hashlib.sha256()
    size = 0
    header = b""

    try:
        with storage.open_write(key) as out:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_file_size:
                    raise BadRequestError("File exceeds the size limit", code="file_too_large")
                if len(header) < 8:
                    header = (header + chunk)[:8]
                hasher.update(chunk)
                out.write(chunk)
    except Exception:
        storage.delete(key)
        raise

    if size == 0:
        storage.delete(key)
        raise BadRequestError("Empty file", code="empty_file")

    doc_type = sniff_type(filename, header)
    if doc_type is None:
        storage.delete(key)
        raise BadRequestError("File content does not match its declared type", code="unsupported_type")

    content_hash = hasher.hexdigest()
    existing = db.execute(
        select(IngestionDocument).where(
            IngestionDocument.batch_id == batch_id,
            IngestionDocument.content_hash == content_hash,
        )
    ).scalar_one_or_none()
    if existing is not None:
        storage.delete(key)
        return existing

    document = IngestionDocument(
        batch_id=batch_id,
        organization_id=organization_id,
        original_filename=filename,
        storage_key=key,
        media_type=doc_type,
        byte_size=size,
        content_hash=content_hash,
        extraction_status="pending",
    )
    db.add(document)
    db.flush()
    _refresh_batch(db, batch_id)
    return document


def _refresh_batch(db: Session, batch_id: str) -> None:
    docs = db.execute(
        select(IngestionDocument).where(IngestionDocument.batch_id == batch_id)
    ).scalars().all()
    batch = db.get(IngestionBatch, batch_id)
    if batch is None:
        return
    batch.total_documents = len(docs)
    batch.processed_documents = sum(
        1 for d in docs if d.extraction_status in ("completed", "requires_manual")
    )
    batch.failed_documents = sum(1 for d in docs if d.extraction_status == "failed")
    terminal = sum(
        1 for d in docs if d.extraction_status in ("completed", "failed", "requires_manual")
    )
    if docs and terminal == len(docs):
        batch.status = "completed"
        batch.completed_at = utcnow()
    elif terminal:
        batch.status = "processing"
    else:
        batch.status = "queued"


def _claim_document(db: Session, document_id: str) -> IngestionDocument | None:
    result = db.execute(
        update(IngestionDocument)
        .where(IngestionDocument.id == document_id, IngestionDocument.extraction_status == "pending")
        .values(extraction_status="processing", attempt_count=IngestionDocument.attempt_count + 1)
    )
    if result.rowcount == 0:
        return None
    db.commit()
    return db.get(IngestionDocument, document_id)


def _create_encounter_and_code(db, *, organization_id, actor_user_id, date_of_service, note, **extra):
    from ..core.errors import AiDisabledError, PhiNotApprovedError
    from .coding import enqueue_coding_job
    from .encounters import create_encounter

    encounter = create_encounter(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        date_of_service=date_of_service,
        note=note,
        encounter_type=extra.get("encounter_type"),
        place_of_service=extra.get("place_of_service"),
        patient_reference=extra.get("patient_reference"),
        payer_context=extra.get("payer_context"),
    )
    try:
        job = enqueue_coding_job(
            db, organization_id=organization_id, actor_user_id=actor_user_id, encounter_id=encounter.id
        )
    except (AiDisabledError, PhiNotApprovedError):
        job = None  # coding disabled — encounter is still created; coding deferred
    return encounter, job


def process_document(document_id: str) -> IngestionDocument | None:
    """Process one uploaded document (the worker's entrypoint)."""
    db = SessionLocal()
    try:
        document = _claim_document(db, document_id)
        if document is None:
            return None  # already terminal / being processed

        batch = db.get(IngestionBatch, document.batch_id)
        storage = _get_storage()
        try:
            with storage.open(document.storage_key) as source:
                if document.media_type == "pdf":
                    text, has_text = extract_pdf_text(source)
                    if not has_text:
                        document.extraction_status = "requires_manual"
                        document.error_code = "no_text"
                        document.completed_at = utcnow()
                    elif batch.date_of_service is None:
                        document.extraction_status = "requires_manual"
                        document.error_code = "missing_date"
                        document.extracted_text = text
                        document.completed_at = utcnow()
                    else:
                        document.extracted_text = text
                        encounter, job = _create_encounter_and_code(
                            db,
                            organization_id=document.organization_id,
                            actor_user_id=batch.created_by,
                            date_of_service=batch.date_of_service,
                            note=text,
                        )
                        document.encounter_id = encounter.id
                        document.coding_job_id = job.id if job else None
                        document.extraction_status = "completed"
                        document.completed_at = utcnow()
                else:  # csv
                    try:
                        text = source.read().decode("utf-8")
                    except UnicodeDecodeError as exc:
                        raise DocumentProcessingError("csv_schema_invalid", "CSV must be UTF-8 text") from exc
                    rows, errors = parse_csv_rows(text)
                    if not rows:
                        document.extraction_status = "failed"
                        document.error_code = "csv_no_valid_rows"
                        document.row_results_json = json.dumps({"rows": [], "errors": errors})
                        document.completed_at = utcnow()
                    else:
                        results = []
                        for index, row in enumerate(rows, start=1):
                            encounter, job = _create_encounter_and_code(
                                db,
                                organization_id=document.organization_id,
                                actor_user_id=batch.created_by,
                                date_of_service=date.fromisoformat(row["date_of_service"]),
                                note=row["note"],
                                encounter_type=row["encounter_type"],
                                place_of_service=row["place_of_service"],
                                patient_reference=row["patient_reference"],
                                payer_context=row["payer_context"],
                            )
                            results.append(
                                {"row": index, "encounter_id": encounter.id, "coding_job_id": job.id if job else None}
                            )
                        document.row_results_json = json.dumps({"rows": results, "errors": errors})
                        document.extraction_status = "completed"
                        document.completed_at = utcnow()
        except DocumentProcessingError as exc:
            document.extraction_status = "failed"
            document.error_code = exc.code
            document.completed_at = utcnow()
        except Exception:
            # transient (storage/DB): return to pending and let the task retry
            document.extraction_status = "pending"
            db.commit()
            raise

        _refresh_batch(db, document.batch_id)
        db.commit()
        return document
    finally:
        db.close()


def mark_document_failed(document_id: str, error_code: str) -> None:
    """Mark a document failed using a fresh session (safe from worker/request)."""
    db = SessionLocal()
    try:
        document = db.get(IngestionDocument, document_id)
        if document is not None and document.extraction_status not in (
            "completed",
            "failed",
            "requires_manual",
        ):
            document.extraction_status = "failed"
            document.error_code = error_code
            document.completed_at = utcnow()
            _refresh_batch(db, document.batch_id)
            db.commit()
    finally:
        db.close()
