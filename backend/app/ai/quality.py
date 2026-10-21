"""Deterministic quality checks applied to model output.

These checks never trust the model: evidence quotes must be exact substrings of
the source note, offsets are recomputed, and hallucinated evidence is dropped and
flagged.
"""
from .schemas import CodingOutput


def _iter_suggestions(output: CodingOutput):
    yield from output.diagnoses
    yield from output.procedures
    yield from output.modifiers


def compute_offsets(note: str, quote: str) -> tuple[int, int] | None:
    """Return ``(start, end)`` for a verbatim quote, or ``None`` if not present."""
    index = note.find(quote)
    if index == -1:
        return None
    return index, index + len(quote)


def validate_evidence(note: str, output: CodingOutput) -> CodingOutput:
    """Correct evidence offsets and drop hallucinated quotes.

    Any suggestion with a quote that is not an exact substring of the note loses
    that span and is flagged ``hallucinated_evidence``.
    """
    for suggestion in _iter_suggestions(output):
        validated = []
        for span in suggestion.evidence:
            offsets = compute_offsets(note, span.quote)
            if offsets is None:
                if "hallucinated_evidence" not in suggestion.flags:
                    suggestion.flags.append("hallucinated_evidence")
                continue
            span.start, span.end = offsets
            validated.append(span)
        suggestion.evidence = validated
    return output
