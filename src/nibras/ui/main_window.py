"""Main chat window and dashboard host (D-41, D-42, D-44, D-47, D-48, D-50, D-59, D-64).

Layout:
- Stacked widget switching between Chat Mode and Dashboard Mode (D-41).
- In Chat Mode: sidebar on the left, chat view in the middle, input at the bottom.
- Status bar at the bottom: Active model & profile, provider status, vault status with auto-lock countdown, online/offline status (D-42 without cost, D-63).
- Fallback approval card support (D-64).
"""

from __future__ import annotations

import time
import uuid
from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config import AUTO_LOCK_TICK_SECONDS, KEY_AUTO_LOCK_MINUTES
from ..core.agent import AgentCore
from .chat_view import STATUS_LABELS, ChatView
from .dashboard import DashboardView
from .dialogs import PassphraseDialog


class MessageInput(QTextEdit):
    """Message box: Enter sends, Shift+Enter inserts a new line."""

    submitted = Signal()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if (event.key() in (Qt.Key_Return, Qt.Key_Enter)
                and not (event.modifiers() & Qt.ShiftModifier)):
            event.accept()
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(
        self,
        core: AgentCore,
        settings: dict,
        api_key_set: bool = False,
        on_settings_saved: Callable = lambda *a: None,
        on_safe_close: Callable = lambda: None,
        has_api_key_fn: Callable[[str], bool] | None = None,
        on_save_api_key: Callable[[str, str], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Nibras")
        self.resize(1100, 720)
        self._core = core
        self._settings = dict(settings)
        self._api_key_set = api_key_set
        self._on_settings_saved = on_settings_saved
        self._on_safe_close = on_safe_close
        self._has_api_key_fn = has_api_key_fn or (lambda _pid: False)
        self._on_save_api_key = on_save_api_key or (lambda _pid, _k: None)

        self._current_conversation: str | None = None
        self._streaming = False
        self._provider_ready = False
        self._pending_text: str | None = None
        self._last_activity = time.monotonic()
        self._vault_locked = False
        self._active_model_info: dict = {}

        self._build_ui()
        self._connect_core()
        self._setup_shortcuts()

        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(AUTO_LOCK_TICK_SECONDS * 1000)
        self._idle_timer.timeout.connect(self._tick_idle)
        self._idle_timer.start()

        core.request_load_conversations.emit()

    # -- UI construction -------------------------------------------------------
    def _build_ui(self) -> None:
        self._stack = QStackedWidget()

        # Page 0: Chat View
        chat_page = self._build_chat_page()
        self._stack.addWidget(chat_page)

        # Dashboard View is created lazily on first access (D-59)
        self._dashboard: DashboardView | None = None

        self.setCentralWidget(self._stack)

        # Status Bar (D-42 without cost, D-63)
        status = QStatusBar()
        self.setStatusBar(status)
        model_name = self._settings.get("provider.model", "").strip()
        self._status_model = QLabel(f"Model: {model_name}" if model_name else "Model: Belum diatur")
        self._status_provider = QLabel("Provider: menyiapkan AI…")
        self._status_vault = QLabel("Brankas: terbuka")
        self._status_online = QLabel("Status: Online")

        status.addWidget(self._status_model)
        status.addWidget(self._status_provider)
        status.addWidget(self._status_vault)
        status.addPermanentWidget(self._status_online)

    def _build_chat_page(self) -> QWidget:
        splitter = QSplitter(Qt.Horizontal)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        side_layout = QVBoxLayout(sidebar)

        new_btn = QPushButton("+ Percakapan baru")
        new_btn.clicked.connect(self._new_conversation)
        side_layout.addWidget(new_btn)

        self._conv_list = QListWidget()
        self._conv_list.itemClicked.connect(self._open_conversation)
        side_layout.addWidget(self._conv_list)

        btn_dash = QPushButton("⚙️ Dashboard")
        btn_dash.clicked.connect(self._show_dashboard)
        side_layout.addWidget(btn_dash)

        self._lock_btn = QPushButton("Kunci Brankas")
        self._lock_btn.clicked.connect(self._lock_vault)
        side_layout.addWidget(self._lock_btn)

        self._safe_close_btn = QPushButton("Tutup & Aman Dilepas")
        self._safe_close_btn.clicked.connect(self._on_safe_close)
        side_layout.addWidget(self._safe_close_btn)

        splitter.addWidget(sidebar)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        self._chat = ChatView()
        center_layout.addWidget(self._chat, 1)

        self._notice = QLabel("")
        self._notice.setObjectName("muted")
        center_layout.addWidget(self._notice)

        input_row = QHBoxLayout()
        self._input = MessageInput()
        self._input.submitted.connect(self._send_current)
        self._input.setPlaceholderText(
            "Tulis pesan... (Enter untuk kirim, Shift+Enter baris baru)"
        )
        self._input.setMaximumHeight(110)
        input_row.addWidget(self._input, 1)

        self._send_btn = QPushButton("Kirim")
        self._send_btn.setObjectName("primary")
        self._send_btn.clicked.connect(self._send_current)
        input_row.addWidget(self._send_btn)

        self._cancel_btn = QPushButton("Batalkan")
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._cancel_streaming)
        input_row.addWidget(self._cancel_btn)

        center_layout.addLayout(input_row)
        splitter.addWidget(center)
        splitter.setSizes([260, 840])
        return splitter

    def _connect_core(self) -> None:
        core = self._core
        core.conversations_loaded.connect(self._show_conversations)
        core.messages_loaded.connect(self._show_messages)
        core.conversation_created.connect(self._on_conversation_created)
        core.token_received.connect(self._on_token)
        core.message_finished.connect(self._on_message_finished)
        core.message_failed.connect(self._on_message_failed)
        core.fallback_offered.connect(self._on_fallback_offered)
        core.provider_ready.connect(self._on_provider_ready)
        core.context_truncated.connect(self._on_context_truncated)
        core.vault_locked.connect(self._on_vault_locked)
        core.active_model_changed.connect(self._on_active_model_changed)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._new_conversation)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._cancel_streaming)

    # -- mode switching --------------------------------------------------------
    def _show_dashboard(self) -> None:
        if self._dashboard is None:
            self._dashboard = DashboardView(
                core=self._core,
                settings=self._settings,
                has_api_key_fn=self._has_api_key_fn,
                on_save_api_key=self._on_save_api_key,
            )
            self._dashboard.back_to_chat.connect(self._show_chat)
            self._stack.addWidget(self._dashboard)
        self._dashboard.refresh()
        self._stack.setCurrentWidget(self._dashboard)

    def _show_chat(self) -> None:
        self._stack.setCurrentIndex(0)
        self._input.setFocus()

    # -- conversation handling -------------------------------------------------
    @Slot(list)
    def _show_conversations(self, items: list) -> None:
        self._conv_list.clear()
        for item in items:
            entry = QListWidgetItem(item["title"])
            entry.setData(Qt.UserRole, item["id"])
            self._conv_list.addItem(entry)

    def _new_conversation(self) -> None:
        self._core.request_new_conversation.emit()

    @Slot(str)
    def _on_conversation_created(self, conv_id: str) -> None:
        self._current_conversation = conv_id
        self._chat.clear()
        self._core.request_load_conversations.emit()
        self._input.setFocus()
        if self._pending_text and self._provider_ready and not self._vault_locked:
            text, self._pending_text = self._pending_text, None
            self._send_now(text)

    def _open_conversation(self, item: QListWidgetItem) -> None:
        conv_id = item.data(Qt.UserRole)
        self._current_conversation = conv_id
        self._core.request_load_messages.emit(conv_id)

    @Slot(str, list)
    def _show_messages(self, conv_id: str, messages: list) -> None:
        if conv_id != self._current_conversation:
            return
        self._chat.clear()
        for msg in messages:
            self._chat.add_message(
                msg["id"], msg["role"], msg["content"], msg.get("status", "")
            )

    # -- sending ---------------------------------------------------------------
    def _send_current(self) -> None:
        text = self._input.toPlainText().strip()
        if not text or self._streaming:
            return
        self._mark_activity()
        if self._vault_locked:
            self._ask_unlock_then_send(text)
            return
        if not self._provider_ready:
            self._pending_text = text
            self._notice.setText("Menyiapkan AI… pesanmu ditahan, tidak dibuang.")
            self._input.clear()
            return
        self._send_now(text)

    def _send_now(self, text: str) -> None:
        if self._current_conversation is None:
            self._pending_text = text
            self._core.request_new_conversation.emit()
            self._input.clear()
            return
        self._input.clear()
        self._notice.setText("")
        self._chat.add_message(f"local-{uuid.uuid4().hex}", "user", text)
        self._core.request_send.emit(self._current_conversation, text)
        self._streaming = True
        self._cancel_btn.setVisible(True)
        self._send_btn.setEnabled(False)

    def _prompt_unlock(self) -> bool:
        dlg = PassphraseDialog(first_setup=False, parent=self)
        if not dlg.exec():
            return False
        passphrase = dlg.passphrase()
        dlg.pass1.clear()
        self._on_settings_saved("unlock", passphrase)
        return not self._vault_locked

    def _ask_unlock_then_send(self, text: str) -> None:
        self._pending_text = text
        self._prompt_unlock()

    @Slot(str, str)
    def _on_token(self, message_id: str, delta: str) -> None:
        card = self._chat.card(message_id)
        if card is None:
            card = self._chat.add_message(message_id, "assistant", "")
        card.append_delta(delta)

    @Slot(str, str)
    def _on_message_finished(self, message_id: str, status: str) -> None:
        self._streaming = False
        self._cancel_btn.setVisible(False)
        self._send_btn.setEnabled(True)
        card = self._chat.card(message_id)
        if card is not None:
            card.finish(STATUS_LABELS.get(status, ""))
        self._core.request_load_conversations.emit()

    @Slot(str, str)
    def _on_message_failed(self, message_id: str, error: str) -> None:
        self._streaming = False
        self._cancel_btn.setVisible(False)
        self._send_btn.setEnabled(True)
        card = self._chat.card(message_id)
        if card is not None:
            card.finish()
            card.set_status(error + " — Tekan Kirim lagi untuk mencoba ulang.")
        QMessageBox.warning(self, "Nibras", error)

    @Slot(str, str, str)
    def _on_fallback_offered(self, message_id: str, fallback_label: str, error_text: str) -> None:
        """Display approval card for fallback (D-64)."""
        self._streaming = False
        self._cancel_btn.setVisible(False)
        self._send_btn.setEnabled(True)

        card = self._chat.card(message_id)
        if card is None:
            card = self._chat.add_message(message_id, "assistant", "")

        def _approve():
            self._streaming = True
            self._cancel_btn.setVisible(True)
            self._send_btn.setEnabled(False)
            self._core.request_send_fallback.emit(message_id)

        def _reject():
            self._core.request_reject_fallback.emit(message_id)

        self._chat.offer_fallback(
            message_id=message_id,
            fallback_label=fallback_label,
            error_text=error_text,
            on_approve=_approve,
            on_reject=_reject,
        )

    @Slot(bool)
    def _on_provider_ready(self, ready: bool) -> None:
        self._provider_ready = ready
        if not self._active_model_info:
            self._status_provider.setText("Provider: belum diatur")
        else:
            self._status_provider.setText("Provider: siap" if ready else "Provider: tidak terjangkau")

        if ready and self._pending_text and not self._vault_locked:
            text, self._pending_text = self._pending_text, None
            self._notice.setText("")
            self._send_now(text)

    @Slot(dict)
    def _on_active_model_changed(self, info: dict) -> None:
        self._active_model_info = dict(info)
        if not info:
            self._status_model.setText("Model: Belum diatur")
            self._status_provider.setText("Provider: belum diatur")
        else:
            pname = info.get("profile_name", "")
            mname = info.get("name", "")
            self._status_model.setText(f"Model: {mname} ({pname})")
            self._status_provider.setText("Provider: menyiapkan AI…")

    @Slot(str)
    def _on_context_truncated(self, _message_id: str) -> None:
        self._notice.setText(
            "Sebagian riwayat lama tidak dikirim karena melebihi context window."
        )

    def _cancel_streaming(self) -> None:
        if self._streaming:
            self._core.request_cancel.emit()

    # -- vault / idle ----------------------------------------------------------
    def _mark_activity(self) -> None:
        self._last_activity = time.monotonic()

    def _tick_idle(self) -> None:
        if self._vault_locked:
            return
        if self._streaming:
            self._mark_activity()
            return
        limit = int(self._settings.get(KEY_AUTO_LOCK_MINUTES, 30)) * 60
        idle = time.monotonic() - self._last_activity
        remaining = max(0, int(limit - idle))
        mins, secs = divmod(remaining, 60)
        self._status_vault.setText(f"Brankas: terbuka ({mins:02d}:{secs:02d})")
        if idle >= limit:
            self._lock_vault()

    def _lock_vault(self) -> None:
        self._vault_locked = True
        self._status_vault.setText("Brankas: terkunci")
        self._on_settings_saved("lock")
        self._core.request_lock_vault.emit()

    @Slot()
    def _on_vault_locked(self) -> None:
        self._vault_locked = True
        self._status_vault.setText("Brankas: terkunci")
        self._notice.setText(
            "Brankas terkunci. Pesan berikutnya akan ditahan sampai kamu "
            "memasukkan passphrase lagi."
        )

    def unlock_vault(self) -> None:
        self._vault_locked = False
        self._last_activity = time.monotonic()
        self._status_vault.setText("Brankas: terbuka")
        if self._pending_text:
            text, self._pending_text = self._pending_text, None
            self._send_now(text)

    # -- shutdown --------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self._on_safe_close()
        event.ignore()
