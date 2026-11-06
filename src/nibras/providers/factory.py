"""Factory for creating ProviderAdapter instances (D-15)."""

from __future__ import annotations

from .anthropic import AnthropicAdapter
from .base import ProviderAdapter
from .openai import OpenAIAdapter
from .openai_compatible import OpenAICompatibleAdapter


def create_adapter(
    kind: str,
    model: str,
    api_key: str,
    context_window: int = 128000,
    base_url: str = "",
) -> ProviderAdapter:
    if kind == "openai":
        return OpenAIAdapter(
            base_url=base_url,
            model=model,
            api_key=api_key,
            context_window=context_window,
        )
    if kind == "anthropic":
        return AnthropicAdapter(
            base_url=base_url,
            model=model,
            api_key=api_key,
            context_window=context_window,
        )
    if kind == "openai_compatible":
        return OpenAICompatibleAdapter(
            base_url=base_url,
            model=model,
            api_key=api_key,
            context_window=context_window,
        )
    raise ValueError(f"Jenis provider tidak didukung: {kind}")
