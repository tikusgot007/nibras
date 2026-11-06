"""Settings dialog (brief item 11) and passphrase dialogs (D-10).

The API key field is a password input. The key is never displayed back
in plain text and never written anywhere except the vault, by the caller.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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


class ProfileEditDialog(QDialog):
    """Add or edit a provider profile (D-15)."""

    KINDS = [
        ("openai", "OpenAI Official"),
        ("anthropic", "Anthropic"),
        ("openai_compatible", "OpenAI-Compatible"),
    ]

    def __init__(
        self,
        profile: dict | None = None,
        has_api_key: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.profile = profile or {}
        is_edit = bool(profile and profile.get("id"))
        self.setWindowTitle("Edit Profil Provider" if is_edit else "Tambah Profil Provider")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.kind_combo = QComboBox()
        for k_val, k_label in self.KINDS:
            self.kind_combo.addItem(k_label, k_val)
        if profile and profile.get("kind"):
            idx = self.kind_combo.findData(profile["kind"])
            if idx >= 0:
                self.kind_combo.setCurrentIndex(idx)
        if is_edit:
            self.kind_combo.setEnabled(False)  # kind is fixed once created
        form.addRow("Jenis Provider:", self.kind_combo)

        self.name_edit = QLineEdit(profile.get("name", "") if profile else "")
        self.name_edit.setPlaceholderText("Contoh: OpenAI Kantor, Claude Pribadi, Ollama")
        form.addRow("Nama Tampilan:", self.name_edit)

        self.base_url_edit = QLineEdit(profile.get("base_url", "") if profile else "")
        self.base_url_edit.setPlaceholderText("https://... (hanya untuk OpenAI-Compatible)")
        form.addRow("Base URL:", self.base_url_edit)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        if has_api_key:
            self.api_key_edit.setPlaceholderText("Sudah tersimpan di vault (isi untuk mengganti)")
        else:
            self.api_key_edit.setPlaceholderText("Masukkan API key...")
        form.addRow("API Key:", self.api_key_edit)

        layout.addLayout(form)

        info_lbl = QLabel(
            "API key tersimpan di brankas terenkripsi di USB, tidak pernah ditampilkan atau dicatat."
        )
        info_lbl.setObjectName("muted")
        layout.addWidget(info_lbl)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.kind_combo.currentIndexChanged.connect(self._update_url_visibility)
        self._update_url_visibility()

    def _update_url_visibility(self) -> None:
        kind = self.kind_combo.currentData()
        self.base_url_edit.setEnabled(kind == "openai_compatible")

    def _on_save(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Nibras", "Nama tampilan profil tidak boleh kosong.")
            return
        kind = self.kind_combo.currentData()
        if kind == "openai_compatible" and not self.base_url_edit.text().strip():
            QMessageBox.warning(self, "Nibras", "Base URL wajib diisi untuk OpenAI-Compatible.")
            return
        self.accept()

    def result_profile(self) -> dict:
        data = {
            "kind": self.kind_combo.currentData(),
            "name": self.name_edit.text().strip(),
            "base_url": self.base_url_edit.text().strip() if self.kind_combo.currentData() == "openai_compatible" else "",
        }
        if self.profile and self.profile.get("id"):
            data["id"] = self.profile["id"]
        return data

    def result_api_key(self) -> str:
        return self.api_key_edit.text().strip()


class ModelEditDialog(QDialog):
    """Add or edit a model under a profile."""

    def __init__(
        self,
        profile_id: str,
        model: dict | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.profile_id = profile_id
        self.model = model or {}
        is_edit = bool(model and model.get("id"))
        self.setWindowTitle("Edit Model" if is_edit else "Tambah Model")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(model.get("name", "") if model else "")
        self.name_edit.setPlaceholderText("Contoh: gpt-4o, claude-3-7-sonnet")
        form.addRow("Nama Model:", self.name_edit)

        self.context_window = QSpinBox()
        self.context_window.setRange(1024, 10_000_000)
        self.context_window.setSingleStep(4096)
        self.context_window.setValue(int(model.get("context_window", 128000) if model else 128000))
        form.addRow("Context Window (token):", self.context_window)

        self.can_stream = QCheckBox("Streaming (teks bertahap)")
        self.can_stream.setChecked(bool(model.get("can_stream", True) if model else True))
        form.addRow("Kemampuan Streaming:", self.can_stream)

        self.can_tools = QCheckBox("Tool Calling (pemanggilan fungsi)")
        self.can_tools.setChecked(bool(model.get("can_tools", False) if model else False))
        form.addRow("Kemampuan Tools:", self.can_tools)

        self.can_vision = QCheckBox("Vision (pemrosesan gambar)")
        self.can_vision.setChecked(bool(model.get("can_vision", False) if model else False))
        form.addRow("Kemampuan Vision:", self.can_vision)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Nibras", "Nama model tidak boleh kosong.")
            return
        self.accept()

    def result_model(self) -> dict:
        data = {
            "profile_id": self.profile_id,
            "name": self.name_edit.text().strip(),
            "context_window": self.context_window.value(),
            "can_stream": self.can_stream.isChecked(),
            "can_tools": self.can_tools.isChecked(),
            "can_vision": self.can_vision.isChecked(),
        }
        if self.model and self.model.get("id"):
            data["id"] = self.model["id"]
        return data
