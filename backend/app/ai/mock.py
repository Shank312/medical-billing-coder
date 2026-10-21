"""Deterministic mock provider — runs locally with no network or API key.

Used by the test suite and for local development. It returns a caller-supplied
JSON string (defaulting to an empty coding output), or raises on demand to
simulate provider failures and timeouts.
"""
from ..core.errors import ProviderError
from .base import AIProvider, ProviderRequest, ProviderResponse, ProviderUsage

_EMPTY_OUTPUT = (
    '{"diagnoses": [], "procedures": [], "modifiers": [], '
    '"missing_documentation": [], "contradictions": []}'
)


class MockProvider(AIProvider):
    name = "mock"
    model = "mock-model"
    transmits_phi = False

    def __init__(
        self,
        response_json: str | None = None,
        *,
        fail_with: str | None = None,
        fail_code: str = "provider_error",
        transmits_phi: bool = False,
    ) -> None:
        self._response = response_json if response_json is not None else _EMPTY_OUTPUT
        self._fail_with = fail_with
        self._fail_code = fail_code
        self.transmits_phi = transmits_phi

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        if self._fail_with is not None:
            raise ProviderError(self._fail_with, code=self._fail_code)
        return ProviderResponse(
            content=self._response,
            model="mock-model",
            usage=ProviderUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            request_id=request.request_id,
        )
