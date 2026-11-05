"""Agent Core (D-11).

The Core lives in its own QThread and runs its own asyncio event loop
there. It is the only thread that touches the database or calls the
provider. The UI talks to it only through Qt signals (``request_*``);
the Core talks back only through Qt signals. No widget method is ever
called from this thread, and no database is ever touched from the UI.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..config import (
    KEY_BASE_URL,
    KEY_CONTEXT_WINDOW,
    KEY_MODEL,
)
from ..core.messages import CanonicalMessage
from ..providers.openai_compatible import OpenAICompatibleAdapter
from ..storage import audit, conversations
from ..storage.databases import Databases


class _CoreThread(QThread):
    """Runs the Core's asyncio event loop."""

    def __init__(self, core: "AgentCore"):
        super().__init__()
        self._core = core

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._core._loop = loop
        loop.create_task(self._core._check_provider())
        loop.run_forever()
        loop.close()


class AgentCore(QObject):
    """Owns the asyncio loop, the provider adapter, and all database access."""

    # Core -> UI
    token_received = Signal(str, str)          # message_id, text delta
    message_finished = Signal(str, str)        # message_id, "done"|"failed"|"cancelled"
    message_failed = Signal(str, str)          # message_id, error text
    conversation_created = Signal(str)         # conversation_id
    conversations_loaded = Signal(list)      # [conversation dicts]
    messages_loaded = Signal(str, list)      # conversation_id, [message dicts]
    provider_ready = Signal(bool)              # provider reachable
    context_truncated = Signal(str)            # message_id
    vault_locked = Signal()

    # UI -> Core (the UI emits these; the slots run on the Core thread)
    request_send = Signal(str, str)            # conversation_id, text
    request_new_conversation = Signal()
    request_load_conversations = Signal()
    request_load_messages = Signal(str)        # conversation_id
    request_update_settings = Signal(dict, str)  # settings, new api key or ""
    request_audit = Signal(str, str)           # event, detail
    request_cancel = Signal()
    request_lock_vault = Signal()

    def __init__(self, data_dir: Path, api_key: str, settings: dict):
        super().__init__()
        self._data_dir = Path(data_dir)
        self._api_key = api_key
        self._settings = dict(settings)
        self._dbs: Databases | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: _CoreThread | None = None
        self._current_task: asyncio.Task | None = None
        self._adapter: OpenAICompatibleAdapter | None = None

        self.request_send.connect(self.on_send)
        self.request_new_conversation.connect(self.on_new_conversation)
        self.request_load_conversations.connect(self.on_load_conversations)
        self.request_load_messages.connect(self.on_load_messages)
        self.request_update_settings.connect(self.on_update_settings)
        self.request_audit.connect(self.on_audit)
        self.request_cancel.connect(self.on_cancel)
        self.request_lock_vault.connect(self.on_lock_vault)

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        self._dbs = Databases(self._data_dir).open_all()
        audit.record(self._dbs["core.db"], "vault_open")
        self._adapter = OpenAICompatibleAdapter(
            base_url=self._settings[KEY_BASE_URL],
            model=self._settings[KEY_MODEL],
            api_key=self._api_key,
            context_window=int(self._settings[KEY_CONTEXT_WINDOW]),
        )
        self._thread = _CoreThread(self)
        self.moveToThread(self._thread)
        self._thread.start()

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)
        if self._dbs is not None:
            try:
                audit.record(self._dbs["core.db"], "vault_lock")
            except Exception:
                pass
            self._dbs.close()

    async def _check_provider(self) -> None:
        assert self._adapter is not None
        ready = await self._adapter.check_ready()
        self.provider_ready.emit(ready)

    # -- slots (run on the Core thread) ------------------------------------
    @Slot()
    def on_new_conversation(self) -> None:
        assert self._dbs is not None
        conv_id = conversations.create_conversation(self._dbs["conversations.db"])
        self.conversation_created.emit(conv_id)

    @Slot()
    def on_load_conversations(self) -> None:
        assert self._dbs is not None
        items = conversations.list_conversations(self._dbs["conversations.db"])
        self.conversations_loaded.emit(items)

    @Slot(str)
    def on_load_messages(self, conversation_id: str) -> None:
        assert self._dbs is not None
        items = conversations.list_messages(
            self._dbs["conversations.db"], conversation_id)
        self.messages_loaded.emit(conversation_id, items)

    @Slot(str, str)
    def on_audit(self, event: str, detail: str) -> None:
        assert self._dbs is not None
        audit.record(self._dbs["core.db"], event, detail)

    @Slot(dict, str)
    def on_update_settings(self, settings: dict, api_key: str) -> None:
        assert self._dbs is not None
        conn = self._dbs["core.db"]
        for key, value in settings.items():
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
        conn.commit()
        self.update_settings(settings, api_key or None)

    @Slot(str, str)
    def on_send(self, conversation_id: str, text: str) -> None:
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(
            self._handle_send(conversation_id, text), self._loop
        )

    @Slot()
    def on_cancel(self) -> None:
        if self._loop is not None and self._current_task is not None:
            self._loop.call_soon_threadsafe(self._current_task.cancel)

    @Slot()
    def on_lock_vault(self) -> None:
        self._api_key = ""
        self._adapter = None
        self.vault_locked.emit()

    # -- chat pipeline (runs on the Core thread) ---------------------------
    async def _handle_send(self, conversation_id: str, text: str) -> None:
        assert self._dbs is not None and self._adapter is not None
        conv_db = self._dbs["conversations.db"]
        conversations.add_message(conv_db, conversation_id, "user", text)
        history = conversations.list_messages(conv_db, conversation_id)
        assistant_id = conversations.add_message(
            conv_db, conversation_id, "assistant", "", status="streaming"
        )
        canonical = [
            CanonicalMessage(role=m["role"], content=m["content"])
            for m in history
            if m["status"] != "interrupted"
        ]
        canonical.append(CanonicalMessage(role="user", content=text))
        to_send, truncated = self._adapter.trim_messages(canonical)
        if truncated:
            self.context_truncated.emit(assistant_id)

        full_text = ""
        self._current_task = asyncio.current_task()
        try:
            async for delta in self._adapter.stream(to_send):
                full_text += delta
                self.token_received.emit(assistant_id, delta)
                if len(full_text) % 200 == 0:
                    conversations.update_message(
                        conv_db, assistant_id, full_text, "streaming"
                    )
            conversations.update_message(conv_db, assistant_id, full_text, "done")
            self.message_finished.emit(assistant_id, "done")
        except asyncio.CancelledError:
            conversations.update_message(conv_db, assistant_id, full_text, "cancelled")
            self.message_finished.emit(assistant_id, "cancelled")
            raise
        except Exception as exc:  # noqa: BLE001 - surfaced to the user as text
            conversations.update_message(conv_db, assistant_id, full_text, "failed")
            self.message_failed.emit(assistant_id, _friendly_error(exc))
        finally:
            self._current_task = None

    # -- settings ----------------------------------------------------------
    def update_settings(self, settings: dict, api_key: str | None = None) -> None:
        self._settings.update(settings)
        if api_key is not None:
            self._api_key = api_key
        if self._adapter is not None:
            self._adapter.base_url = self._settings[KEY_BASE_URL]
            self._adapter.model = self._settings[KEY_MODEL]
            self._adapter.context_window = int(self._settings[KEY_CONTEXT_WINDOW])
            if api_key is not None:
                self._adapter.api_key = api_key


def _friendly_error(exc: Exception) -> str:
    name = type(exc).__name__
    if "terputus" in str(exc):
        return ("Jawaban terputus di tengah jalan. Teks sebagian sudah "
                "disimpan — coba lagi.")
    if "Connection" in name or "Timeout" in name:
        return "Tidak bisa terhubung ke provider. Periksa jaringan dan base_url, lalu coba lagi."
    if "RateLimit" in name or "429" in str(exc):
        return "Provider membatasi permintaan (rate limit). Tunggu sebentar lalu coba lagi."
    if "Authentication" in name or "401" in str(exc):
        return "API key ditolak provider. Periksa API key di Pengaturan."
    if "NotFound" in name or "404" in str(exc):
        return "Model atau endpoint tidak ditemukan. Periksa nama model dan base_url."
    return f"Provider gagal: {exc}"
