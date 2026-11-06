"""Agent Core (D-11).

Threading design
----------------
The Core owns ONE dedicated thread (:class:`_CoreThread`). That thread

* runs the asyncio event loop (``run_forever``) as its main loop,
* opens the SQLite connections itself (a connection must be used in the
  thread that created it) and is the only thread that ever touches them,
* is the only thread that calls the provider.

UI -> Core. The ``request_*`` Qt signals stay the UI's API. They are
connected with ``Qt.DirectConnection`` to tiny functions that run in the
*emitting* (UI) thread and do nothing but hand the request to the Core's
loop with ``loop.call_soon_threadsafe``. A queued Qt connection would need
a Qt event loop running in the Core thread, which is not the case: the
asyncio loop is the thread's loop. The handler then runs in the Core
thread, in order of arrival.

Core -> UI. Responses are plain Qt signals emitted from the Core thread.
Their receivers live in the UI thread, so Qt delivers them queued; no
widget method is ever called from the Core thread.

Secrets. While the vault is locked the Core holds no API key and no
adapter. ``request_unlock`` hands it the key again and rebuilds the adapter.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal

from ..config import (
    KEY_BASE_URL,
    KEY_CONTEXT_WINDOW,
    KEY_MODEL,
)
from ..core.messages import CanonicalMessage
from ..providers.openai_compatible import OpenAICompatibleAdapter
from ..storage import audit, conversations
from ..storage.databases import Databases

log = logging.getLogger("nibras.core")

# An unfinished answer is flushed to disk at most this often, so a pulled
# USB stick loses at most a couple of seconds of text (D-08).
PARTIAL_SAVE_SECONDS = 2.0
START_TIMEOUT_SECONDS = 15.0
STOP_TIMEOUT_MS = 10_000


class _CoreThread(QThread):
    """The Core's dedicated thread. ``run`` is the Core's whole lifetime."""

    def __init__(self, core: "AgentCore"):
        super().__init__()
        self._core = core

    def run(self) -> None:
        self._core._thread_main()


class AgentCore(QObject):
    """Owns the Core thread, the asyncio loop, the adapter, and all database access."""

    # Core -> UI
    token_received = Signal(str, str)          # message_id, text delta
    message_finished = Signal(str, str)        # message_id, "done"|"failed"|"cancelled"
    message_failed = Signal(str, str)          # message_id, error text
    conversation_created = Signal(str)         # conversation_id
    conversations_loaded = Signal(list)        # [conversation dicts]
    messages_loaded = Signal(str, list)        # conversation_id, [message dicts]
    provider_ready = Signal(bool)              # provider reachable
    context_truncated = Signal(str)            # message_id
    vault_locked = Signal()

    # UI -> Core (emitted by the UI; handled in the Core thread, see module doc)
    request_send = Signal(str, str)            # conversation_id, text
    request_new_conversation = Signal()
    request_load_conversations = Signal()
    request_load_messages = Signal(str)        # conversation_id
    request_update_settings = Signal(dict, str)  # settings, new api key or ""
    request_audit = Signal(str, str)           # event, detail
    request_cancel = Signal()
    request_lock_vault = Signal()
    request_unlock = Signal(str)               # api key from the reopened vault

    def __init__(self, data_dir: Path, api_key: str, settings: dict):
        super().__init__()
        self._data_dir = Path(data_dir)
        self._api_key = api_key
        self._settings = dict(settings)
        self._dbs: Databases | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: _CoreThread | None = None
        self._adapter: OpenAICompatibleAdapter | None = None
        self._current_task: asyncio.Task | None = None
        self._tasks: set[asyncio.Task] = set()
        self._locked = False
        self._ready = threading.Event()
        self._start_error: BaseException | None = None

        direct = Qt.DirectConnection
        self.request_send.connect(
            lambda c, t: self._post(self._do_send, c, t), direct)
        self.request_new_conversation.connect(
            lambda: self._post(self._do_new_conversation), direct)
        self.request_load_conversations.connect(
            lambda: self._post(self._do_load_conversations), direct)
        self.request_load_messages.connect(
            lambda c: self._post(self._do_load_messages, c), direct)
        self.request_update_settings.connect(
            lambda s, k: self._post(self._do_update_settings, s, k), direct)
        self.request_audit.connect(
            lambda e, d: self._post(self._do_audit, e, d), direct)
        self.request_cancel.connect(
            lambda: self._post(self._do_cancel), direct)
        self.request_lock_vault.connect(
            lambda: self._post(self._do_lock_vault), direct)
        self.request_unlock.connect(
            lambda k: self._post(self._do_unlock, k), direct)

    # -- lifecycle (called from the UI thread) -----------------------------
    def start(self) -> None:
        """Start the Core thread and wait until its databases and loop are up."""
        self._thread = _CoreThread(self)
        self._thread.start()
        if not self._ready.wait(START_TIMEOUT_SECONDS):
            raise RuntimeError("Agent Core tidak siap dalam waktu yang wajar.")
        if self._start_error is not None:
            raise RuntimeError("Agent Core gagal dimulai.") from self._start_error

    def stop(self) -> None:
        """Stop the loop, let the Core thread clean up, and join it."""
        thread, loop = self._thread, self._loop
        if thread is None:
            return
        if loop is not None and thread.isRunning():
            try:
                loop.call_soon_threadsafe(loop.stop)
            except RuntimeError:  # loop already closed
                pass
        if not thread.wait(STOP_TIMEOUT_MS):
            log.error("Core thread tidak berhenti dalam %d ms", STOP_TIMEOUT_MS)
        self._thread = None

    # -- Core thread --------------------------------------------------------
    def _thread_main(self) -> None:
        """Whole lifetime of the Core thread."""
        loop = None
        try:
            # Databases are opened HERE, in the Core thread, because a SQLite
            # connection may only be used by the thread that created it.
            self._dbs = Databases(self._data_dir).open_all()
            audit.record(self._dbs["core.db"], "vault_open")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._build_adapter()
            self._spawn(self._check_provider())
        except BaseException as exc:  # noqa: BLE001 - reported to start()
            log.exception("Core gagal dimulai")
            self._start_error = exc
            self._ready.set()
            self._close_resources(loop)
            return
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            self._teardown(loop)

    def _teardown(self, loop: asyncio.AbstractEventLoop) -> None:
        pending = [t for t in self._tasks if not t.done()]
        for task in pending:
            task.cancel()  # the send handler saves the partial text on cancel
        if pending:
            try:
                loop.run_until_complete(asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True), 5))
            except Exception:  # noqa: BLE001
                log.exception("Pembatalan task saat shutdown gagal")
        if self._dbs is not None and not self._locked:
            try:
                audit.record(self._dbs["core.db"], "vault_lock", "shutdown")
            except Exception:  # noqa: BLE001
                log.exception("Audit shutdown gagal")
        self._close_resources(loop)

    def _close_resources(self, loop) -> None:
        self._api_key = ""
        self._adapter = None
        if self._dbs is not None:
            try:
                self._dbs.close()
            finally:
                self._dbs = None
        if loop is not None:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:  # noqa: BLE001
                pass
            loop.close()
        self._loop = None

    def _build_adapter(self) -> None:
        self._adapter = OpenAICompatibleAdapter(
            base_url=self._settings[KEY_BASE_URL],
            model=self._settings[KEY_MODEL],
            api_key=self._api_key,
            context_window=int(self._settings[KEY_CONTEXT_WINDOW]),
        )

    def _configured(self) -> bool:
        return bool(self._settings.get(KEY_BASE_URL, "").strip()
                    and self._settings.get(KEY_MODEL, "").strip())

    # -- request plumbing ---------------------------------------------------
    def _post(self, fn, *args) -> None:
        """Hand a UI request to the Core's loop. Safe to call from any thread."""
        loop = self._loop
        if loop is None:
            log.warning("Permintaan UI diabaikan: Core belum berjalan atau sudah berhenti")
            return
        try:
            loop.call_soon_threadsafe(self._run_handler, fn, args)
        except RuntimeError:  # loop closed between the check and the call
            log.warning("Permintaan UI diabaikan: loop Core sudah ditutup")

    def _run_handler(self, fn, args) -> None:
        """Runs in the Core thread. Coroutine handlers become tasks."""
        try:
            result = fn(*args)
            if asyncio.iscoroutine(result):
                self._spawn(result)
        except Exception:  # noqa: BLE001 - one bad request must not kill the loop
            log.exception("Handler Core gagal: %s", getattr(fn, "__name__", fn))

    def _spawn(self, coro) -> asyncio.Task:
        task = self._loop.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._task_done)
        return task

    def _task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            log.error("Task Core gagal", exc_info=task.exception())

    async def _check_provider(self) -> None:
        adapter = self._adapter
        if adapter is None or not self._configured():
            self.provider_ready.emit(False)
            return
        self.provider_ready.emit(await adapter.check_ready())

    # -- handlers (all run in the Core thread) ------------------------------
    def _do_new_conversation(self) -> None:
        conv_id = conversations.create_conversation(self._dbs["conversations.db"])
        self.conversation_created.emit(conv_id)

    def _do_load_conversations(self) -> None:
        self.conversations_loaded.emit(
            conversations.list_conversations(self._dbs["conversations.db"]))

    def _do_load_messages(self, conversation_id: str) -> None:
        self.messages_loaded.emit(conversation_id, conversations.list_messages(
            self._dbs["conversations.db"], conversation_id))

    def _do_audit(self, event: str, detail: str) -> None:
        audit.record(self._dbs["core.db"], event, detail)

    def _do_update_settings(self, settings: dict, api_key: str) -> None:
        conn = self._dbs["core.db"]
        for key, value in settings.items():
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
        conn.commit()
        # A locked Core never takes a key: it only comes back via request_unlock.
        self.update_settings(settings, None if self._locked else (api_key or None))
        if not self._locked:
            # New URL/model/key: the earlier readiness result is stale. Without
            # this the UI keeps "menyiapkan AI" and holds messages forever.
            self._spawn(self._check_provider())

    def _do_cancel(self) -> None:
        if self._current_task is not None:
            self._current_task.cancel()

    def _do_lock_vault(self) -> None:
        """Forget the API key and drop the adapter (D-10, D-39)."""
        if self._current_task is not None:
            self._current_task.cancel()  # never keep using the key after locking
        if self._adapter is not None:
            self._adapter.api_key = ""
        self._adapter = None
        self._api_key = ""
        if not self._locked:
            audit.record(self._dbs["core.db"], "vault_lock", "idle")
        self._locked = True
        self.vault_locked.emit()

    def _do_unlock(self, api_key: str) -> None:
        """The vault was reopened by the UI: take the key, rebuild the adapter."""
        self._api_key = api_key
        self._locked = False
        self._build_adapter()
        audit.record(self._dbs["core.db"], "vault_unlock")
        self._spawn(self._check_provider())

    async def _do_send(self, conversation_id: str, text: str) -> None:
        if self._adapter is None:
            self.vault_locked.emit()  # the UI asks for the passphrase and holds the text
            return
        if not self._configured():
            self.message_failed.emit(
                "", "Provider belum diatur. Buka Pengaturan, isi Base URL dan "
                    "Nama model, lalu coba lagi.")
            return
        if self._current_task is not None:
            log.warning("Pengiriman diabaikan: masih ada jawaban yang berjalan")
            return
        await self._handle_send(conversation_id, text)

    # -- chat pipeline ------------------------------------------------------
    async def _handle_send(self, conversation_id: str, text: str) -> None:
        adapter = self._adapter
        assert self._dbs is not None and adapter is not None
        conv_db = self._dbs["conversations.db"]
        # The user's message is stored ONCE; the history read back already
        # contains it, so it must not be appended to the context again.
        conversations.add_message(conv_db, conversation_id, "user", text)
        history = conversations.list_messages(conv_db, conversation_id)
        assistant_id = conversations.add_message(
            conv_db, conversation_id, "assistant", "", status="streaming")
        canonical = [
            CanonicalMessage(role=m["role"], content=m["content"])
            for m in history
            if m["status"] != "interrupted"
        ]
        to_send, truncated = adapter.trim_messages(canonical)
        if truncated:
            self.context_truncated.emit(assistant_id)

        full_text = ""
        self._current_task = asyncio.current_task()
        last_save = time.monotonic()
        try:
            async for delta in adapter.stream(to_send):
                full_text += delta
                self.token_received.emit(assistant_id, delta)
                now = time.monotonic()
                if now - last_save >= PARTIAL_SAVE_SECONDS:
                    conversations.update_message(
                        conv_db, assistant_id, full_text, "streaming")
                    last_save = now
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

    # -- settings -----------------------------------------------------------
    def update_settings(self, settings: dict, api_key: str | None = None) -> None:
        """Apply settings to the running adapter. Core thread only."""
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
