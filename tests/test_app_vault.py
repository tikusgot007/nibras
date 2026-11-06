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
from nibras.storage.databases import Databases
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


def test_application_unlock_with_multiple_profile_keys_and_no_cross_fallback(
        qapp, root_dir: Path, monkeypatch):
    """Review finding 1 & 2 & 5: Application sends dict of profile keys on unlock,
    each profile receives only its own key, and unconfigured profile gets empty string."""
    monkeypatch.setattr(app_mod.QMessageBox, "warning", lambda *a, **k: None)
    app = Application(root_dir)
    dbs = Databases(app.data).open_all()
    conn = dbs["core.db"]
    from nibras.storage.profiles import create_profile, create_model, set_active_model
    p1 = create_profile(conn, kind="openai_compatible", name="P1", base_url="http://127.0.0.1:8001/v1")
    m1 = create_model(conn, profile_id=p1["id"], name="m1")
    p2 = create_profile(conn, kind="openai_compatible", name="P2", base_url="http://127.0.0.1:8002/v1")
    m2 = create_model(conn, profile_id=p2["id"], name="m2")
    p3 = create_profile(conn, kind="openai_compatible", name="P3", base_url="http://127.0.0.1:8003/v1")
    m3 = create_model(conn, profile_id=p3["id"], name="m3")
    set_active_model(conn, m1["id"])
    dbs.close()

    path = app.data / "vault.bin"
    payload = {
        "api_keys": {
            p1["id"]: "KEY-PROFIL-1",
            p2["id"]: "KEY-PROFIL-2",
        }
    }
    vault_mod.create_vault(path, PASSPHRASE, payload, params=FAST)
    app._session, app._vault_payload = vault_mod.unlock_vault(path, PASSPHRASE)

    # Core constructed the same way as app.py (keyword args, passing api_keys)
    core = AgentCore(app.data, settings=DEFAULT_SETTINGS, api_keys=app._vault_payload.get("api_keys"))
    core.start()
    app.core = core
    try:
        # Check keys in core
        assert core._get_api_key_for_profile(p1["id"]) == "KEY-PROFIL-1"
        assert core._get_api_key_for_profile(p2["id"]) == "KEY-PROFIL-2"
        # Profile without key MUST be empty string, never a fallback to other keys or dict
        assert core._get_api_key_for_profile(p3["id"]) == ""
        assert app.has_api_key(p1["id"]) is True
        assert app.has_api_key(p2["id"]) is True
        assert app.has_api_key(p3["id"]) is False

        # Active adapter for p1 has KEY-PROFIL-1
        assert core._adapter is not None
        assert core._adapter.api_key == "KEY-PROFIL-1"

        # Switch to p2
        core.request_set_active_model.emit(m2["id"])
        wait_until(lambda: core._adapter is not None and core._adapter.api_key == "KEY-PROFIL-2", what="p2 active")
        assert core._adapter.api_key == "KEY-PROFIL-2"

        # Switch to p3 (no key)
        core.request_set_active_model.emit(m3["id"])
        wait_until(lambda: core._adapter is not None and core._adapter.api_key == "", what="p3 active")
        assert core._adapter.api_key == ""

        # Lock and unlock via application
        core.request_lock_vault.emit()
        app._on_settings_saved("lock")
        wait_until(lambda: core._locked is True, what="core locked")

        app._on_settings_saved("unlock", PASSPHRASE)
        wait_until(lambda: core._locked is False, what="core unlocked")
        assert core._get_api_key_for_profile(p1["id"]) == "KEY-PROFIL-1"
        assert core._get_api_key_for_profile(p2["id"]) == "KEY-PROFIL-2"
        assert core._get_api_key_for_profile(p3["id"]) == ""
    finally:
        core.stop()

