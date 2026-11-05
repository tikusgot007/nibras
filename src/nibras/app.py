"""Application entry point: startup checks, vault unlock, safe shutdown.

Startup order (D-47, D-58, D-59):
1. Resolve the USB root, create the Data/Temp/Backups layout.
2. Take the single-instance lock (D-08). A second instance brings the
   first window forward instead of opening a new one.
3. Write/read/delete probe in Data/ (D-58). On failure, show a clear
   message and stop.
4. Open the databases and run recovery when the last shutdown was not
   clean; show the recovery report.
5. First setup or passphrase unlock for the vault (D-10).
6. Show the chat window immediately; the provider SDK is imported in
   the background by the Agent Core (D-59).

Shutdown order (D-47, D-08): stop tasks, final commit, write
``clean_shutdown``, clean Temp/, release the lock.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from . import config
from .config import DEFAULT_SETTINGS
from .core.agent import AgentCore
from .paths import app_dir, data_dir, ensure_layout, find_usb_root, temp_dir
from .security import vault as vault_mod
from .security.vault import VaultError
from .storage.databases import Databases
from .storage.lock import SingleInstanceLock, write_clean_shutdown
from .storage.recovery import run_recovery
from .ui.dialogs import PassphraseDialog
from .ui.main_window import MainWindow
from .ui.theme import QSS, load_fonts

log = logging.getLogger("nibras")


def setup_logging(data: Path) -> None:
    logs = data / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        logs / "nibras.log", maxBytes=1_000_000, backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    # Never log secrets: only event names are logged, never values.


def probe_data_writable(data: Path) -> bool:
    """Write/read/delete probe in Data/ (D-58)."""
    probe = data / ".nibras-write-test"
    try:
        probe.write_text("ok", encoding="utf-8")
        if probe.read_text(encoding="utf-8") != "ok":
            return False
        probe.unlink()
        return True
    except OSError:
        return False


def bring_existing_to_front() -> bool:
    """Windows only: show the first instance's window. Returns True if
    a window was found and brought forward."""
    if sys.platform != "win32":
        return False
    try:
        import win32con
        import win32gui

        hwnd = win32gui.FindWindow(None, "Nibras")
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return True
    except Exception:  # noqa: BLE001 - best effort only
        pass
    return False


def load_settings(conn) -> dict:
    settings = dict(DEFAULT_SETTINGS)
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    for key, value in rows:
        settings[key] = value
    return settings


class Application:
    def __init__(self, root: Path):
        self.root = root
        self.data = data_dir(root)
        self.temp = temp_dir(root)
        self.dbs: Databases | None = None
        self.lock: SingleInstanceLock | None = None
        self.core: AgentCore | None = None
        self.window: MainWindow | None = None
        self._passphrase: str | None = None
        self._api_key = ""
        self._settings: dict = dict(DEFAULT_SETTINGS)
        self._shutting_down = False

    # -- startup -------------------------------------------------------------
    def run(self, qt_app: QApplication) -> int:
        setup_logging(self.data)
        self.lock = SingleInstanceLock(self.data)
        if not self.lock.acquire():
            if not bring_existing_to_front():
                QMessageBox.information(
                    None, "Nibras",
                    "Nibras sudah berjalan. Jendela yang sudah ada "
                    "ditampilkan kembali.")
            return 0
        if not probe_data_writable(self.data):
            QMessageBox.critical(
                None, "Nibras",
                "Flashdisk tidak bisa ditulisi. Periksa apakah flashdisk "
                "terkunci (write-protect) atau hak aksesnya, lalu coba lagi.")
            self.lock.release()
            return 1

        self.dbs = Databases(self.data).open_all()
        write_clean_shutdown(self.dbs["core.db"], False)
        report = run_recovery(self.dbs, self.temp)
        if not report["clean_shutdown"]:
            self._show_recovery_report(report)
        self._settings = load_settings(self.dbs["core.db"])

        if not self._unlock_vault(qt_app):
            self._shutdown()
            return 0

        self.core = AgentCore(self.data, self._api_key, self._settings)
        self.core.start()
        load_fonts(app_dir(self.root) / "fonts")
        self.window = MainWindow(
            self.core, self._settings, bool(self._api_key),
            on_settings_saved=self._on_settings_saved,
            on_safe_close=self.safe_close,
        )
        self.window.setStyleSheet(QSS)
        self.window.show()
        return qt_app.exec()

    def _show_recovery_report(self, report: dict) -> None:
        lines = ["Nibras mendeteksi sesi sebelumnya tidak ditutup dengan bersih."]
        bad = {k: v for k, v in report["quick_check"].items() if v != "ok"}
        if bad:
            lines.append("Pemeriksaan database menemukan masalah: "
                         + ", ".join(f"{k}={v}" for k, v in bad.items()))
        else:
            lines.append("Pemeriksaan database: semua OK.")
        if report["temp_cleaned"]:
            lines.append("Folder Temp/ sudah dibersihkan.")
        if report["interrupted_messages"]:
            lines.append(
                f"{report['interrupted_messages']} pesan yang sedang di-stream "
                "ditandai terputus (tidak dilanjutkan otomatis).")
        QMessageBox.information(None, "Nibras — Laporan pemulihan",
                                "\n".join(lines))

    def _unlock_vault(self, qt_app: QApplication) -> bool:
        vault_path = self.data / "vault.bin"
        if not vault_mod.vault_exists(vault_path):
            dlg = PassphraseDialog(first_setup=True)
            if not dlg.exec():
                return False
            self._passphrase = dlg.passphrase()
            vault_mod.create_vault(vault_path, self._passphrase, {"api_key": ""})
            self._api_key = ""
            return True
        while True:
            dlg = PassphraseDialog(first_setup=False)
            if not dlg.exec():
                return False
            try:
                payload = vault_mod.open_vault(vault_path, dlg.passphrase())
            except VaultError as exc:
                QMessageBox.warning(None, "Nibras", str(exc))
                continue
            self._passphrase = dlg.passphrase()
            self._api_key = str(payload.get("api_key", ""))
            return True

    # -- settings / unlock callbacks (from the UI) ---------------------------
    def _on_settings_saved(self, kind: str, *args) -> None:
        if kind == "settings":
            _settings, api_key = args
            if api_key and self._passphrase is not None:
                vault_path = self.data / "vault.bin"
                try:
                    payload = vault_mod.open_vault(vault_path, self._passphrase)
                except VaultError:
                    payload = {}
                payload["api_key"] = api_key
                vault_mod.create_vault(vault_path, self._passphrase, payload)
                self._api_key = api_key
            if self.dbs is not None:
                if self.core is not None:
                    self.core.request_audit.emit("settings_saved", "")
        elif kind == "unlock":
            passphrase = args[0]
            vault_path = self.data / "vault.bin"
            try:
                payload = vault_mod.open_vault(vault_path, passphrase)
            except VaultError as exc:
                QMessageBox.warning(None, "Nibras", str(exc))
                return
            self._passphrase = passphrase
            self._api_key = str(payload.get("api_key", ""))
            if self.core is not None:
                self.core.request_update_settings.emit(self._settings, self._api_key)
            if self.window is not None:
                self.window.unlock_vault()

    # -- shutdown --------------------------------------------------------------
    def safe_close(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        if self.window is not None:
            self.window.setEnabled(False)
        self._shutdown()
        QApplication.quit()

    def _shutdown(self) -> None:
        if self.core is not None:
            self.core.stop()
            self.core = None
        if self.dbs is not None:
            try:
                write_clean_shutdown(self.dbs["core.db"], True)
            finally:
                self.dbs.close()
                self.dbs = None
        try:
            for child in self.temp.iterdir():
                if child.is_dir():
                    import shutil

                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
        except OSError:
            pass
        if self.lock is not None:
            self.lock.release()
            self.lock = None


def main(argv: list[str] | None = None) -> int:
    root = ensure_layout(find_usb_root())
    qt_app = QApplication(list(argv or sys.argv))
    qt_app.setApplicationName(config.APP_NAME)
    app = Application(root)
    try:
        return app.run(qt_app)
    except Exception:  # noqa: BLE001 - last-resort: never crash silently
        log.exception("startup gagal")
        QMessageBox.critical(None, "Nibras",
                             "Nibras gagal dijalankan. Lihat Data/logs/nibras.log.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
