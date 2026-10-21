"""Code-reference API schemas."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CodeReferenceItem(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    description: str | None = Field(default=None, max_length=500)
    effective_start: date | None = None
    effective_end: date | None = None
    is_billable: bool = True


class CodeReferenceImport(BaseModel):
    code_type: str = Field(..., pattern="^(icd10cm|cpt|hcpcs)$")
    source: str = Field(..., min_length=1, max_length=255)
    version: str = Field(..., min_length=1, max_length=100)
    effective_start: date | None = None
    effective_end: date | None = None
    codes: list[CodeReferenceItem] = Field(..., min_length=1)


class CodeReferenceSetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code_type: str
    source: str
    version: str
    effective_start: date | None
    effective_end: date | None
    record_count: int
    created_at: datetime


class CodeLookupOut(BaseModel):
    code: str
    code_type: str
    status: str
    description: str | None
    version: str | None
    source: str | None
