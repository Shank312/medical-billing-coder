"""Batch ingestion API schemas (Phase 5)."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    batch_id: str
    original_filename: str
    media_type: str
    byte_size: int
    extraction_status: str
    error_code: str | None = None
    encounter_id: str | None = None
    coding_job_id: str | None = None
    attempt_count: int
    created_at: datetime
    completed_at: datetime | None = None


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    date_of_service: date | None = None
    total_documents: int
    processed_documents: int
    failed_documents: int
    created_at: datetime
    completed_at: datetime | None = None


class BatchDetailOut(BatchOut):
    documents: list[DocumentOut] = []


class BatchListOut(BaseModel):
    items: list[BatchOut]
    total: int
    limit: int
    offset: int


class BatchCreateIn(BaseModel):
    date_of_service: date | None = None
