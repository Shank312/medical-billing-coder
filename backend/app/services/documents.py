"""Document validation, PDF text extraction, and CSV parsing (Phase 5)."""
import csv
import hashlib
import io
from datetime import date
from pathlib import Path
from typing import BinaryIO

from pypdf import PdfReader

from ..core.config import get_settings

SUPPORTED_EXTENSIONS = {".pdf", ".csv"}
PDF_MAGIC = b"%PDF-"

CSV_REQUIRED_COLUMNS = ("date_of_service", "note")
CSV_OPTIONAL_COLUMNS = ("encounter_type", "place_of_service", "patient_reference", "payer_context")


class DocumentProcessingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def sniff_type(filename: str, header: bytes) -> str | None:
    """Return 'pdf'/'csv' when extension AND content match; else None."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "pdf" if header.startswith(PDF_MAGIC) else None
    if ext == ".csv":
        try:
            header.decode("utf-8")
        except UnicodeDecodeError:
            return None
        return "csv"
    return None


def extract_pdf_text(source: BinaryIO) -> tuple[str, bool]:
    """Extract text from a text-based PDF. Returns ``(text, has_usable_text)``.

    Raises ``DocumentProcessingError`` for encrypted, oversized, or unparseable PDFs.
    Does not OCR: image-only PDFs yield an empty string and ``has_usable_text=False``.
    """
    settings = get_settings()
    try:
        reader = PdfReader(source)
    except Exception as exc:  # noqa: BLE001 - normalize parser errors
        raise DocumentProcessingError("pdf_extraction_failed", "Unable to parse the PDF") from exc
    if reader.is_encrypted:
        raise DocumentProcessingError("encrypted_pdf", "Encrypted PDFs are not supported")
    if len(reader.pages) > settings.max_pdf_pages:
        raise DocumentProcessingError(
            "pdf_too_many_pages", f"PDF exceeds the {settings.max_pdf_pages} page limit"
        )
    parts = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(parts).strip()
    if len(text) > settings.max_extracted_chars:
        raise DocumentProcessingError("extracted_too_long", "Extracted text exceeds the size limit")
    return text, bool(text)


def _validate_csv_row(row: dict) -> list[str]:
    errors: list[str] = []
    try:
        date.fromisoformat((row.get("date_of_service") or "").strip())
    except ValueError:
        errors.append("invalid_date")
    note = (row.get("note") or "").strip()
    if not note:
        errors.append("missing_note")
    elif len(note) > 50_000:
        errors.append("note_too_long")
    return errors


def parse_csv_rows(text: str) -> tuple[list[dict], list[dict]]:
    """Parse CSV text into validated encounter rows.

    Returns ``(rows, errors)``. ``rows`` are normalized encounter dicts; ``errors``
    are ``{row, errors}``. Malformed rows are never silently dropped.
    """
    settings = get_settings()
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []
    missing = [c for c in CSV_REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        raise DocumentProcessingError(
            "csv_schema_invalid", f"Missing required columns: {', '.join(missing)}"
        )

    rows: list[dict] = []
    errors: list[dict] = []
    seen: set[str] = set()
    for line_no, row in enumerate(reader, start=2):
        row_errors = _validate_csv_row(row)
        if row_errors:
            errors.append({"row": line_no, "errors": row_errors})
            continue
        normalized = {
            "date_of_service": (row["date_of_service"] or "").strip(),
            "note": (row["note"] or "").strip(),
            "encounter_type": (row.get("encounter_type") or "").strip() or None,
            "place_of_service": (row.get("place_of_service") or "").strip() or None,
            "patient_reference": (row.get("patient_reference") or "").strip() or None,
            "payer_context": (row.get("payer_context") or "").strip() or None,
        }
        row_hash = hashlib.sha256(
            f"{normalized['date_of_service']}|{normalized['note']}".encode()
        ).hexdigest()
        if row_hash in seen:
            errors.append({"row": line_no, "errors": ["duplicate_row"]})
            continue
        seen.add(row_hash)
        if len(rows) >= settings.max_csv_rows:
            raise DocumentProcessingError(
                "csv_too_many_rows", f"CSV exceeds the {settings.max_csv_rows} row limit"
            )
        rows.append(normalized)
    return rows, errors
