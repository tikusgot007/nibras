"""Tests for AgentCore fallback workflow and profile management (D-64, D-15, D-59)."""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from nibras.config import DEFAULT_SETTINGS
from nibras.core.agent import AgentCore
from nibras.storage.databases import Databases
from nibras.storage.profiles import (
    create_model,
    create_profile,
    set_active_model,
    set_fallback_model,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def wait_until(predicate, timeout=10.0, what="kondisi"):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError(f"Timeout menunggu {what}")


class ServerState:
    def __init__(self, mode="ok", response_text="Halo dunia!"):
        self.mode = mode
        self.response_text = response_text
        self.requests = 0


def make_mock_handler(state: ServerState):
    class Handler(BaseHTTPRequestHandler):
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
                self._send_json(200, {"data": [{"id": "model-1"}]})
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self):
            state.requests += 1
            if state.mode == "fail":
                self._send_json(500, {"error": {"message": "primary boom"}})
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()

            payload = {"choices": [{"delta": {"content": state.response_text}, "finish_reason": None}]}
            self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode())
            finish = {"choices": [{"delta": {}, "finish_reason": "stop"}]}
            self.wfile.write(f"data: {json.dumps(finish)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            self.close_connection = True

    return Handler


@pytest.fixture()
def twin_servers():
    s1_state = ServerState(mode="fail")
    s2_state = ServerState(mode="ok", response_text="Halo dari fallback!")

    srv1 = ThreadingHTTPServer(("127.0.0.1", 0), make_mock_handler(s1_state))
    srv2 = ThreadingHTTPServer(("127.0.0.1", 0), make_mock_handler(s2_state))
    srv1.daemon_threads = True
    srv2.daemon_threads = True

    t1 = threading.Thread(target=srv1.serve_forever, daemon=True)
    t2 = threading.Thread(target=srv2.serve_forever, daemon=True)
    t1.start()
    t2.start()

    try:
        yield (srv1, s1_state), (srv2, s2_state)
    finally:
        srv1.shutdown()
        srv1.server_close()
        srv2.shutdown()
        srv2.server_close()


def test_fallback_approval_and_single_message_rule(qapp, data_dir: Path, twin_servers):
    (srv1, state1), (srv2, state2) = twin_servers
    p1_port = srv1.server_address[1]
    p2_port = srv2.server_address[1]

    # Setup database with 2 profiles: 1 active (failing), 1 fallback (working)
    dbs = Databases(data_dir).open_all()
    conn = dbs["core.db"]
    prof1 = create_profile(conn, kind="openai_compatible", name="Primary Fails", base_url=f"http://127.0.0.1:{p1_port}/v1")
    mod1 = create_model(conn, profile_id=prof1["id"], name="primary-m")

    prof2 = create_profile(conn, kind="openai_compatible", name="Secondary Works", base_url=f"http://127.0.0.1:{p2_port}/v1")
    mod2 = create_model(conn, profile_id=prof2["id"], name="fallback-m")

    set_active_model(conn, mod1["id"])
    set_fallback_model(conn, mod2["id"])
    dbs.close()

    api_keys = {
        prof1["id"]: "sk-primary-key",
        prof2["id"]: "sk-fallback-key",
    }

    core = AgentCore(data_dir, api_keys=api_keys, settings=DEFAULT_SETTINGS)

    tokens: list[tuple[str, str]] = []
    finished: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []
    fallback_offers: list[tuple[str, str, str]] = []
    created_convs: list[str] = []

    core.token_received.connect(lambda m, d: tokens.append((m, d)))
    core.message_finished.connect(lambda m, s: finished.append((m, s)))
    core.message_failed.connect(lambda m, e: failed.append((m, e)))
    core.fallback_offered.connect(lambda m, p, mod: fallback_offers.append((m, p, mod)))
    core.conversation_created.connect(lambda c: created_convs.append(c))

    core.start()
    try:
        # Create conversation
        core.request_new_conversation.emit()
        wait_until(lambda: len(created_convs) > 0, what="conversation_created")
        conv_id = created_convs[0]

        # Send message to primary
        core.request_send.emit(conv_id, "Halo bot")

        # Expect fallback offered (after primary retries and fails)
        wait_until(lambda: len(fallback_offers) == 1, timeout=10.0, what="fallback_offered")
        msg_id, off_prof, _ = fallback_offers[0]
        assert "Secondary Works" in off_prof
        assert state1.requests > 0
        assert len(finished) == 0

        # Approve fallback
        core.request_send_fallback.emit(msg_id)

        # Expect stream from fallback server to complete
        wait_until(lambda: len(finished) == 1, timeout=10.0, what="message_finished via fallback")
        assert finished[0][0] == msg_id
        assert state2.requests >= 1
        assert "".join(d for _, d in tokens) == "Halo dari fallback!"

        # D-64 verification: Next message sent MUST use the active provider (primary),
        # not the fallback provider, because fallback is strictly single-message!
        tokens.clear()
        fallback_offers.clear()
        finished.clear()
        failed.clear()

        core.request_send.emit(conv_id, "Pesan kedua")
        # Should fail on primary again and offer fallback again
        wait_until(lambda: len(fallback_offers) == 1, timeout=10.0, what="second fallback_offered")
        assert "Secondary Works" in fallback_offers[0][1]

    finally:
        core.stop()


def test_fallback_rejection(qapp, data_dir: Path, twin_servers):
    (srv1, _), (srv2, _) = twin_servers
    p1_port = srv1.server_address[1]
    p2_port = srv2.server_address[1]

    dbs = Databases(data_dir).open_all()
    conn = dbs["core.db"]
    prof1 = create_profile(conn, kind="openai_compatible", name="Primary Fails", base_url=f"http://127.0.0.1:{p1_port}/v1")
    mod1 = create_model(conn, profile_id=prof1["id"], name="primary-m")

    prof2 = create_profile(conn, kind="openai_compatible", name="Secondary Works", base_url=f"http://127.0.0.1:{p2_port}/v1")
    mod2 = create_model(conn, profile_id=prof2["id"], name="fallback-m")

    set_active_model(conn, mod1["id"])
    set_fallback_model(conn, mod2["id"])
    dbs.close()

    api_keys = {prof1["id"]: "k1", prof2["id"]: "k2"}
    core = AgentCore(data_dir, api_keys=api_keys, settings=DEFAULT_SETTINGS)

    failed: list[tuple[str, str]] = []
    finished: list[tuple[str, str]] = []
    fallback_offers: list[tuple[str, str, str]] = []
    created_convs: list[str] = []

    core.message_failed.connect(lambda m, e: failed.append((m, e)))
    core.message_finished.connect(lambda m, s: finished.append((m, s)))
    core.fallback_offered.connect(lambda m, p, mod: fallback_offers.append((m, p, mod)))
    core.conversation_created.connect(lambda c: created_convs.append(c))

    core.start()
    try:
        core.request_new_conversation.emit()
        wait_until(lambda: len(created_convs) > 0, what="conversation_created")
        conv_id = created_convs[0]

        core.request_send.emit(conv_id, "Halo")
        wait_until(lambda: len(fallback_offers) == 1, timeout=10.0, what="fallback_offered")
        msg_id, _, _ = fallback_offers[0]

        # Operator rejects fallback
        core.request_reject_fallback.emit(msg_id)

        # Message finishes with status failed
        wait_until(lambda: len(finished) == 1, timeout=5.0, what="message_finished on reject")
        assert finished[0] == (msg_id, "failed")

    finally:
        core.stop()
