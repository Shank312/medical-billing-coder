"""Provider registry and selection.

Providers are registered by name and selected at runtime from configuration
(``ai_provider``), so swapping DeepSeek for another provider never touches the
coding workflow.
"""
from ..core.config import get_settings
from ..core.errors import ProviderError
from .base import AIProvider
from .deepseek import DeepSeekProvider
from .mock import MockProvider

_REGISTRY: dict[str, type[AIProvider]] = {
    MockProvider.name: MockProvider,
    DeepSeekProvider.name: DeepSeekProvider,
}


def register_provider(provider_cls: type[AIProvider]) -> None:
    """Register an additional provider implementation."""
    _REGISTRY[provider_cls.name] = provider_cls


def get_provider(name: str | None = None) -> AIProvider:
    """Instantiate the configured (or named) provider."""
    settings = get_settings()
    resolved = name or settings.ai_provider
    if resolved == MockProvider.name:
        return MockProvider(response_json=settings.mock_provider_response or None)
    provider_cls = _REGISTRY.get(resolved)
    if provider_cls is None:
        raise ProviderError(f"Unknown AI provider: {resolved}", code="provider_unknown")
    return provider_cls()
