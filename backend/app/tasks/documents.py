"""Background batch-document processing task (Phase 5).

The task receives only the document id; the worker re-fetches and verifies the
document/batch from the database. Retries use bounded backoff; exhaustion leaves a
stable ``failed`` state.
"""
from ..celery_app import celery_app
from ..core.config import get_settings
from ..services.batches import mark_document_failed, process_document


@celery_app.task(
    bind=True,
    name="ingestion.process_document",
    max_retries=None,
    ignore_result=True,
    acks_late=True,
)
def process_batch_document_task(self, document_id: str) -> None:
    settings = get_settings()
    try:
        process_document(document_id)
    except Exception as exc:  # noqa: BLE001 - transient failures retry; exhaust to failed
        if self.request.retries >= settings.coding_max_retries:
            mark_document_failed(document_id, "retry_exhausted")
            return
        countdown = settings.coding_retry_backoff_base ** self.request.retries
        raise self.retry(exc=exc, countdown=countdown)
