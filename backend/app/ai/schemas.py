"""AI coding-result schemas.

The model returns JSON parsed into ``CodingOutput``. Every suggestion is a
*candidate*; deterministic validation and human review happen afterwards and are
never conflated with the model's output.
"""
from pydantic import BaseModel, Field

# Prompt and schema versions are recorded on every job/attempt so results are
# reproducible and auditable.
PROMPT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"


class EvidenceSpan(BaseModel):
    quote: str
    start: int = 0
    end: int = 0


class Suggestion(BaseModel):
    code: str
    code_type: str = "icd10cm"  # icd10cm | cpt | hcpcs | modifier
    description: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str | None = None
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    applies_to: str | None = None  # modifier: the procedure code it modifies


class CodingOutput(BaseModel):
    diagnoses: list[Suggestion] = Field(default_factory=list)
    procedures: list[Suggestion] = Field(default_factory=list)
    modifiers: list[Suggestion] = Field(default_factory=list)
    missing_documentation: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
