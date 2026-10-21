"""Background coding job task.

The task receives only the job id (never clinical content or tenant context, which
are re-fetched and verified from the database by the worker). Retries use bounded
exponential backoff; exhaustion leaves a stable ``failed`` state.
"""
from ..celery_app import celery_app
from ..core.config import get_settings
from ..services.coding import RetryableCodingError, mark_job_failed, process_coding_job


@celery_app.task(
    bind=True,
    name="coding.process_job",
    max_retries=None,
    ignore_result=True,
    acks_late=True,
)
def process_coding_job_task(self, job_id: str) -> None:
    settings = get_settings()
    try:
        process_coding_job(job_id, attempt_number=self.request.retries + 1)
    except RetryableCodingError as exc:
        if self.request.retries >= settings.coding_max_retries:
            mark_job_failed(job_id, "retry_exhausted")
            return
        countdown = settings.coding_retry_backoff_base ** self.request.retries
        raise self.retry(exc=exc, countdown=countdown)
