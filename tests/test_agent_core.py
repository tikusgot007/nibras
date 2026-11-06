"""Integration tests: the REAL AgentCore (real Core thread, real asyncio loop,
real SQLite files) talking to a local mock OpenAI-compatible server.

These cover the main application path that unit tests missed (review
findings 1, 4, 5, 6): UI -> Core requests actually arrive, tokens come back
as Qt signals, the user's message is stored and sent exactly once, partial
text is saved by time, and a locked Core holds no key.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nibras.config import (
    DEFAULT_SETTINGS,
    KEY_BASE_URL,
    KEY_CONTEXT_WINDOW,
    KEY_MODEL,
)
from nibras.core import agent as agent_mod
from nibras.core.agent import AgentCore
from nibras.storage.databases import Databases
from tests.test_adapter import mock_server  # noqa: F401  (pytest fixture)

API_KEY = "sk-test-tidak-asli-aaa"


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


def wait_until(predicate, timeout=10.0, what="kondisi"):
    """Process Qt events (queued signals from the Core thread) until true."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError(f"timeout menunggu {what}")


class Harness:
    """Starts a real AgentCore against the mock server and records its signals."""

    def __init__(self, data_dir: Path, mock_server, api_key=API_KEY):
        server, self.state = mock_server
        port = server.server_address[1]
        settings = {
            **DEFAULT_SETTINGS,
            KEY_BASE_URL: f"http://127.0.0.1:{port}/v1",
            KEY_MODEL: "test-model",
            KEY_CONTEXT_WINDOW: "100000",
        }
        self.data_dir = data_dir
        self.core = AgentCore(data_dir, api_key=api_key, settings=settings)
        self.tokens: list[tuple[str, str]] = []
        self.finished: list[tuple[str, str]] = []
        self.failed: list[tuple[str, str]] = []
        self.created: list[str] = []
        self.provider: list[bool] = []
        self.locked_signals = 0
        c = self.core
        c.token_received.connect(lambda m, d: self.tokens.append((m, d)))
        c.message_finished.connect(lambda m, s: self.finished.append((m, s)))
        c.message_failed.connect(lambda m, e: self.failed.append((m, e)))
        c.conversation_created.connect(self.created.append)
        c.provider_ready.connect(self.provider.append)
        c.vault_locked.connect(self._on_locked)
        c.start()

    def _on_locked(self):
        self.locked_signals += 1

    def new_conversation(self) -> str:
        n = len(self.created)
        self.core.request_new_conversation.emit()
        wait_until(lambda: len(self.created) > n, what="conversation_created")
        return self.created[-1]

    def send(self, conv_id: str, text: str) -> None:
        n = len(self.finished)
        self.core.request_send.emit(conv_id, text)
        wait_until(lambda: len(self.finished) > n or self.failed,
                   what="message_finished")

    def stop(self):
        self.core.stop()

    def rows(self, sql: str, args=()):
        """Read with a SEPARATE connection (the Core owns its own)."""
        conn = sqlite3.connect(str(self.data_dir / "conversations.db"))
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def audit_events(self) -> list[str]:
        conn = sqlite3.connect(str(self.data_dir / "core.db"))
        try:
            return [r[0] for r in conn.execute("SELECT event FROM audit_log ORDER BY id")]
        finally:
            conn.close()


@pytest.fixture()
def harness(qapp, data_dir: Path, mock_server):  # noqa: F811
    h = Harness(data_dir, mock_server)
    try:
        yield h
    finally:
        h.stop()


def test_requests_reach_core_and_a_full_chat_roundtrip_works(harness: Harness):
    """Finding 1 + 10/11: create a conversation, send a message to the mock
    server, receive tokens on the UI side, and end with the user message
    stored ONCE and the assistant message 'done'."""
    wait_until(lambda: harness.provider == [True], what="provider_ready")
    conv = harness.new_conversation()
    harness.send(conv, "Halo Nibras")

    assert harness.failed == []
    assert "".join(d for _, d in harness.tokens) == "Halo dunia!"
    assert harness.finished[-1][1] == "done"

    rows = harness.rows(
        "SELECT role, content, status FROM messages WHERE conversation_id=? ORDER BY rowid",
        (conv,))
    assert rows == [("user", "Halo Nibras", "done"),
                    ("assistant", "Halo dunia!", "done")]


def test_user_message_is_sent_to_provider_exactly_once(harness: Harness):
    """Finding 4: the user message must not be duplicated in the context."""
    wait_until(lambda: harness.provider == [True], what="provider_ready")
    conv = harness.new_conversation()
    harness.send(conv, "pesan pertama")
    sent = harness.state.last_body["messages"]
    assert [m for m in sent if m["content"] == "pesan pertama"] == [
        {"role": "user", "content": "pesan pertama"}]
    assert len(sent) == 1

    harness.send(conv, "pesan kedua")
    sent = harness.state.last_body["messages"]
    assert [(m["role"], m["content"]) for m in sent] == [
        ("user", "pesan pertama"),
        ("assistant", "Halo dunia!"),
        ("user", "pesan kedua"),
    ]


