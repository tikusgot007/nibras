"""UI smoke tests (offscreen): the window builds, dialogs open, and the
markdown renderer produces highlighted code."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nibras.config import DEFAULT_SETTINGS
from nibras.core.agent import AgentCore
from nibras.ui.dialogs import PassphraseDialog, SettingsDialog
from nibras.ui.main_window import MainWindow
from nibras.ui.markdown import render_markdown
from nibras.ui.theme import QSS


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_markdown_renders_code_with_highlight():
    html = render_markdown("# Judul\n\n```python\nprint('halo')\n```\n")
    assert "Judul" in html
    assert "halo" in html
    assert "<pre" in html


def test_main_window_builds_offscreen(qapp, data_dir: Path):
    core = AgentCore(data_dir, api_key="", settings=dict(DEFAULT_SETTINGS))
    saved: list = []
    window = MainWindow(core, dict(DEFAULT_SETTINGS), False,
                        on_settings_saved=lambda *a: saved.append(a),
                        on_safe_close=lambda: None)
    try:
        window.setStyleSheet(QSS)
        window.show()
        qapp.processEvents()
        assert window.isVisible()
        assert window.windowTitle() == "Nibras"
        assert "aan-hermes" in window._status_model.text()
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
