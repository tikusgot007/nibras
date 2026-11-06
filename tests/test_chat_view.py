"""Chat view regressions found in operator acceptance testing on the USB stick:
the user's own message was never shown, old answers were cut to one line, and
a first message typed before any conversation existed was never sent."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from nibras.config import (
    DEFAULT_SETTINGS,
    KEY_BASE_URL,
    KEY_CONTEXT_WINDOW,
    KEY_MODEL,
)
from nibras.core.agent import AgentCore
from nibras.ui.chat_view import MessageCard
from nibras.ui.main_window import MainWindow
from tests.test_adapter import mock_server  # noqa: F401  (pytest fixture)
from tests.test_agent_core import wait_until

LONG = "\n\n".join(f"Paragraf {i}: " + "kata " * 60 for i in range(8))


def _doc_height(card: MessageCard) -> int:
    return int(card.browser.document().size().height())


def test_card_height_matches_the_wrapped_document(qapp):
    """A long answer must be fully visible: the card's height follows the
    document wrapped to the REAL width, and follows it when the width changes."""
    card = MessageCard("assistant")
    card.set_text(LONG)  # rendered BEFORE the widget has its final width
    card.resize(700, 100)
    card.show()
    qapp.processEvents()
    wide = card.browser.height()
    assert wide >= _doc_height(card)
    assert wide > 300, "answer collapsed to a line or two"
    assert card.browser.verticalScrollBar().value() == 0  # starts at the top

    card.resize(300, 100)
    qapp.processEvents()
    narrow = card.browser.height()
    assert narrow >= _doc_height(card)
    assert narrow > wide, "narrower width wraps more lines, so the card must grow"


def test_streamed_card_keeps_growing(qapp):
    card = MessageCard("assistant")
    card.resize(700, 100)
    card.show()
    qapp.processEvents()
    heights = []
    for i in range(6):
        card.append_delta(f"Paragraf {i}: " + "kata " * 60 + "\n\n")
        card.finish()  # forces a render regardless of the 10-token batching
        qapp.processEvents()
        heights.append(card.browser.height())
        assert card.browser.height() >= _doc_height(card)
    assert heights == sorted(heights) and heights[-1] > heights[0]


def test_sending_shows_the_users_own_message(qapp, data_dir: Path):
    settings = {**DEFAULT_SETTINGS, KEY_MODEL: "test-model"}
    core = AgentCore(data_dir, api_key="", settings=settings)
    window = MainWindow(core, dict(settings), False,
                        on_settings_saved=lambda *a: None,
                        on_safe_close=lambda: None)
    try:
        window._current_conversation = "c1"
        window._provider_ready = True
        window._input.setPlainText("halo nibras")
        window._send_current()
        users = [c for c in window._chat._cards.values() if c.role == "user"]
        assert [c.text for c in users] == ["halo nibras"]
    finally:
        window.close()
        core.stop()


def test_first_message_without_a_conversation_is_sent_and_shown(
        qapp, data_dir: Path, mock_server):  # noqa: F811
    """No conversation yet: typing + Enter must create one, show the user's
    message, send it once, and show the answer."""
    server, state = mock_server
    port = server.server_address[1]
    settings = {**DEFAULT_SETTINGS, KEY_BASE_URL: f"http://127.0.0.1:{port}/v1",
                KEY_MODEL: "test-model", KEY_CONTEXT_WINDOW: "100000"}
    core = AgentCore(data_dir, "sk-test-tidak-asli", settings)
    ready = []
    core.provider_ready.connect(ready.append)
    core.start()
    window = MainWindow(core, dict(settings), True,
                        on_settings_saved=lambda *a: None,
                        on_safe_close=lambda: None)
    try:
        window.show()
        wait_until(lambda: ready == [True], what="provider_ready")
        QTest.keyClicks(window._input, "pesan pertama")
        QTest.keyClick(window._input, Qt.Key_Return)

        def answered():
            roles = [c.role for c in window._chat._cards.values()]
            return roles == ["user", "assistant"] and not window._streaming

        wait_until(answered, what="user + assistant card")
        cards = list(window._chat._cards.values())
        assert cards[0].text == "pesan pertama"
        assert cards[1].text == "Halo dunia!"

        conn = sqlite3.connect(str(data_dir / "conversations.db"))
        try:
            rows = conn.execute(
                "SELECT role, content FROM messages ORDER BY rowid").fetchall()
        finally:
            conn.close()
        assert rows == [("user", "pesan pertama"), ("assistant", "Halo dunia!")]
        assert state.requests == 1
    finally:
        core.stop()
        window.close()


def _window(data_dir: Path):
    settings = {**DEFAULT_SETTINGS, KEY_MODEL: "test-model"}
    core = AgentCore(data_dir, api_key="", settings=settings)
    window = MainWindow(core, dict(settings), False,
                        on_settings_saved=lambda *a: None,
                        on_safe_close=lambda: None)
    return core, window


def test_reloaded_history_marks_interrupted_cancelled_and_failed(qapp, data_dir: Path):
    """Finding from acceptance item 5: an interrupted answer reloaded from
    history was an empty card with no explanation."""
    core, window = _window(data_dir)
    try:
        window._current_conversation = "c1"
        window._show_messages("c1", [
            {"id": "m1", "role": "user", "content": "halo", "status": "done"},
            {"id": "m2", "role": "assistant", "content": "", "status": "interrupted"},
            {"id": "m3", "role": "assistant", "content": "sebagian", "status": "cancelled"},
            {"id": "m4", "role": "assistant", "content": "x", "status": "failed"},
            {"id": "m5", "role": "assistant", "content": "ok", "status": "done"},
        ])
        label = {mid: window._chat.card(mid)._status.text() for mid in ("m1", "m2", "m3", "m4", "m5")}
        assert label["m1"] == "" and label["m5"] == ""  # normal messages: no mark
        assert "Terputus" in label["m2"] and "tidak dilanjutkan" in label["m2"]
        assert "Dibatalkan" in label["m3"]
        assert "Gagal" in label["m4"]
    finally:
        window.close()
        core.stop()


def test_cancelled_answer_is_marked_when_it_finishes(qapp, data_dir: Path):
    core, window = _window(data_dir)
    try:
        card = window._chat.add_message("m9", "assistant", "setengah")
        window._on_message_finished("m9", "cancelled")
        assert "Dibatalkan" in card._status.text()
    finally:
        window.close()
        core.stop()
