"""Settings dialog (brief item 11) and passphrase dialogs (D-10).

The API key field is a password input. The key is never displayed back
in plain text and never written anywhere except the vault, by the caller.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import (
    DEFAULT_AUTO_LOCK_MINUTES,
    DEFAULT_BASE_URL,
    DEFAULT_CONTEXT_WINDOW,
    DEFAULT_MODEL,
    KEY_AUTO_LOCK_MINUTES,
    KEY_BASE_URL,
    KEY_CONTEXT_WINDOW,
    KEY_MODEL,
)


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, api_key_set: bool,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Pengaturan")
        self._api_key = ""
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.base_url = QLineEdit(settings.get(KEY_BASE_URL, DEFAULT_BASE_URL))
        form.addRow("Base URL provider:", self.base_url)
        self.model = QLineEdit(settings.get(KEY_MODEL, DEFAULT_MODEL))
        form.addRow("Nama model:", self.model)
        self.context_window = QSpinBox()
        self.context_window.setRange(1024, 2_000_000)
        self.context_window.setValue(int(settings.get(
            KEY_CONTEXT_WINDOW, DEFAULT_CONTEXT_WINDOW)))
        form.addRow("Context window (token):", self.context_window)
        self.auto_lock = QSpinBox()
        self.auto_lock.setRange(1, 480)
        self.auto_lock.setValue(int(settings.get(
            KEY_AUTO_LOCK_MINUTES, DEFAULT_AUTO_LOCK_MINUTES)))
        form.addRow("Auto-lock vault (menit idle):", self.auto_lock)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText(
            "Sudah tersimpan di vault" if api_key_set
            else "Masukkan API key"
        )
        form.addRow("API key:", self.api_key)
        layout.addLayout(form)
        layout.addWidget(QLabel(
            "API key hanya tersimpan di vault di flashdisk, tidak pernah "
            "ditampilkan atau dicatat di mana pun."))
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_settings(self) -> dict:
        return {
            KEY_BASE_URL: self.base_url.text().strip(),
            KEY_MODEL: self.model.text().strip(),
            KEY_CONTEXT_WINDOW: str(self.context_window.value()),
            KEY_AUTO_LOCK_MINUTES: str(self.auto_lock.value()),
        }

    def result_api_key(self) -> str:
        return self.api_key.text()


class PassphraseDialog(QDialog):
    """Unlock vault (once) or first setup (twice, with the no-recovery
    warning from D-10)."""

    def __init__(self, first_setup: bool, parent: QWidget | None = None):
        super().__init__(parent)
        self._first_setup = first_setup
        self.setWindowTitle(
            "Buat passphrase brankas" if first_setup else "Buka brankas")
        layout = QVBoxLayout(self)
        if first_setup:
            layout.addWidget(QLabel(
                "Buat passphrase untuk brankas API key.\n\n"
                "PENTING: tidak ada cara memulihkan passphrase yang lupa. "
                "Kalau lupa, API key di dalam brankas tidak bisa dibuka lagi "
                "dan harus dimasukkan ulang dari awal."))
        else:
            layout.addWidget(QLabel("Masukkan passphrase brankas:"))
        form = QFormLayout()
        self.pass1 = QLineEdit()
        self.pass1.setEchoMode(QLineEdit.Password)
        form.addRow("Passphrase:", self.pass1)
        self.pass2 = QLineEdit()
        self.pass2.setEchoMode(QLineEdit.Password)
        if first_setup:
            form.addRow("Ulangi passphrase:", self.pass2)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        if not self.pass1.text():
            QMessageBox.warning(self, "Nibras", "Passphrase tidak boleh kosong.")
            return
        if self._first_setup and self.pass1.text() != self.pass2.text():
            QMessageBox.warning(
                self, "Nibras", "Passphrase tidak sama. Ulangi lagi.")
            return
        self.accept()

    def passphrase(self) -> str:
        return self.pass1.text()
