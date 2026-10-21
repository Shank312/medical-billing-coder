"""Coding workflow unit tests: output parsing, evidence validation, confidence."""
import pytest

from app.ai.quality import compute_offsets, validate_evidence
from app.ai.schemas import CodingOutput, EvidenceSpan, Suggestion
from app.core.errors import ProviderError
from app.services.coding import parse_output


def test_parse_output_valid():
    output = parse_output(
        '{"diagnoses": [{"code": "F32.9", "code_type": "icd10cm"}], "procedures": [], '
        '"modifiers": [], "missing_documentation": [], "contradictions": []}'
    )
    assert output.diagnoses[0].code == "F32.9"


def test_parse_output_invalid_json():
    with pytest.raises(ProviderError) as exc:
        parse_output("this is not json")
    assert exc.value.code == "invalid_model_output"


def test_parse_output_malformed():
    with pytest.raises(ProviderError) as exc:
        parse_output('{"diagnoses": "not-a-list"}')
    assert exc.value.code == "invalid_model_output"


def test_parse_output_strips_markdown_fences():
    output = parse_output(
        '```json\n{"diagnoses": [], "procedures": [], "modifiers": [], '
        '"missing_documentation": [], "contradictions": []}\n```'
    )
    assert output.diagnoses == []


def test_compute_offsets():
    note = "hello world"
    assert compute_offsets(note, "world") == (6, 11)
    assert compute_offsets(note, "absent") is None


def test_validate_evidence_corrects_offsets():
    note = "Patient has major depressive disorder."
    output = CodingOutput(
        diagnoses=[Suggestion(code="F32.9", evidence=[EvidenceSpan(quote="major depressive disorder", start=999, end=999)])]
    )
    validate_evidence(note, output)
    span = output.diagnoses[0].evidence[0]
    assert note[span.start : span.end] == "major depressive disorder"


def test_hallucinated_evidence_rejected():
    note = "Patient has hypertension."
    output = CodingOutput(
        diagnoses=[Suggestion(code="F32.9", evidence=[EvidenceSpan(quote="diabetes", start=0, end=0)])]
    )
    validate_evidence(note, output)
    assert output.diagnoses[0].evidence == []
    assert "hallucinated_evidence" in output.diagnoses[0].flags
