"""'Tutup & Aman Dilepas' must END the application.

Bug found on the USB stick: the button ran the whole shutdown (lock released,
clean_shutdown written) but the window stayed on screen, disabled, and the
process never exited. QApplication.quit() first sends a close event to every
window, and MainWindow.closeEvent always ignores it, so the quit was
cancelled by the window itself. These tests run a REAL exec() loop; the
earlier checks pumped events by hand and could not see this.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer

from nibras.app import Application
from nibras.config import (
    DEFAULT_SETTINGS,
    KEY_BASE_URL,
    KEY_CONTEXT_WINDOW,
    KEY_MODEL,
)
from nibras.core.agent import AgentCore
from nibras.storage.lock import SingleInstanceLock, read_clean_shutdown
from nibras.storage.databases import Databases
from nibras.ui.main_window import MainWindow
from tests.test_adapter import mock_server  # noqa: F401  (pytest fixture)

WATCHDOG_RC = 99


def _run_app(qapp, root: Path, mock_server, trigger):
    """Build Application + real window + real Core, run exec(), call
    ``trigger(app)`` from inside the loop, and return (rc, seconds, app)."""
    server, _state = mock_server
    settings = {**DEFAULT_SETTINGS,
                KEY_BASE_URL: f"http://127.0.0.1:{server.server_address[1]}/v1",
                KEY_MODEL: "test-model", KEY_CONTEXT_WINDOW: "100000"}
    app = Application(root)
    app.lock = SingleInstanceLock(app.data)
    assert app.lock.acquire()
    app._prepare_databases()
    app.core = AgentCore(app.data, "sk-test-tidak-asli", settings)
    app.core.start()
    app.window = MainWindow(app.core, settings, True,
                            on_settings_saved=app._on_settings_saved,
                            on_safe_close=app.safe_close)
    app.window.show()
    marks: dict[str, float] = {}

    def fire():
        marks["t"] = time.monotonic()
        trigger(app)

    QTimer.singleShot(300, fire)
    QTimer.singleShot(8000, lambda: qapp.exit(WATCHDOG_RC))  # test must never hang
    rc = qapp.exec()
    return rc, time.monotonic() - marks["t"], app


def _assert_clean(root: Path):
    dbs = Databases(root / "Data").open_all()
    try:
        assert read_clean_shutdown(dbs["core.db"]) is True
    finally:
        dbs.close()
    # lock released: another holder can take it
    other = SingleInstanceLock(root / "Data")
    assert other.acquire() is True
    other.release()


def test_safe_close_button_ends_the_event_loop(qapp, root_dir: Path, mock_server):  # noqa: F811
    rc, took, app = _run_app(qapp, root_dir, mock_server,
                             lambda a: a.window._safe_close_btn.click())
    assert rc == 0, f"exec() did not return on its own (rc={rc}); the app would stay frozen"
    assert took < 3.0
    _assert_clean(root_dir)


def test_closing_the_window_ends_the_event_loop(qapp, root_dir: Path, mock_server):  # noqa: F811
    """The X button goes through closeEvent -> safe shutdown, and must also end."""
    rc, took, app = _run_app(qapp, root_dir, mock_server, lambda a: a.window.close())
    assert rc == 0, f"exec() did not return on its own (rc={rc})"
    assert took < 3.0
    _assert_clean(root_dir)
