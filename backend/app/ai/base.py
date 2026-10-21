"""Provider-independent AI interface.

A provider adapter implements ``complete``. The coding workflow depends only on
this interface, so DeepSeek can be replaced without touching the workflow.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ProviderRequest:
    messages: list[ChatMessage]
    model: str
    max_tokens: int
    temperature: float
    request_id: str | None = None  # correlation id for logs/attempts


@dataclass
class ProviderUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ProviderResponse:
    content: str
    model: str
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    request_id: str | None = None


class AIProvider(ABC):
    """Common interface implemented by every model provider."""

    name: str = "base"
    model: str = ""
    # Whether calling this provider sends PHI to an external party. Local providers
    # (the mock) set this to False so they need no PHI approval gate.
    transmits_phi: bool = True

    @abstractmethod
    def complete(self, request: ProviderRequest) -> ProviderResponse:
        """Return a completion. Raise ``ProviderError`` on failure (never leak keys)."""
        raise NotImplementedError
