"""Adapter tests with a local mock OpenAI-compatible server (D-15, D-21).

No real API is ever called. The mock server implements the subset of the
OpenAI API the adapter uses: ``GET /v1/models`` and streaming
``POST /v1/chat/completions`` (SSE).
"""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from nibras.core.messages import CanonicalMessage
from nibras.providers.openai_compatible import OpenAICompatibleAdapter


class MockState:
    def __init__(self):
        self.fail_first_n = 0
        self.fail_mid_stream_after = -1  # -1 = never
        self.requests = 0
        self.last_body: dict | None = None


def _sse_chunk(content: str) -> bytes:
    payload = {"choices": [{"delta": {"content": content}, "finish_reason": None}]}
    return f"data: {json.dumps(payload)}\n\n".encode()


def make_handler(state: MockState):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # keep test output clean
            pass

        def _send_json(self, code: int, obj: dict):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/v1/models":
                self._send_json(200, {"data": [{"id": "aan-hermes"}]})
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            state.last_body = json.loads(self.rfile.read(length) or b"{}")
            state.requests += 1
            if self.path != "/v1/chat/completions":
                self._send_json(404, {"error": "not found"})
                return
            if state.requests <= state.fail_first_n:
                self._send_json(500, {"error": {"message": "boom"}})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            chunks = ["Halo ", "dunia", "!"]
            for i, text in enumerate(chunks):
                if state.fail_mid_stream_after == i:
                    # Close the connection mid-stream without [DONE].
                    # NOTE: closing self.connection directly does NOT send
                    # FIN: rfile/wfile hold dup()ed fds of the same socket.
                    # Set close_connection so the handler closes them in
                    # finish() and the client actually sees EOF.
                    self.close_connection = True
                    return
                self.wfile.write(_sse_chunk(text))
                self.wfile.flush()
            finish = {"choices": [{"delta": {}, "finish_reason": "stop"}]}
            self.wfile.write(f"data: {json.dumps(finish)}\n\n".encode())
            self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

    return Handler


@pytest.fixture()
def mock_server():
    state = MockState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, state
    finally:
        server.shutdown()
        server.server_close()


def make_adapter(mock_server, **overrides):
    server, _state = mock_server
    port = server.server_address[1]
    return OpenAICompatibleAdapter(
        base_url=overrides.get("base_url", f"http://127.0.0.1:{port}/v1"),
        model=overrides.get("model", "aan-hermes"),
        api_key="sk-test-tidak-asli",
        context_window=overrides.get("context_window", 1000),
    )


@pytest.mark.asyncio()
async def test_streaming_collects_text(mock_server):
    adapter = make_adapter(mock_server)
    deltas = []
    async for delta in adapter.stream(
        [CanonicalMessage(role="user", content="Halo")]
    ):
        deltas.append(delta)
    assert "".join(deltas) == "Halo dunia!"


@pytest.mark.asyncio()
async def test_check_ready(mock_server):
    adapter = make_adapter(mock_server)
    assert await adapter.check_ready() is True


@pytest.mark.asyncio()
async def test_retry_before_first_token(mock_server):
    _server, state = mock_server
    state.fail_first_n = 2
    adapter = make_adapter(mock_server)
    deltas = []
    async for delta in adapter.stream(
        [CanonicalMessage(role="user", content="Halo")]
    ):
        deltas.append(delta)
    assert "".join(deltas) == "Halo dunia!"
    assert state.requests == 3  # 2 failures + 1 success


@pytest.mark.asyncio()
async def test_no_retry_mid_stream(mock_server):
    _server, state = mock_server
    state.fail_mid_stream_after = 1
    adapter = make_adapter(mock_server)
    deltas = []
    with pytest.raises(Exception):
        async for delta in adapter.stream(
            [CanonicalMessage(role="user", content="Halo")]
        ):
            deltas.append(delta)
    # Partial text was received before the failure; only one request made.
    assert "".join(deltas) == "Halo "
    assert state.requests == 1


def test_context_trim_keeps_latest():
    adapter = OpenAICompatibleAdapter(
        base_url="http://127.0.0.1:9/v1", model="aan-hermes",
        api_key="sk-test", context_window=60,
    )
    msgs = [CanonicalMessage(role="system", content="s" * 40)]
    msgs += [CanonicalMessage(role="user", content=f"pesan lama {i} " + "x" * 40)
             for i in range(5)]
    msgs.append(CanonicalMessage(role="user", content="terbaru"))
    kept, truncated = adapter.trim_messages(msgs)
    assert truncated is True
    assert kept[0].role == "system"
    assert kept[-1].content == "terbaru"
    assert len(kept) < len(msgs)


def test_context_no_trim_when_fits():
    adapter = OpenAICompatibleAdapter(
        base_url="http://127.0.0.1:9/v1", model="aan-hermes",
        api_key="sk-test", context_window=1_000_000,
    )
    msgs = [CanonicalMessage(role="user", content="Halo")]
    kept, truncated = adapter.trim_messages(msgs)
    assert truncated is False
    assert kept == msgs
