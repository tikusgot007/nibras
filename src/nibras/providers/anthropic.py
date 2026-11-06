"""Official Anthropic provider adapter (D-15, D-21).

Uses the official ``anthropic`` SDK targeting the official Anthropic API endpoint
(or custom endpoint if specified). The SDK is imported lazily inside
:meth:`_client` so the application window can appear before the SDK is
loaded (D-59).
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from ..core.messages import CanonicalMessage
from .base import ModelCapabilities, ProviderAdapter

MAX_RETRIES_BEFORE_FIRST_TOKEN = 3
RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)


class AnthropicAdapter(ProviderAdapter):
    name = "anthropic"

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            streaming=True,
            tool_calling=True,
            vision=True,
            context_window=self.context_window,
        )

    def _client(self):
        from anthropic import AsyncAnthropic

        base = self.base_url.strip() or None
        return AsyncAnthropic(
            api_key=self.api_key, base_url=base, max_retries=0
        )

    def _to_provider(
        self, messages: list[CanonicalMessage]
    ) -> tuple[str | None, list[dict]]:
        """Separate system messages from conversational messages."""
        system_parts = [m.content for m in messages if m.role == "system"]
        system_text = "\n\n".join(system_parts) if system_parts else None

        chat_messages = [m for m in messages if m.role != "system"]
        payload_messages: list[dict] = []
        for m in chat_messages:
            role = "user" if m.role == "user" else "assistant"
            if payload_messages and payload_messages[-1]["role"] == role:
                payload_messages[-1]["content"] += "\n\n" + m.content
            else:
                payload_messages.append({"role": role, "content": m.content})

        if not payload_messages:
            payload_messages.append({"role": "user", "content": ""})

        return system_text, payload_messages

    async def check_ready(self) -> bool:
        try:
            client = self._client()
            try:
                await asyncio.wait_for(client.models.list(), timeout=15)
            finally:
                await client.close()
            return True
        except Exception:
            return False

    async def stream(
        self, messages: list[CanonicalMessage]
    ) -> AsyncIterator[str]:
        """Yield text deltas. Retries only before the first token."""
        to_send, _ = self.trim_messages(messages)
        system_text, payload_messages = self._to_provider(to_send)
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES_BEFORE_FIRST_TOKEN + 1):
            try:
                async for delta in self._stream_once(system_text, payload_messages):
                    yield delta
                return
            except _RetryableBeforeFirstToken as exc:
                last_error = exc.cause
                if attempt >= MAX_RETRIES_BEFORE_FIRST_TOKEN:
                    break
                await asyncio.sleep(RETRY_DELAYS_SECONDS[attempt])
        assert last_error is not None
        raise last_error

    async def _stream_once(
        self, system_text: str | None, messages: list[dict]
    ) -> AsyncIterator[str]:
        from anthropic import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            RateLimitError,
        )

        client = self._client()
        got_first_token = False
        saw_finish = False
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
        }
        if system_text:
            kwargs["system"] = system_text

        try:
            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    if text:
                        got_first_token = True
                        yield text
                final_message = await stream.get_final_message()
                if final_message and final_message.stop_reason is not None:
                    saw_finish = True

            if not saw_finish:
                raise _StreamIncompleteError("Stream terputus sebelum selesai.")
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            if not got_first_token:
                raise _RetryableBeforeFirstToken(exc) from exc
            raise
        except APIStatusError as exc:
            retryable = exc.status_code in (408, 409, 429, 500, 502, 503, 504)
            if retryable and not got_first_token:
                raise _RetryableBeforeFirstToken(exc) from exc
            raise
        finally:
            await client.close()


class _RetryableBeforeFirstToken(Exception):
    def __init__(self, cause: Exception):
        super().__init__(str(cause))
        self.cause = cause


class _StreamIncompleteError(Exception):
    """The stream ended without completing (cut off mid-stream)."""
