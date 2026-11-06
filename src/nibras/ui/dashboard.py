"""Dashboard view for Provider & Model and Settings (D-41, D-46, D-63).

Dashboard is opened as a dedicated mode (D-41).
Contains only:
- Provider & Model: provider profiles, models per profile, active model, fallback model.
- Settings: auto-lock duration, UI theme.
No budget, token, or cost tracking (D-63).
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import (
    DEFAULT_AUTO_LOCK_MINUTES,
    KEY_AUTO_LOCK_MINUTES,
    KEY_THEME,
)
from ..core.agent import AgentCore
from .dialogs import ModelEditDialog, ProfileEditDialog


class DashboardView(QWidget):
    back_to_chat = Signal()

    def __init__(
        self,
        core: AgentCore,
        settings: dict,
        has_api_key_fn: Callable[[str], bool],
        on_save_api_key: Callable[[str, str], None],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.core = core
        self.settings = dict(settings)
        self.has_api_key_fn = has_api_key_fn
        self.on_save_api_key = on_save_api_key

        self._profiles: list[dict] = []
        self._models: list[dict] = []
        self._active_model_id: str = ""
        self._fallback_model_id: str = ""

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -- Left Sidebar --
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(12, 16, 12, 16)
        sb_layout.setSpacing(10)

        btn_back = QPushButton("← Kembali ke Chat")
        btn_back.setStyleSheet("font-weight: bold; padding: 8px;")
        btn_back.clicked.connect(self.back_to_chat.emit)
        sb_layout.addWidget(btn_back)

        sb_layout.addSpacing(10)
        lbl_dash = QLabel("DASHBOARD")
        lbl_dash.setObjectName("muted")
        sb_layout.addWidget(lbl_dash)

        self.nav_list = QListWidget()
        self.nav_list.addItem(QListWidgetItem("Provider & Model"))
        self.nav_list.addItem(QListWidgetItem("Settings"))

        # Placeholder items for future stages (Tahap 3-5)
        for stage_name in [
            "Memori (Tahap 3)",
            "Tools & Policy (Tahap 4)",
            "Projects & Personas (Tahap 5)",
            "Backup & Restore (Tahap 5)",
        ]:
            item = QListWidgetItem(stage_name)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.nav_list.addItem(item)

        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        sb_layout.addWidget(self.nav_list)
        sb_layout.addStretch(1)

        main_layout.addWidget(sidebar)

        # -- Right Stack --
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_provider_page())
        self.stack.addWidget(self._build_settings_page())
        main_layout.addWidget(self.stack)

        self.nav_list.setCurrentRow(0)

        # Connect to Core signals
        self.core.profiles_loaded.connect(self._on_profiles_loaded)

    def refresh(self) -> None:
        self.core.request_load_profiles.emit()

    def _on_nav_changed(self, row: int) -> None:
        if row in (0, 1):
            self.stack.setCurrentIndex(row)

    # -- Provider & Model Page --
    def _build_provider_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = QLabel("Pengaturan Provider & Model")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        # 1. Profiles
        prof_box = QGroupBox("Profil Provider")
        pb_layout = QVBoxLayout(prof_box)

        btn_add_prof = QPushButton("+ Tambah Profil Provider")
        btn_add_prof.setFixedWidth(200)
        btn_add_prof.clicked.connect(self._on_add_profile)
        pb_layout.addWidget(btn_add_prof)

        self.profile_table = QTableWidget(0, 5)
        self.profile_table.setHorizontalHeaderLabels(
            ["Nama", "Jenis", "Base URL", "API Key", "Aksi"]
        )
        self.profile_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.profile_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        pb_layout.addWidget(self.profile_table)
        layout.addWidget(prof_box)

        # 2. Models
        model_box = QGroupBox("Daftar Model")
        mb_layout = QVBoxLayout(model_box)

        btn_add_model = QPushButton("+ Tambah Model")
        btn_add_model.setFixedWidth(160)
        btn_add_model.clicked.connect(self._on_add_model)
        mb_layout.addWidget(btn_add_model)

        self.model_table = QTableWidget(0, 5)
        self.model_table.setHorizontalHeaderLabels(
            ["Profil", "Nama Model", "Context Window", "Kemampuan", "Aksi"]
        )
        self.model_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.model_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        mb_layout.addWidget(self.model_table)
        layout.addWidget(model_box)

        # 3. Global Active & Fallback Selection (D-64)
        active_box = QGroupBox("Pemilihan Model Aktif & Cadangan (D-64)")
        ab_layout = QVBoxLayout(active_box)

        row_active = QHBoxLayout()
        row_active.addWidget(QLabel("Model Aktif (Global):"))
        self.combo_active = QComboBox()
        row_active.addWidget(self.combo_active, 1)
        ab_layout.addLayout(row_active)

        row_fallback = QHBoxLayout()
        row_fallback.addWidget(QLabel("Model Cadangan (Fallback):"))
        self.combo_fallback = QComboBox()
        row_fallback.addWidget(self.combo_fallback, 1)
        ab_layout.addLayout(row_fallback)

        btn_apply_models = QPushButton("Terapkan Pilihan Model")
        btn_apply_models.setStyleSheet("background-color: #61afef; color: #1e1e24; font-weight: bold; padding: 6px 14px;")
        btn_apply_models.clicked.connect(self._on_apply_models)
        ab_layout.addWidget(btn_apply_models, 0, Qt.AlignRight)

        layout.addWidget(active_box)
        return page

    # -- Settings Page --
    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = QLabel("Pengaturan Aplikasi")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        box = QGroupBox("Pengaturan Dasar")
        b_layout = QVBoxLayout(box)

        row_lock = QHBoxLayout()
        row_lock.addWidget(QLabel("Auto-lock brankas setelah idle (menit):"))
        self.spin_lock = QSpinBox()
        self.spin_lock.setRange(1, 480)
        self.spin_lock.setValue(int(self.settings.get(KEY_AUTO_LOCK_MINUTES, DEFAULT_AUTO_LOCK_MINUTES)))
        row_lock.addWidget(self.spin_lock)
        row_lock.addStretch(1)
        b_layout.addLayout(row_lock)

        row_theme = QHBoxLayout()
        row_theme.addWidget(QLabel("Tema tampilan:"))
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["midnight"])
        row_theme.addWidget(self.combo_theme)
        row_theme.addStretch(1)
        b_layout.addLayout(row_theme)

        btn_save_settings = QPushButton("Simpan Pengaturan")
        btn_save_settings.setStyleSheet("background-color: #61afef; color: #1e1e24; font-weight: bold; padding: 6px 14px;")
        btn_save_settings.clicked.connect(self._on_save_settings)
        b_layout.addWidget(btn_save_settings, 0, Qt.AlignRight)

        layout.addWidget(box)
        layout.addStretch(1)
        return page

    # -- Handlers for Provider & Models --
    def _on_profiles_loaded(
        self,
        profiles_list: list,
        models_list: list,
        active_id: str,
        fallback_id: str,
    ) -> None:
        self._profiles = profiles_list
        self._models = models_list
        self._active_model_id = active_id
        self._fallback_model_id = fallback_id

        # Populate profile table
        self.profile_table.setRowCount(len(self._profiles))
        for row, p in enumerate(self._profiles):
            self.profile_table.setItem(row, 0, QTableWidgetItem(p["name"]))
            self.profile_table.setItem(row, 1, QTableWidgetItem(p["kind"]))
            self.profile_table.setItem(row, 2, QTableWidgetItem(p.get("base_url", "") or "—"))

            has_key = self.has_api_key_fn(p["id"])
            key_item = QTableWidgetItem("Tersimpan" if has_key else "Kosong")
            if not has_key:
                key_item.setForeground(Qt.red)
            self.profile_table.setItem(row, 3, key_item)

            # Actions
            action_widget = QWidget()
            aw_layout = QHBoxLayout(action_widget)
            aw_layout.setContentsMargins(4, 2, 4, 2)
            aw_layout.setSpacing(6)

            btn_edit = QPushButton("Edit")
            btn_edit.clicked.connect(lambda _, prof=p: self._on_edit_profile(prof))
            aw_layout.addWidget(btn_edit)

            btn_del = QPushButton("Hapus")
            btn_del.setStyleSheet("color: #e06c75;")
            btn_del.clicked.connect(lambda _, pid=p["id"]: self._on_delete_profile(pid))
            aw_layout.addWidget(btn_del)

            self.profile_table.setCellWidget(row, 4, action_widget)

        # Populate models table
        self.model_table.setRowCount(len(self._models))
        prof_map = {p["id"]: p["name"] for p in self._profiles}
        for row, m in enumerate(self._models):
            pname = prof_map.get(m["profile_id"], "Unknown")
            self.model_table.setItem(row, 0, QTableWidgetItem(pname))
            self.model_table.setItem(row, 1, QTableWidgetItem(m["name"]))
            self.model_table.setItem(row, 2, QTableWidgetItem(f"{m['context_window']:,}"))

            caps = []
            if m.get("can_stream"):
                caps.append("stream")
            if m.get("can_tools"):
                caps.append("tools")
            if m.get("can_vision"):
                caps.append("vision")
            self.model_table.setItem(row, 3, QTableWidgetItem(", ".join(caps) or "—"))

            action_widget = QWidget()
            aw_layout = QHBoxLayout(action_widget)
            aw_layout.setContentsMargins(4, 2, 4, 2)
            aw_layout.setSpacing(6)

            btn_edit = QPushButton("Edit")
            btn_edit.clicked.connect(lambda _, mdl=m: self._on_edit_model(mdl))
            aw_layout.addWidget(btn_edit)

            btn_del = QPushButton("Hapus")
            btn_del.setStyleSheet("color: #e06c75;")
            btn_del.clicked.connect(lambda _, mid=m["id"]: self._on_delete_model(mid))
            aw_layout.addWidget(btn_del)

            self.model_table.setCellWidget(row, 4, action_widget)

        # Populate combo boxes
        self.combo_active.clear()
        self.combo_fallback.clear()

        self.combo_fallback.addItem("(Tidak ada cadangan)", "")

        for m in self._models:
            pname = prof_map.get(m["profile_id"], "Unknown")
            label = f"[{pname}] {m['name']}"
            self.combo_active.addItem(label, m["id"])
            self.combo_fallback.addItem(label, m["id"])

        if self._active_model_id:
            idx = self.combo_active.findData(self._active_model_id)
            if idx >= 0:
                self.combo_active.setCurrentIndex(idx)

        if self._fallback_model_id:
            idx = self.combo_fallback.findData(self._fallback_model_id)
            if idx >= 0:
                self.combo_fallback.setCurrentIndex(idx)
        else:
            self.combo_fallback.setCurrentIndex(0)

    def _on_add_profile(self) -> None:
        dlg = ProfileEditDialog(parent=self)
        if dlg.exec():
            prof = dlg.result_profile()
            key = dlg.result_api_key()
            self.core.request_save_profile.emit(prof, key)
            if prof.get("id") and key:
                self.on_save_api_key(prof["id"], key)

    def _on_edit_profile(self, profile: dict) -> None:
        has_key = self.has_api_key_fn(profile["id"])
        dlg = ProfileEditDialog(profile=profile, has_api_key=has_key, parent=self)
        if dlg.exec():
            prof = dlg.result_profile()
            key = dlg.result_api_key()
            self.core.request_save_profile.emit(prof, key)
            if key:
                self.on_save_api_key(prof["id"], key)

    def _on_delete_profile(self, profile_id: str) -> None:
        res = QMessageBox.question(
            self,
            "Hapus Profil",
            "Yakin ingin menghapus profil ini beserta seluruh modelnya?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if res == QMessageBox.Yes:
            self.core.request_delete_profile.emit(profile_id)

    def _on_add_model(self) -> None:
        if not self._profiles:
            QMessageBox.warning(self, "Nibras", "Buat profil provider terlebih dahulu.")
            return
        # Use first profile by default or prompt
        prof_id = self._profiles[0]["id"]
        dlg = ModelEditDialog(profile_id=prof_id, parent=self)
        if dlg.exec():
            mdl = dlg.result_model()
            self.core.request_save_model.emit(mdl)

    def _on_edit_model(self, model: dict) -> None:
        dlg = ModelEditDialog(profile_id=model["profile_id"], model=model, parent=self)
        if dlg.exec():
            mdl = dlg.result_model()
            self.core.request_save_model.emit(mdl)

    def _on_delete_model(self, model_id: str) -> None:
        res = QMessageBox.question(
            self,
            "Hapus Model",
            "Yakin ingin menghapus model ini?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if res == QMessageBox.Yes:
            self.core.request_delete_model.emit(model_id)

    def _on_apply_models(self) -> None:
        act_id = self.combo_active.currentData()
        fb_id = self.combo_fallback.currentData()
        if not act_id:
            QMessageBox.warning(self, "Nibras", "Pilih model aktif terlebih dahulu.")
            return
        if fb_id and fb_id == act_id:
            QMessageBox.warning(self, "Nibras", "Model cadangan tidak boleh sama dengan model aktif.")
            return
        self.core.request_set_active_model.emit(act_id)
        self.core.request_set_fallback_model.emit(fb_id or "")
        QMessageBox.information(self, "Nibras", "Pilihan model aktif dan cadangan berhasil disimpan.")

    def _on_save_settings(self) -> None:
        mins = self.spin_lock.value()
        self.settings[KEY_AUTO_LOCK_MINUTES] = str(mins)
        self.core.request_update_settings.emit({KEY_AUTO_LOCK_MINUTES: str(mins)}, "")
        QMessageBox.information(self, "Nibras", "Pengaturan aplikasi berhasil disimpan.")
