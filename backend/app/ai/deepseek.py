"""DeepSeek provider adapter (OpenAI-compatible chat completions API).

Only standard, documented parameters are sent (model, messages, temperature,
max_tokens, stream). No privacy-related parameters are invented. Errors are
sanitized: the API key, request body, and response body are never included in
raised errors or logs.
"""
import time

import httpx

from ..core.config import get_settings
from ..core.errors import ProviderError
from .base import AIProvider, ProviderRequest, ProviderResponse, ProviderUsage

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class DeepSeekProvider(AIProvider):
    name = "deepseek"
    transmits_phi = True

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.deepseek_api_key
        self.base_url = (base_url or settings.deepseek_base_url).rstrip("/")
        self.model = model or settings.deepseek_model
        self.timeout = float(timeout if timeout is not None else settings.ai_timeout_seconds)
        self.max_retries = int(max_retries if max_retries is not None else settings.ai_max_retries)

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": request.model or self.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False,
        }

        last_error: ProviderError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, headers=headers, json=body)
            except httpx.TimeoutException:
                last_error = ProviderError("Provider request timed out", code="provider_timeout")
            except httpx.HTTPError:
                last_error = ProviderError("Provider connection failed", code="provider_unavailable")
            else:
                if response.status_code in _RETRYABLE_STATUS:
                    last_error = ProviderError(
                        f"Provider unavailable (HTTP {response.status_code})",
                        code="provider_unavailable",
                    )
                elif response.status_code >= 400:
                    raise ProviderError(
                        f"Provider rejected the request (HTTP {response.status_code})",
                        code="provider_error",
                    )
                else:
                    return self._parse(response, request)

            if attempt < self.max_retries:
                self._backoff(attempt)

        raise last_error or ProviderError("Provider request failed", code="provider_error")

    def _parse(self, response: httpx.Response, request: ProviderRequest) -> ProviderResponse:
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Malformed provider response", code="provider_error") from exc

        usage = data.get("usage") or {}
        return ProviderResponse(
            content=content,
            model=data.get("model", self.model),
            usage=ProviderUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
            request_id=request.request_id,
        )

    @staticmethod
    def _backoff(attempt: int) -> None:
        time.sleep(min(2 ** attempt, 8.0))
