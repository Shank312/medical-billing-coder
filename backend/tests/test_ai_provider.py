"""AI provider tests: mock success/failure and DeepSeek retry/timeout behavior."""
import httpx
import pytest

from app.ai.base import ProviderRequest
from app.ai.deepseek import DeepSeekProvider
from app.ai.mock import MockProvider
from app.core.errors import ProviderError


def test_mock_provider_success():
    provider = MockProvider(response_json='{"diagnoses": []}')
    response = provider.complete(ProviderRequest(messages=[], model="mock-model", max_tokens=10, temperature=0))
    assert response.content == '{"diagnoses": []}'
    assert response.model == "mock-model"
    assert response.usage.total_tokens == 30


def test_mock_provider_failure():
    provider = MockProvider(fail_with="boom")
    with pytest.raises(ProviderError) as exc:
        provider.complete(ProviderRequest(messages=[], model="m", max_tokens=10, temperature=0))
    assert exc.value.code == "provider_error"


class _FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


def _response(status_code, body=None):
    return _FakeResponse(status_code, body)


def test_deepseek_timeout_retries(monkeypatch):
    monkeypatch.setattr("app.ai.deepseek.time.sleep", lambda s: None)
    calls = {"n": 0}

    def client_factory(*args, **kwargs):
        calls["n"] += 1
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr("app.ai.deepseek.httpx.Client", client_factory)
    provider = DeepSeekProvider(api_key="k", base_url="http://x", max_retries=2)
    with pytest.raises(ProviderError) as exc:
        provider.complete(ProviderRequest(messages=[], model="m", max_tokens=10, temperature=0))
    assert exc.value.code == "provider_timeout"
    assert calls["n"] == 3  # 1 initial + 2 retries


def test_deepseek_5xx_retry_then_success(monkeypatch):
    monkeypatch.setattr("app.ai.deepseek.time.sleep", lambda s: None)
    responses = [
        _response(500),
        _response(200, {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 5}}),
    ]

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return responses.pop(0)

    monkeypatch.setattr("app.ai.deepseek.httpx.Client", FakeClient)
    provider = DeepSeekProvider(api_key="k", base_url="http://x", max_retries=2)
    response = provider.complete(ProviderRequest(messages=[], model="m", max_tokens=10, temperature=0))
    assert response.content == "ok"
    assert response.usage.total_tokens == 5


def test_deepseek_4xx_immediate_failure(monkeypatch):
    monkeypatch.setattr("app.ai.deepseek.time.sleep", lambda s: None)
    calls = {"n": 0}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            calls["n"] += 1
            return _response(400)

    monkeypatch.setattr("app.ai.deepseek.httpx.Client", FakeClient)
    provider = DeepSeekProvider(api_key="k", base_url="http://x", max_retries=2)
    with pytest.raises(ProviderError) as exc:
        provider.complete(ProviderRequest(messages=[], model="m", max_tokens=10, temperature=0))
    assert exc.value.code == "provider_error"
    assert calls["n"] == 1
