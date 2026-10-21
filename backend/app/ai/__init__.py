"""Provider-independent AI layer (Phase 2).

The coding workflow talks only to the ``AIProvider`` interface; DeepSeek is one
adapter and the mock provider runs locally so tests never touch the network.
"""
from .base import AIProvider, ChatMessage, ProviderRequest, ProviderResponse, ProviderUsage
from .registry import get_provider

__all__ = [
    "AIProvider",
    "ChatMessage",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderUsage",
    "get_provider",
]
