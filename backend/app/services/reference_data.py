"""Deterministic code-reference validation and import workflow.

Reference datasets are *not* invented here. An organization loads an authorized
dataset (e.g. CMS/CDC public data, or licensed CPT content) through the import
endpoint. Until a dataset is loaded for a code type, validation returns the
explicit ``reference_data_unavailable`` status — it never claims validation passed.
"""
from datetime import date

from sqlalchemy.orm import Session

from ..core.errors import BadRequestError, ConflictError
from ..models.code_reference import CodeReferenceSet
from ..repositories.references import ReferenceRepository
from .audit import AuditService

VALID_CODE_TYPES = {"icd10cm", "cpt", "hcpcs"}

# Deterministic validation statuses.
VALID = "valid"
DATE_INVALID = "date_invalid"
UNKNOWN = "unknown"
REFERENCE_UNAVAILABLE = "reference_data_unavailable"


def import_code_set(
    db: Session,
    *,
    code_type: str,
    source: str,
    version: str,
    effective_start: date | None,
    effective_end: date | None,
    codes: list[dict],
    imported_by: str | None,
    organization_id: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> CodeReferenceSet:
    if code_type not in VALID_CODE_TYPES:
        raise BadRequestError("Invalid code type", code="invalid_code_type")
    if not codes:
        raise BadRequestError("Code list must not be empty", code="empty_code_set")

    repo = ReferenceRepository(db)
    if repo.get_set_by_key(code_type, source, version) is not None:
        raise ConflictError("Code set already imported", code="code_set_exists")

    ref_set = repo.create_set(
        code_type=code_type,
        source=source,
        version=version,
        effective_start=effective_start,
        effective_end=effective_end,
        imported_by=imported_by,
    )
    for item in codes:
        repo.add_code(
            set_id=ref_set.id,
            code=item["code"],
            description=item.get("description"),
            effective_start=item.get("effective_start"),
            effective_end=item.get("effective_end"),
            is_billable=item.get("is_billable", True),
        )
    ref_set.record_count = len(codes)

    AuditService.append(
        db,
        organization_id=organization_id,
        actor_user_id=imported_by,
        action="reference_data.imported",
        resource_type="code_reference_set",
        resource_id=ref_set.id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"code_type": code_type, "source": source, "version": version, "record_count": len(codes)},
    )
    return ref_set


def _effective(set_row: CodeReferenceSet, ref, dos: date | None) -> bool:
    if dos is not None:
        if ref.effective_start and dos < ref.effective_start:
            return False
        if ref.effective_end and dos > ref.effective_end:
            return False
    return True


def lookup_code(db: Session, *, code_type: str, code: str, date_of_service: date | None) -> dict:
    """Return ``{code, code_type, status, description, version, source}``."""
    repo = ReferenceRepository(db)
    if not repo.has_any_set(code_type):
        return {
            "code": code,
            "code_type": code_type,
            "status": REFERENCE_UNAVAILABLE,
            "description": None,
            "version": None,
            "source": None,
        }

    for ref_set in repo.latest_sets(code_type):
        ref = repo.find_code(ref_set.id, code)
        if ref is None:
            continue
        if not _effective(ref_set, ref, date_of_service):
            return {
                "code": code,
                "code_type": code_type,
                "status": DATE_INVALID,
                "description": ref.description,
                "version": ref_set.version,
                "source": ref_set.source,
            }
        return {
            "code": code,
            "code_type": code_type,
            "status": VALID,
            "description": ref.description,
            "version": ref_set.version,
            "source": ref_set.source,
        }

    return {
        "code": code,
        "code_type": code_type,
        "status": UNKNOWN,
        "description": None,
        "version": None,
        "source": None,
    }


def validate_code(db: Session, *, code_type: str, code: str, date_of_service: date | None) -> str:
    """Return the deterministic validation status for a code against loaded data."""
    return lookup_code(db, code_type=code_type, code=code, date_of_service=date_of_service)["status"]


def latest_set_version(db: Session, code_type: str) -> str | None:
    sets = ReferenceRepository(db).latest_sets(code_type)
    return sets[0].version if sets else None
