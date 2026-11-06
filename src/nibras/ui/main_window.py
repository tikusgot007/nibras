"""Main chat window (D-41, D-42 sebagian, D-44, D-47, D-48, D-50, D-59).

Layout: sidebar kiri (daftar percakapan), chat di tengah, status bar di
bawah. The window never touches the database: every data request goes to
the Agent Core through signals.
"""

from __future__ import annotations

import time
import uuid

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
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config import (
    AUTO_LOCK_TICK_SECONDS,
    KEY_AUTO_LOCK_MINUTES,
    KEY_MODEL,
)
from ..core.agent import AgentCore
from .chat_view import ChatView
from .dialogs import PassphraseDialog, SettingsDialog


class MessageInput(QTextEdit):
    """Message box: Enter sends, Shift+Enter inserts a new line.

    A plain QTextEdit inserts a line break on Enter. While an IME is
    composing (e.g. Japanese/Chinese input) Qt hands Enter to the input
    method first, so it never reaches here and does not send by mistake.
    """

    submitted = Signal()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if (event.key() in (Qt.Key_Return, Qt.Key_Enter)
                and not (event.modifiers() & Qt.ShiftModifier)):
            event.accept()
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, core: AgentCore, settings: dict,
                 api_key_set: bool, on_settings_saved,
                 on_safe_close, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nibras")
        self.resize(1100, 700)
        self._core = core
        self._settings = dict(settings)
        self._api_key_set = api_key_set
        self._on_settings_saved = on_settings_saved
        self._on_safe_close = on_safe_close
        self._current_conversation: str | None = None
        self._streaming = False
        self._streaming_card = None
        self._provider_ready = False
        self._pending_text: str | None = None
        self._last_activity = time.monotonic()
        self._vault_locked = False

        self._build_ui()
        self._connect_core()
        self._setup_shortcuts()
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(AUTO_LOCK_TICK_SECONDS * 1000)
        self._idle_timer.timeout.connect(self._tick_idle)
        self._idle_timer.start()
        core.request_load_conversations.emit()

    # -- UI construction ---------------------------------------------------
    def _build_ui(self) -> None:
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
        settings_btn = QPushButton("Pengaturan")
        settings_btn.clicked.connect(self._open_settings)
        side_layout.addWidget(settings_btn)
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
            "Tulis pesan... (Enter untuk kirim, Shift+Enter baris baru)")
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
        self.setCentralWidget(splitter)

        status = QStatusBar()
        self.setStatusBar(status)
        self._status_model = QLabel(f"Model: {self._settings.get(KEY_MODEL, '')}")
        self._status_provider = QLabel("Provider: menyiapkan AI…")
        self._status_vault = QLabel("Vault: terbuka")
        status.addWidget(self._status_model)
        status.addWidget(self._status_provider)
        status.addWidget(self._status_vault)

    def _connect_core(self) -> None:
        core = self._core
        core.conversations_loaded.connect(self._show_conversations)
        core.messages_loaded.connect(self._show_messages)
        core.conversation_created.connect(self._on_conversation_created)
        core.token_received.connect(self._on_token)
        core.message_finished.connect(self._on_message_finished)
        core.message_failed.connect(self._on_message_failed)
        core.provider_ready.connect(self._on_provider_ready)
        core.context_truncated.connect(self._on_context_truncated)
        core.vault_locked.connect(self._on_vault_locked)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(
            self._new_conversation)
        QShortcut(QKeySequence("Escape"), self).activated.connect(
            self._cancel_streaming)

    # -- conversation list ---------------------------------------------------
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
        # A first message typed before any conversation existed was held while
        # the conversation was being created; send it now.
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
            self._chat.add_message(msg["id"], msg["role"], msg["content"])

    # -- sending -------------------------------------------------------------
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
        # Show the user's own message right away; it was never added to the
        # chat view before, so only the replies were visible.
        self._chat.add_message(f"local-{uuid.uuid4().hex}", "user", text)
        self._core.request_send.emit(self._current_conversation, text)
        self._streaming = True
        self._cancel_btn.setVisible(True)
        self._send_btn.setEnabled(False)

    def _prompt_unlock(self) -> bool:
        """Ask for the passphrase and reopen the vault. True when unlocked."""
        dlg = PassphraseDialog(first_setup=False, parent=self)
        if not dlg.exec():
            return False
        passphrase = dlg.passphrase()
        dlg.pass1.clear()
        self._on_settings_saved("unlock", passphrase)  # unlock_vault() runs on success
        return not self._vault_locked

    def _ask_unlock_then_send(self, text: str) -> None:
        self._pending_text = text  # held, never dropped (D-10)
        self._prompt_unlock()

    @Slot(str, str)
    def _on_token(self, message_id: str, delta: str) -> None:
        card = self._chat.card(message_id)
        if card is None:
            card = self._chat.add_message(message_id, "assistant", "")
            self._streaming_card = card
        card.append_delta(delta)

    @Slot(str, str)
    def _on_message_finished(self, message_id: str, status: str) -> None:
        self._streaming = False
        self._cancel_btn.setVisible(False)
        self._send_btn.setEnabled(True)
        card = self._chat.card(message_id)
        if card is not None:
            card.finish()
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

    @Slot(bool)
    def _on_provider_ready(self, ready: bool) -> None:
        self._provider_ready = ready
        self._status_provider.setText(
            "Provider: siap" if ready else "Provider: tidak terjangkau")
        if ready and self._pending_text:
            text, self._pending_text = self._pending_text, None
            self._notice.setText("")
            self._send_now(text)

    @Slot(str)
    def _on_context_truncated(self, _message_id: str) -> None:
        self._notice.setText(
            "Sebagian riwayat lama tidak dikirim karena melebihi context window.")

    def _cancel_streaming(self) -> None:
        if self._streaming:
            self._core.request_cancel.emit()

    # -- settings --------------------------------------------------------------
    def _open_settings(self) -> None:
        if self._vault_locked and not self._prompt_unlock():
            return  # a new API key can only be saved into an open vault
        dlg = SettingsDialog(self._settings, self._api_key_set, parent=self)
        if not dlg.exec():
            return
        new_settings = dlg.result_settings()
        api_key = dlg.result_api_key()
        self._settings.update(new_settings)
        self._status_model.setText(f"Model: {new_settings.get(KEY_MODEL, '')}")
        if api_key:
            self._api_key_set = True
        self._provider_ready = False
        self._status_provider.setText("Provider: menyiapkan AI…")
        self._core.request_update_settings.emit(new_settings, api_key)
        self._on_settings_saved("settings", new_settings, api_key)

    # -- vault / idle ------------------------------------------------------------
    def _mark_activity(self) -> None:
        self._last_activity = time.monotonic()

    def _tick_idle(self) -> None:
        if self._vault_locked:
            return
        if self._streaming:  # never lock in the middle of an answer
            self._mark_activity()
            return
        limit = int(self._settings.get(KEY_AUTO_LOCK_MINUTES, 30)) * 60
        idle = time.monotonic() - self._last_activity
        remaining = max(0, int(limit - idle))
        mins, secs = divmod(remaining, 60)
        self._status_vault.setText(f"Vault: terbuka (auto-lock {mins:02d}:{secs:02d})")
        if idle >= limit:
            self._lock_vault()

    def _lock_vault(self) -> None:
        self._vault_locked = True
        self._status_vault.setText("Vault: terkunci")
        self._on_settings_saved("lock")  # Application wipes its derived key
        self._core.request_lock_vault.emit()

    @Slot()
    def _on_vault_locked(self) -> None:
        self._vault_locked = True
        self._status_vault.setText("Vault: terkunci")
        self._notice.setText(
            "Vault terkunci. Pesan berikutnya akan ditahan sampai kamu "
            "memasukkan passphrase lagi.")

    def unlock_vault(self) -> None:
        self._vault_locked = False
        self._last_activity = time.monotonic()
        self._status_vault.setText("Vault: terbuka")
        if self._pending_text:
            text, self._pending_text = self._pending_text, None
            self._send_now(text)

    # -- shutdown ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self._on_safe_close()
        event.ignore()
