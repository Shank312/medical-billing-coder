"""Celery application for background coding jobs.

Redis is used only as the broker (task delivery). The database remains the
authoritative source of job ownership, tenant context, and final coding results;
no clinical content is placed in task arguments (only the job id).
"""
from celery import Celery

from .core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "medical_billing_coder",
    broker=_settings.celery_broker_url,
    include=["app.tasks.coding", "app.tasks.documents"],
)

celery_app.conf.update(
    task_always_eager=_settings.celery_task_always_eager,
    task_eager_propagates=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_ignore_result=True,
    task_time_limit=_settings.coding_task_timeout_seconds,
    task_soft_time_limit=max(_settings.coding_task_timeout_seconds - 30, 30),
    task_default_queue="coding",
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": _settings.coding_task_timeout_seconds * 2},
    broker_connection_retry_on_startup=True,
)
