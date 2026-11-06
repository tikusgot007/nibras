"""Tests for OpenAI and Anthropic adapters with local mock servers (D-15, D-21, D-59)."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from nibras.core.messages import CanonicalMessage
from nibras.providers.anthropic import AnthropicAdapter
from nibras.providers.openai import OpenAIAdapter


class MockOpenAIState:
    def __init__(self):
        self.requests = 0
        self.fail_first_n = 0
        self.last_body: dict | None = None
        self.last_auth: str | None = None


def make_openai_handler(state: MockOpenAIState):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
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
                self._send_json(200, {"data": [{"id": "test-model"}]})
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            state.last_body = json.loads(self.rfile.read(length) or b"{}")
            state.last_auth = self.headers.get("Authorization")
            state.requests += 1

            if state.requests <= state.fail_first_n:
                self._send_json(500, {"error": {"message": "boom"}})
                return

            if self.path == "/v1/chat/completions":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                for chunk in ["Halo ", "dunia!"]:
                    payload = {"choices": [{"delta": {"content": chunk}, "finish_reason": None}]}
                    self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode())
                    self.wfile.flush()

                finish = {"choices": [{"delta": {}, "finish_reason": "stop"}]}
                self.wfile.write(f"data: {json.dumps(finish)}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            else:
                self._send_json(404, {"error": "not found"})

    return Handler


@pytest.fixture()
def mock_openai_server():
    state = MockOpenAIState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_openai_handler(state))
    server.daemon_threads = True
    import threading
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        yield server, state
    finally:
        server.shutdown()
        server.server_close()


class MockAnthropicState:
    def __init__(self):
        self.requests = 0
        self.fail_first_n = 0
        self.last_body: dict | None = None
        self.last_auth: str | None = None


def make_anthropic_handler(state: MockAnthropicState):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
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
                self._send_json(200, {"data": [{"id": "claude-3-5-sonnet"}]})
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            state.last_body = json.loads(self.rfile.read(length) or b"{}")
            state.last_auth = self.headers.get("x-api-key") or self.headers.get("Authorization")
            state.requests += 1

            if state.requests <= state.fail_first_n:
                self._send_json(500, {"type": "error", "error": {"type": "api_error", "message": "server boom"}})
                return

            if self.path == "/v1/messages":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()

                # Anthropic message streaming events
                events = [
                    (
                        "message_start",
                        {
                            "type": "message_start",
                            "message": {
                                "id": "msg_1",
                                "type": "message",
                                "role": "assistant",
                                "content": [],
                                "model": "claude-3-5-sonnet",
                                "stop_reason": None,
                                "usage": {"input_tokens": 10, "output_tokens": 1},
                            },
                        },
                    ),
                    ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
                    ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Halo "}}),
                    ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Claude!"}}),
                    ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                    (
                        "message_delta",
                        {
                            "type": "message_delta",
                            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                            "usage": {"output_tokens": 5},
                        },
                    ),
                    ("message_stop", {"type": "message_stop"}),
                ]
                for ev_name, ev_data in events:
                    self.wfile.write(f"event: {ev_name}\ndata: {json.dumps(ev_data)}\n\n".encode())
                    self.wfile.flush()
                self.close_connection = True
            else:
                self._send_json(404, {"error": "not found"})

    return Handler


@pytest.fixture()
def mock_anthropic_server():
    state = MockAnthropicState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_anthropic_handler(state))
    server.daemon_threads = True
    import threading
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        yield server, state
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.asyncio
async def test_openai_adapter_streaming(mock_openai_server):
    server, state = mock_openai_server
    port = server.server_address[1]
    adapter = OpenAIAdapter(
        base_url=f"http://127.0.0.1:{port}/v1",
        model="test-model",
        api_key="sk-test-openai",
        context_window=100000,
    )
    assert await adapter.check_ready() is True
    chunks = []
    messages = [
        CanonicalMessage(role="system", content="Kamu ramah"),
        CanonicalMessage(role="user", content="Halo"),
    ]
    async for delta in adapter.stream(messages):
        chunks.append(delta)
    assert "".join(chunks) == "Halo dunia!"
    assert state.last_auth == "Bearer sk-test-openai"


@pytest.mark.asyncio
async def test_openai_adapter_retries_before_first_token(mock_openai_server):
    server, state = mock_openai_server
    port = server.server_address[1]
    state.fail_first_n = 2  # Fails twice, succeeds on 3rd attempt
    adapter = OpenAIAdapter(
        base_url=f"http://127.0.0.1:{port}/v1",
        model="test-model",
        api_key="sk-test",
        context_window=100000,
    )
    chunks = []
    async for delta in adapter.stream([CanonicalMessage(role="user", content="Hi")]):
        chunks.append(delta)
    assert "".join(chunks) == "Halo dunia!"
    assert state.requests == 3


@pytest.mark.asyncio
async def test_anthropic_adapter_streaming(mock_anthropic_server):
    server, state = mock_anthropic_server
    port = server.server_address[1]
    adapter = AnthropicAdapter(
        base_url=f"http://127.0.0.1:{port}",
        model="claude-3-5-sonnet",
        api_key="sk-ant-test",
        context_window=200000,
    )
    assert await adapter.check_ready() is True
    chunks = []
    messages = [
        CanonicalMessage(role="system", content="Kamu asisten Nibras"),
        CanonicalMessage(role="user", content="Halo Claude"),
    ]
    async for delta in adapter.stream(messages):
        chunks.append(delta)
    assert "".join(chunks) == "Halo Claude!"
    assert "sk-ant-test" in (state.last_auth or "")
    # System prompt separated
    assert state.last_body.get("system") == "Kamu asisten Nibras"
    assert state.last_body.get("messages") == [{"role": "user", "content": "Halo Claude"}]


@pytest.mark.asyncio
async def test_anthropic_adapter_retries_before_first_token(mock_anthropic_server):
    server, state = mock_anthropic_server
    port = server.server_address[1]
    state.fail_first_n = 2
    adapter = AnthropicAdapter(
        base_url=f"http://127.0.0.1:{port}",
        model="claude-3-5-sonnet",
        api_key="sk-ant-test",
        context_window=200000,
    )
    chunks = []
    async for delta in adapter.stream([CanonicalMessage(role="user", content="Hi")]):
        chunks.append(delta)
    assert "".join(chunks) == "Halo Claude!"
    assert state.requests == 3


def test_lazy_import_anthropic_not_loaded_on_openai_start():
    """Verify D-59: anthropic is not imported when provider is not Anthropic."""
    code = """
import sys
from pathlib import Path
from nibras.core.agent import AgentCore
from nibras.config import DEFAULT_SETTINGS

data_dir = Path(sys.argv[1])
settings = {
    **DEFAULT_SETTINGS,
    "provider.base_url": "http://127.0.0.1:9999/v1",
    "provider.model": "test-openai",
}
core = AgentCore(data_dir, api_key="test-key", settings=settings)
core.start()
try:
    assert "anthropic" not in sys.modules, "anthropic should not be imported!"
    print("SUCCESS")
finally:
    core.stop()
"""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        env["PYTHONPATH"] = "src"
        res = subprocess.run(
            [sys.executable, "-c", code, tmp],
            capture_output=True,
            text=True,
            env=env,
        )
        assert res.returncode == 0, f"Error: {res.stderr}\n{res.stdout}"
        assert "SUCCESS" in res.stdout