def test_partial_text_is_saved_by_time_while_streaming(
        qapp, data_dir: Path, mock_server, monkeypatch):  # noqa: F811
    """Finding 6: a half-finished answer is flushed on a timer, not on a
    character-count coincidence, so pulling the stick loses little text."""
    monkeypatch.setattr(agent_mod, "PARTIAL_SAVE_SECONDS", 0.05)
    _server, state = mock_server
    state.chunk_delay = 0.5
    h = Harness(data_dir, mock_server)
    try:
        wait_until(lambda: h.provider == [True], what="provider_ready")
        conv = h.new_conversation()
        h.core.request_send.emit(conv, "tulis panjang")

        def partial_on_disk() -> bool:
            rows = h.rows(
                "SELECT content, status FROM messages "
                "WHERE conversation_id=? AND role='assistant'", (conv,))
            return bool(rows) and rows[0][1] == "streaming" and rows[0][0] != ""

        # While the stream is still running (3 chunks, 0.5 s apart) the
        # partial text must show up on disk.
        wait_until(lambda: partial_on_disk() or h.finished, timeout=10,
                   what="teks parsial di disk")
        assert not h.finished, "stream selesai sebelum teks parsial pernah tersimpan"
        wait_until(lambda: h.finished, what="message_finished")
        assert h.finished[-1][1] == "done"
    finally:
        h.stop()


def test_cancel_stops_streaming_and_keeps_partial_text(
        qapp, data_dir: Path, mock_server):  # noqa: F811
    """D-44: Batalkan reaches the Core, the answer is marked cancelled and
    the text received so far is kept."""
    _server, state = mock_server
    state.chunk_delay = 0.4
    h = Harness(data_dir, mock_server)
    try:
        wait_until(lambda: h.provider == [True], what="provider_ready")
        conv = h.new_conversation()
        h.core.request_send.emit(conv, "tulis panjang")
        wait_until(lambda: len(h.tokens) >= 1, what="token pertama")
        h.core.request_cancel.emit()
        wait_until(lambda: h.finished, what="message_finished")
        assert h.finished[-1][1] == "cancelled"
        rows = h.rows("SELECT content, status FROM messages "
                      "WHERE conversation_id=? AND role='assistant'", (conv,))
        assert rows[0][1] == "cancelled" and rows[0][0].startswith("Halo")
    finally:
        h.stop()


def test_locking_the_core_drops_the_key_and_unlock_rebuilds_the_adapter(
        harness: Harness):
    """Finding 5: a locked Core holds no key and no adapter, refuses to send,
    logs lock and unlock, and works again with the new key after unlock."""
    wait_until(lambda: harness.provider == [True], what="provider_ready")
    conv = harness.new_conversation()

    harness.core.request_lock_vault.emit()
    wait_until(lambda: harness.locked_signals == 1, what="vault_locked")
    assert harness.core._api_key == ""
    assert harness.core._adapter is None

    # Sending while locked: nothing is sent, nothing is stored, the UI is told.
    harness.core.request_send.emit(conv, "ditahan")
    wait_until(lambda: harness.locked_signals == 2, what="vault_locked kedua")
    assert harness.state.requests == 0
    assert harness.rows("SELECT count(*) FROM messages")[0][0] == 0

    harness.core.request_unlock.emit("sk-kunci-baru-tes")
    wait_until(lambda: harness.provider.count(True) == 2, what="provider_ready ulang")
    harness.send(conv, "sesudah unlock")
    assert harness.failed == []
    assert harness.state.last_auth == "Bearer sk-kunci-baru-tes"

    events = harness.audit_events()
    assert "vault_lock" in events and "vault_unlock" in events
    assert events.index("vault_lock") < events.index("vault_unlock")


def test_unconfigured_provider_gives_a_clear_message_not_a_request(
        qapp, data_dir: Path, mock_server):  # noqa: F811
    """Public repo: no default URL/model, so an unconfigured provider must be
    reported to the user and nothing may be sent anywhere."""
    h = Harness(data_dir, mock_server)
    try:
        wait_until(lambda: h.provider == [True], what="provider_ready")
        h.core.request_update_settings.emit({KEY_BASE_URL: "", KEY_MODEL: ""}, "")
        conv = h.new_conversation()
        h.core.request_send.emit(conv, "halo")
        wait_until(lambda: h.failed, what="message_failed")
        assert "Pengaturan" in h.failed[-1][1]
        assert h.state.requests == 0
    finally:
        h.stop()


def test_databases_are_opened_in_the_core_thread(harness: Harness):
    """SQLite connections are tied to their creating thread. The Core opened
    its own, so a connection used here from the test thread must be refused."""
    wait_until(lambda: harness.provider == [True], what="provider_ready")
    conn = harness.core._dbs["conversations.db"]
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")  # wrong thread -> proves it belongs to the Core thread
