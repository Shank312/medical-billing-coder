"""Deterministic code-reference validation and import tests."""
from datetime import date

import pytest

from app.core.errors import ConflictError
from app.db.session import SessionLocal
from app.services.reference_data import import_code_set, lookup_code

ORG_ID = "00000000-0000-0000-0000-000000000001"


def _import(db, *, code_type="icd10cm", version="2025.1", codes=None):
    return import_code_set(
        db,
        code_type=code_type,
        source="SYNTHETIC_TEST",
        version=version,
        effective_start=None,
        effective_end=None,
        codes=codes or [{"code": "F32.9", "description": "Major depressive disorder, recurrent, unspecified"}],
        imported_by=None,
        organization_id=ORG_ID,
    )


def test_lookup_unavailable_before_import():
    db = SessionLocal()
    try:
        result = lookup_code(db, code_type="icd10cm", code="F32.9", date_of_service=None)
        assert result["status"] == "reference_data_unavailable"
    finally:
        db.close()


def test_lookup_valid_and_unknown():
    db = SessionLocal()
    try:
        _import(db)
        db.commit()
        assert lookup_code(db, code_type="icd10cm", code="F32.9", date_of_service=None)["status"] == "valid"
        assert lookup_code(db, code_type="icd10cm", code="Z99.9", date_of_service=None)["status"] == "unknown"
    finally:
        db.rollback()
        db.close()


def test_date_of_service_validity():
    db = SessionLocal()
    try:
        import_code_set(
            db,
            code_type="icd10cm",
            source="SYNTHETIC_TEST",
            version="2025.1",
            effective_start=None,
            effective_end=None,
            codes=[{"code": "F32.9", "description": "MDD", "effective_start": date(2025, 1, 1)}],
            imported_by=None,
            organization_id=ORG_ID,
        )
        db.commit()
        assert (
            lookup_code(db, code_type="icd10cm", code="F32.9", date_of_service=date(2024, 6, 1))["status"]
            == "date_invalid"
        )
        assert (
            lookup_code(db, code_type="icd10cm", code="F32.9", date_of_service=date(2025, 6, 1))["status"]
            == "valid"
        )
    finally:
        db.rollback()
        db.close()


def test_import_rejects_duplicate():
    db = SessionLocal()
    try:
        _import(db)
        db.commit()
        with pytest.raises(ConflictError):
            _import(db)
    finally:
        db.rollback()
        db.close()
