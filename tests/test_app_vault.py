"""Vault lifecycle in the Application (D-09, D-10, D-39, D-40): the app keeps
only the DERIVED KEY while the vault is open, wipes it on lock, rebuilds the
Core's adapter on unlock, and saves settings without re-running Argon2."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import nibras.app as app_mod
from nibras.app import Application
from nibras.config import DEFAULT_SETTINGS, KEY_BASE_URL, KEY_CONTEXT_WINDOW, KEY_MODEL
from nibras.core.agent import AgentCore
from nibras.security import vault as vault_mod
from nibras.ui.main_window import MainWindow
from tests.test_adapter import mock_server  # noqa: F401  (pytest fixture)
from tests.test_agent_core import wait_until

FAST = {"time_cost": 1, "memory_cost": 1024, "lanes": 1}
PASSPHRASE = "passphrase-uji-tidak-asli"
API_KEY = "sk-test-tidak-asli-bbb"


class FakeSignal:
    def __init__(self):
        self.calls: list[tuple] = []

    def emit(self, *args):
        self.calls.append(args)


class FakeCore:
    def __init__(self):
        self.request_unlock = FakeSignal()
        self.request_audit = FakeSignal()
        self.request_lock_vault = FakeSignal()


class FakeWindow:
    def __init__(self):
        self.unlocked = 0

    def unlock_vault(self):
        self.unlocked += 1


@pytest.fixture()
def app_with_vault(root_dir: Path, monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(app_mod.QMessageBox, "warning",
                        lambda *a, **k: warnings.append(a[2]))
    app = Application(root_dir)
    path = app.data / "vault.bin"
    vault_mod.create_vault(path, PASSPHRASE, {"api_key": API_KEY}, params=FAST)
    app._session, _ = vault_mod.unlock_vault(path, PASSPHRASE)
    app.warnings = warnings
    return app


def test_application_never_stores_the_passphrase(app_with_vault: Application):
    assert not hasattr(app_with_vault, "_passphrase")
    assert app_with_vault._session.is_open


def test_lock_wipes_the_derived_key_and_drops_key_copies(app_with_vault: Application):
    app = app_with_vault
    held = app._session._key  # the exact buffer
    app._api_key = "sisa-kunci"
    assert any(held)
    app._on_settings_saved("lock")
    assert not any(held)  # zeroed in place
    assert app._session is None
    assert app._api_key == ""


def test_saving_a_new_api_key_does_not_run_argon2(app_with_vault: Application,
                                                  monkeypatch):
    app = app_with_vault

    def boom(*a, **k):
        raise AssertionError("Argon2 must not run when saving settings")

    monkeypatch.setattr(vault_mod, "_derive_key", boom)
    monkeypatch.setattr(vault_mod, "calibrate_argon2", boom)
    app._on_settings_saved("settings", {}, "sk-kunci-baru-tes")
    path = app.data / "vault.bin"
    assert vault_mod.read_with_session(path, app._session) == {"api_key": "sk-kunci-baru-tes"}
    assert app.warnings == []


def test_saving_a_new_api_key_while_locked_is_refused(app_with_vault: Application):
    app = app_with_vault
    app._on_settings_saved("lock")
    app._on_settings_saved("settings", {}, "sk-tidak-boleh-tersimpan")
    assert any("terkunci" in w for w in app.warnings)
    # the vault still holds the original key
    _s, payload = vault_mod.unlock_vault(app.data / "vault.bin", PASSPHRASE)
    assert payload == {"api_key": API_KEY}


def test_unlock_hands_the_key_to_the_core_and_reopens_the_window(
        app_with_vault: Application):
    app = app_with_vault
    app._on_settings_saved("lock")
    app.core, app.window = FakeCore(), FakeWindow()
    app._on_settings_saved("unlock", PASSPHRASE)
    assert app.core.request_unlock.calls == [(API_KEY,)]
    assert app.window.unlocked == 1
    assert app._session is not None and app._session.is_open
    assert app._api_key == ""  # the app does not keep the key itself


def test_wrong_passphrase_keeps_everything_locked(app_with_vault: Application):
    app = app_with_vault
    app._on_settings_saved("lock")
    app.core, app.window = FakeCore(), FakeWindow()
    app._on_settings_saved("unlock", "salah-total")
    assert app.core.request_unlock.calls == []
    assert app.window.unlocked == 0
    assert app._session is None
    assert any("salah" in w.lower() for w in app.warnings)


def test_window_lock_reaches_application_and_core(
        qapp, root_dir: Path, mock_server, monkeypatch):  # noqa: F811
    """End to end: the window's auto-lock wipes the Application's key AND
    drops the real Core's key/adapter, and the unlock restores sending."""
    monkeypatch.setattr(app_mod.QMessageBox, "warning", lambda *a, **k: None)
    server, state = mock_server
    port = server.server_address[1]
    settings = {**DEFAULT_SETTINGS, KEY_BASE_URL: f"http://127.0.0.1:{port}/v1",
                KEY_MODEL: "test-model", KEY_CONTEXT_WINDOW: "100000"}
    app = Application(root_dir)
    path = app.data / "vault.bin"
    vault_mod.create_vault(path, PASSPHRASE, {"api_key": API_KEY}, params=FAST)
    app._session, _ = vault_mod.unlock_vault(path, PASSPHRASE)

    core = AgentCore(app.data, API_KEY, settings)
    core.start()
    app.core = core
    window = MainWindow(core, settings, True,
                        on_settings_saved=app._on_settings_saved,
                        on_safe_close=lambda: None)
    app.window = window
    try:
        provider, locked = [], []
        core.provider_ready.connect(provider.append)
        core.vault_locked.connect(lambda: locked.append(1))
        wait_until(lambda: provider == [True], what="provider_ready")

        held = app._session._key
        window._lock_vault()
        wait_until(lambda: core._adapter is None and locked, what="Core terkunci")
        assert not any(held) and app._session is None
        assert core._api_key == ""

        app._on_settings_saved("unlock", PASSPHRASE)
        wait_until(lambda: core._adapter is not None, what="adapter dibuat ulang")
        assert core._api_key == API_KEY
        assert not window._vault_locked
    finally:
        core.stop()
        window.close()
