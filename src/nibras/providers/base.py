"""Provider adapter interface (D-15).

An adapter translates canonical messages to one provider and declares
the model's capabilities explicitly. In Tahap 1 only text streaming is
used; tool calling and vision are declared but unused.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..core.messages import CanonicalMessage, estimate_tokens


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

    def trim_messages(self, messages: list[CanonicalMessage]) -> tuple[list[CanonicalMessage], bool]:
        """Return (messages_to_send, truncated_flag)."""
        budget = self.context_window
        if budget <= 0:
            return list(messages), False
        # Reserve ~10% of the window for the reply.
        budget = int(budget * 0.9)
        system = [m for m in messages if m.role == "system"]
        rest = [m for m in messages if m.role != "system"]
        total = sum(estimate_tokens(m.content) for m in messages)
        if total <= budget:
            return list(messages), False
        kept: list[CanonicalMessage] = []
        used = sum(estimate_tokens(m.content) for m in system)
        for msg in reversed(rest):
            cost = estimate_tokens(msg.content)
            if used + cost > budget and kept:
                break
            kept.append(msg)
            used += cost
        kept.reverse()
        return system + kept, True

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
