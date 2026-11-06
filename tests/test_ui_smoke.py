"""UI smoke tests (offscreen): the window builds, dialogs open, and the
markdown renderer produces highlighted code."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nibras.config import DEFAULT_SETTINGS, KEY_MODEL
from nibras.core.agent import AgentCore
from nibras.ui.dialogs import PassphraseDialog, SettingsDialog
from nibras.ui.main_window import MainWindow, MessageInput
from nibras.ui.markdown import render_markdown
from nibras.ui.theme import QSS


def test_markdown_renders_code_with_highlight():
    html = render_markdown("# Judul\n\n```python\nprint('halo')\n```\n")
    assert "Judul" in html
    assert "halo" in html
    assert "<pre" in html


def test_main_window_builds_offscreen(qapp, data_dir: Path):
    settings = {**DEFAULT_SETTINGS, KEY_MODEL: "test-model"}
    core = AgentCore(data_dir, api_key="", settings=settings)
    saved: list = []
    window = MainWindow(core, dict(settings), False,
                        on_settings_saved=lambda *a: saved.append(a),
                        on_safe_close=lambda: None)
    try:
        window.setStyleSheet(QSS)
        window.show()
        qapp.processEvents()
        assert window.isVisible()
        assert window.windowTitle() == "Nibras"
        assert "test-model" in window._status_model.text()
    finally:
        window.close()
        core.stop()


def test_settings_dialog_roundtrip(qapp):
    dlg = SettingsDialog(dict(DEFAULT_SETTINGS), api_key_set=False)
    dlg.model.setText("model-lain")
    result = dlg.result_settings()
    assert result["provider.model"] == "model-lain"
    assert result["provider.base_url"] == DEFAULT_SETTINGS["provider.base_url"]


def test_passphrase_dialog_requires_match(qapp, monkeypatch):
    import nibras.ui.dialogs as dialogs_mod

    # QMessageBox.warning is modal and would block headless runs.
    monkeypatch.setattr(dialogs_mod.QMessageBox, "warning",
                        lambda *a, **k: None)
    dlg = PassphraseDialog(first_setup=True)
    dlg.pass1.setText("satu")
    dlg.pass2.setText("dua")
    # _on_ok refuses mismatched passphrases without accepting.
    dlg._on_ok()
    assert dlg.result() == 0
    dlg.pass2.setText("satu")
    dlg._on_ok()
    assert dlg.result() != 0
    assert dlg.passphrase() == "satu"


def test_enter_submits_and_shift_enter_inserts_a_newline(qapp):
    box = MessageInput()
    sent: list[int] = []
    box.submitted.connect(lambda: sent.append(1))
    box.show()
    QTest.keyClicks(box, "halo")
    QTest.keyClick(box, Qt.Key_Return)
    assert sent == [1]
    assert box.toPlainText() == "halo"  # Enter did not add a line break

    QTest.keyClick(box, Qt.Key_Return, Qt.ShiftModifier)
    assert sent == [1]  # Shift+Enter does not send
    assert box.toPlainText() == "halo\n"
    QTest.keyClick(box, Qt.Key_Enter)  # keypad Enter sends too
    assert sent == [1, 1]


def test_pressing_enter_in_the_window_sends_the_message(qapp, data_dir: Path):
    """End to end in the real window: type, press Enter -> the message is
    taken (box cleared, text held because the provider is not ready yet)."""
    settings = {**DEFAULT_SETTINGS, KEY_MODEL: "test-model"}
    core = AgentCore(data_dir, api_key="", settings=settings)
    window = MainWindow(core, dict(settings), False,
                        on_settings_saved=lambda *a: None,
                        on_safe_close=lambda: None)
    try:
        window.show()
        QTest.keyClicks(window._input, "halo nibras")
        QTest.keyClick(window._input, Qt.Key_Return)
        assert window._input.toPlainText() == ""
        assert window._pending_text == "halo nibras"
    finally:
        window.close()
        core.stop()
