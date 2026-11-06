"""OpenAI-Compatible provider adapter (D-15, D-21).

Uses the official ``openai`` SDK with a custom ``base_url``. The SDK is
imported lazily inside :meth:`_client` so the application window can
appear before the SDK is loaded (D-59).

Retry policy (D-21): technical failures (network, timeout, rate limit)
*before the first token* are retried up to 3 times with growing delays
(1 s, 2 s, 4 s). A failure mid-stream is never retried; the partial text
is kept and the caller marks the message failed.

Context trim: the whole conversation is sent while it fits the context
window (rough token estimate). When it does not fit, the oldest messages
are dropped (system messages are kept) and ``truncated`` is reported so
the UI can show a marker.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from ..core.messages import CanonicalMessage, estimate_tokens
from .base import ModelCapabilities, ProviderAdapter

MAX_RETRIES_BEFORE_FIRST_TOKEN = 3
RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)


class OpenAICompatibleAdapter(ProviderAdapter):
    name = "openai-compatible"

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            streaming=True,
            tool_calling=False,
            vision=False,
            context_window=self.context_window,
        )

    # -- context handling -------------------------------------------------
    def trim_messages(self, messages: list[CanonicalMessage]):
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

    # -- SDK client (lazy import, D-59) ------------------------------------
    def _client(self):
        from openai import AsyncOpenAI

        # max_retries=0: the retry policy is the adapter's own (D-21).
        # SDK-internal retries would double-count and hide the real
        # failure point from the caller.
        return AsyncOpenAI(
            api_key=self.api_key, base_url=self.base_url, max_retries=0
        )

    def _to_provider(self, messages: list[CanonicalMessage]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

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
        payload = self._to_provider(to_send)
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES_BEFORE_FIRST_TOKEN + 1):
            try:
                async for delta in self._stream_once(payload):
                    yield delta
                return
            except _RetryableBeforeFirstToken as exc:
                last_error = exc.cause
                if attempt >= MAX_RETRIES_BEFORE_FIRST_TOKEN:
                    break
                await asyncio.sleep(RETRY_DELAYS_SECONDS[attempt])
        assert last_error is not None
        raise last_error

    async def _stream_once(self, payload: list[dict]) -> AsyncIterator[str]:
        from openai import APIConnectionError, APIStatusError, APITimeoutError

        client = self._client()
        got_first_token = False
        saw_finish = False
        try:
            stream = await client.chat.completions.create(
                model=self.model, messages=payload, stream=True,
            )
            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if choice is not None and choice.finish_reason is not None:
                    saw_finish = True
                delta = getattr(choice, "delta", None) if choice else None
                text = getattr(delta, "content", None) if delta else None
                if text:
                    got_first_token = True
                    yield text
            # A stream that ends without a finish_reason chunk was cut
            # off mid-stream (D-21): partial text is kept by the caller
            # and the message is marked failed, never silently completed.
            if not saw_finish:
                raise _StreamIncompleteError(
                    "Stream terputus sebelum selesai."
                )
        except (APIConnectionError, APITimeoutError) as exc:
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
    """The stream ended without a finish_reason chunk (cut off mid-stream)."""
