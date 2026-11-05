"""Provider adapter interface (D-15).

An adapter translates canonical messages to one provider and declares
the model's capabilities explicitly. In Tahap 1 only text streaming is
used; tool calling and vision are declared but unused.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..core.messages import CanonicalMessage


@dataclass(frozen=True)
class ModelCapabilities:
    streaming: bool = True
    tool_calling: bool = False
    vision: bool = False
    context_window: int = 0


class ProviderAdapter(ABC):
    """One provider behind a common interface."""

    name: str = "unknown"

    def __init__(self, base_url: str, model: str, api_key: str,
                 context_window: int):
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.context_window = context_window

    @property
    @abstractmethod
    def capabilities(self) -> ModelCapabilities:
        ...

    @abstractmethod
    async def stream(self, messages: list[CanonicalMessage]):
        """Yield text deltas for the assistant reply.

        Raises on failure; the caller decides about retry (see D-21).
        """
        ...

    @abstractmethod
    async def check_ready(self) -> bool:
        """Lightweight readiness check (e.g. list models)."""
        ...
