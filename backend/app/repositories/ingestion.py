"""Tenant-scoped batch and document repositories."""
from sqlalchemy import func, select

from ..core.errors import NotFoundError
from ..models.ingestion import IngestionBatch, IngestionDocument
from .base import TenantScopedRepository


class BatchRepository(TenantScopedRepository):
    def get(self, batch_id: str) -> IngestionBatch:
        batch = self.db.get(IngestionBatch, batch_id)
        if batch is None:
            raise NotFoundError("Batch not found")
        self.require_tenant_match(batch.organization_id)
        return batch

    def list(self, *, limit: int = 50, offset: int = 0) -> list[IngestionBatch]:
        return self.db.execute(
            select(IngestionBatch)
            .where(IngestionBatch.organization_id == self.organization_id)
            .order_by(IngestionBatch.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars().all()

    def count(self) -> int:
        return self.db.execute(
            select(func.count())
            .select_from(IngestionBatch)
            .where(IngestionBatch.organization_id == self.organization_id)
        ).scalar_one()


class DocumentRepository(TenantScopedRepository):
    def get(self, document_id: str) -> IngestionDocument:
        document = self.db.get(IngestionDocument, document_id)
        if document is None:
            raise NotFoundError("Document not found")
        self.require_tenant_match(document.organization_id)
        return document

    def list_for_batch(self, batch_id: str) -> list[IngestionDocument]:
        return self.db.execute(
            select(IngestionDocument)
            .where(
                IngestionDocument.batch_id == batch_id,
                IngestionDocument.organization_id == self.organization_id,
            )
            .order_by(IngestionDocument.created_at)
        ).scalars().all()
