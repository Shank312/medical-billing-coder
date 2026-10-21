"""Coding-domain API schemas."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class EncounterCreate(BaseModel):
    date_of_service: date
    encounter_type: str | None = Field(default=None, max_length=100)
    place_of_service: str | None = Field(default=None, max_length=20)
    patient_reference: str | None = Field(default=None, max_length=255)
    payer_context: str | None = Field(default=None, max_length=255)
    note: str = Field(..., min_length=1, max_length=50_000)


class EncounterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    date_of_service: date
    encounter_type: str | None
    place_of_service: str | None
    patient_reference: str | None
    payer_context: str | None
    status: str
    created_at: datetime


class EncounterListOut(BaseModel):
    items: list[EncounterOut]
    total: int
    limit: int
    offset: int


class EvidenceOut(BaseModel):
    quote: str
    start_offset: int
    end_offset: int


class SuggestionOut(BaseModel):
    id: str
    code_type: str
    code: str
    description: str | None
    confidence: float | None
    rationale: str | None
    applies_to: str | None
    validation_status: str | None
    review_status: str
    corrected_code: str | None
    flags: list[str]
    evidence: list[EvidenceOut]


class CodingJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    encounter_id: str
    status: str
    error_code: str | None
    code_set_version: str | None
    schema_version: str | None
    prompt_version: str | None
    created_at: datetime
    completed_at: datetime | None


class CodingJobDetailOut(CodingJobOut):
    suggestions: list[SuggestionOut]


class ReviewRequest(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected|corrected)$")
    corrected_code: str | None = Field(default=None, max_length=20)
    note: str | None = Field(default=None, max_length=2000)


class ReviewDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    decision: str
    corrected_code: str | None
    note: str | None
    created_at: datetime


class EncounterDetailOut(EncounterOut):
    suggestions: list[SuggestionOut]
    reviews: list[ReviewDecisionOut]
