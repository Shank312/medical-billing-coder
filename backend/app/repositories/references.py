"""Code-reference dataset repository (global reference data, not tenant-scoped)."""
import json
from datetime import date

from sqlalchemy import func, select

from ..models.code_reference import CodeReference, CodeReferenceSet
from .base import BaseRepository


class ReferenceRepository(BaseRepository):
    def create_set(
        self,
        *,
        code_type: str,
        source: str,
        version: str,
        effective_start: date | None,
        effective_end: date | None,
        imported_by: str | None,
        metadata: dict | None = None,
    ) -> CodeReferenceSet:
        ref_set = CodeReferenceSet(
            code_type=code_type,
            source=source,
            version=version,
            effective_start=effective_start,
            effective_end=effective_end,
            imported_by=imported_by,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        self.db.add(ref_set)
        self.db.flush()
        return ref_set

    def add_code(
        self,
        *,
        set_id: str,
        code: str,
        description: str | None,
        effective_start: date | None,
        effective_end: date | None,
        is_billable: bool = True,
        metadata: dict | None = None,
    ) -> CodeReference:
        ref = CodeReference(
            set_id=set_id,
            code=code,
            description=description,
            effective_start=effective_start,
            effective_end=effective_end,
            is_billable=is_billable,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        self.db.add(ref)
        self.db.flush()
        return ref

    def get_set(self, set_id: str) -> CodeReferenceSet | None:
        return self.db.get(CodeReferenceSet, set_id)

    def get_set_by_key(self, code_type: str, source: str, version: str) -> CodeReferenceSet | None:
        return self.db.execute(
            select(CodeReferenceSet).where(
                CodeReferenceSet.code_type == code_type,
                CodeReferenceSet.source == source,
                CodeReferenceSet.version == version,
            )
        ).scalar_one_or_none()

    def latest_sets(self, code_type: str) -> list[CodeReferenceSet]:
        return self.db.execute(
            select(CodeReferenceSet)
            .where(CodeReferenceSet.code_type == code_type)
            .order_by(CodeReferenceSet.created_at.desc())
        ).scalars().all()

    def find_code(self, set_id: str, code: str) -> CodeReference | None:
        return self.db.execute(
            select(CodeReference).where(
                CodeReference.set_id == set_id, CodeReference.code == code
            )
        ).scalar_one_or_none()

    def has_any_set(self, code_type: str) -> bool:
        count = self.db.execute(
            select(func.count())
            .select_from(CodeReferenceSet)
            .where(CodeReferenceSet.code_type == code_type)
        ).scalar_one()
        return count > 0

    def list_sets(self, code_type: str | None = None) -> list[CodeReferenceSet]:
        query = select(CodeReferenceSet).order_by(CodeReferenceSet.created_at.desc())
        if code_type:
            query = query.where(CodeReferenceSet.code_type == code_type)
        return self.db.execute(query).scalars().all()

    def list_codes(self, set_id: str, limit: int = 100, offset: int = 0) -> list[CodeReference]:
        return self.db.execute(
            select(CodeReference)
            .where(CodeReference.set_id == set_id)
            .order_by(CodeReference.code)
            .limit(limit)
            .offset(offset)
        ).scalars().all()
