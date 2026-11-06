"""Agent Core (D-11, D-15, D-59, D-64).

Threading design
----------------
The Core owns ONE dedicated thread (:class:`_CoreThread`). That thread:
* runs the asyncio event loop (``run_forever``) as its main loop,
* opens the SQLite connections itself (D-01, D-11) and is the only thread
  that ever touches them,
* is the only thread that calls the providers.

Active Model & Fallback (D-64):
* There is ONE global active model.
* Fallback is NEVER automatic. When the active provider fails after retries,
  a fallback approval card is offered for that single message.
* If approved, fallback adapter is used for that single message only; subsequent
  messages automatically revert to the active model.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal

from ..core.messages import CanonicalMessage
from ..providers.base import ProviderAdapter
from ..providers.factory import create_adapter
from ..storage import audit, conversations, profiles
from ..storage.databases import Databases

log = logging.getLogger("nibras.core")

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
    fallback_offered = Signal(str, str, str)   # message_id, fallback_label, error_text
    conversation_created = Signal(str)         # conversation_id
    conversations_loaded = Signal(list)        # [conversation dicts]
    messages_loaded = Signal(str, list)        # conversation_id, [message dicts]
    provider_ready = Signal(bool)              # active provider reachable
    context_truncated = Signal(str)            # message_id
    vault_locked = Signal()
    profiles_loaded = Signal(list, list, str, str)  # profiles, models, active_id, fallback_id
    active_model_changed = Signal(dict)        # active model info dict

    # UI -> Core
    request_send = Signal(str, str)            # conversation_id, text
    request_send_fallback = Signal(str)        # assistant_message_id
    request_reject_fallback = Signal(str)      # assistant_message_id
    request_new_conversation = Signal()
    request_load_conversations = Signal()
    request_load_messages = Signal(str)        # conversation_id
    request_audit = Signal(str, str)           # event, detail
    request_cancel = Signal()
    request_lock_vault = Signal()
    request_unlock = Signal(object)            # api_keys mapping
    request_load_profiles = Signal()
    request_save_profile = Signal(dict, str)   # profile dict, api_key
    request_delete_profile = Signal(str)       # profile_id
    request_save_model = Signal(dict)          # model dict
    request_delete_model = Signal(str)         # model_id
    request_set_active_model = Signal(str)     # model_id
    request_set_fallback_model = Signal(str)   # model_id or ""
    request_update_settings = Signal(dict, str) # settings dict, new api key or ""

    def __init__(
        self,
        data_dir: Path,
        api_key: str = "",
        settings: dict | None = None,
        api_keys: dict[str, str] | None = None,
    ):
        super().__init__()
        self._data_dir = Path(data_dir)
        self._api_keys: dict[str, str] = {}
        if isinstance(api_key, dict):
            for k, v in api_key.items():
                if isinstance(v, (str, int, float)):
                    self._api_keys[str(k)] = str(v)
            self._api_key = ""
        elif isinstance(api_key, str) and api_key:
            self._api_key = api_key
            self._api_keys["default"] = api_key
        else:
            self._api_key = ""

        if isinstance(api_keys, dict):
            for k, v in api_keys.items():
                if isinstance(v, (str, int, float)):
                    self._api_keys[str(k)] = str(v)

        self._settings = dict(settings or {})
        self._dbs: Databases | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: _CoreThread | None = None

        self._adapter: ProviderAdapter | None = None
        self._active_model_info: dict | None = None
        self._current_task: asyncio.Task | None = None
        self._tasks: set[asyncio.Task] = set()
        self._locked = False
        self._ready = threading.Event()
        self._start_error: BaseException | None = None

        direct = Qt.DirectConnection
        self.request_send.connect(
            lambda c, t: self._post(self._do_send, c, t), direct)
        self.request_send_fallback.connect(
            lambda m: self._post(self._do_send_fallback, m), direct)
        self.request_reject_fallback.connect(
            lambda m: self._post(self._do_reject_fallback, m), direct)
        self.request_new_conversation.connect(
            lambda: self._post(self._do_new_conversation), direct)
        self.request_load_conversations.connect(
            lambda: self._post(self._do_load_conversations), direct)
        self.request_load_messages.connect(
            lambda c: self._post(self._do_load_messages, c), direct)
        self.request_audit.connect(
            lambda e, d: self._post(self._do_audit, e, d), direct)
        self.request_cancel.connect(
            lambda: self._post(self._do_cancel), direct)
        self.request_lock_vault.connect(
            lambda: self._post(self._do_lock_vault), direct)
        self.request_unlock.connect(
            lambda k: self._post(self._do_unlock, k), direct)
        self.request_load_profiles.connect(
            lambda: self._post(self._do_load_profiles), direct)
        self.request_save_profile.connect(
            lambda p, k: self._post(self._do_save_profile, p, k), direct)
        self.request_delete_profile.connect(
            lambda pid: self._post(self._do_delete_profile, pid), direct)
        self.request_save_model.connect(
            lambda m: self._post(self._do_save_model, m), direct)
        self.request_delete_model.connect(
            lambda mid: self._post(self._do_delete_model, mid), direct)
        self.request_set_active_model.connect(
            lambda mid: self._post(self._do_set_active_model, mid), direct)
        self.request_set_fallback_model.connect(
            lambda mid: self._post(self._do_set_fallback_model, mid), direct)
        self.request_update_settings.connect(
            lambda *args: self._post(self._do_update_settings, *args), direct)

    # -- lifecycle -------------------------------------------------------------
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
            except RuntimeError:
                pass
        if not thread.wait(STOP_TIMEOUT_MS):
            log.error("Core thread tidak berhenti dalam %d ms", STOP_TIMEOUT_MS)
        self._thread = None

    # -- Core thread -----------------------------------------------------------
    def _thread_main(self) -> None:
        """Whole lifetime of the Core thread."""
        loop = None
        try:
            self._dbs = Databases(self._data_dir).open_all()
            audit.record(self._dbs["core.db"], "vault_open")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._build_active_adapter()
            self._spawn(self._check_provider())
        except BaseException as exc:
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
            task.cancel()
        if pending:
            try:
                loop.run_until_complete(
                    asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), 5)
                )
            except Exception:
                log.exception("Pembatalan task saat shutdown gagal")
        if self._dbs is not None and not self._locked:
            try:
                audit.record(self._dbs["core.db"], "vault_lock", "shutdown")
            except Exception:
                log.exception("Audit shutdown gagal")
        self._close_resources(loop)

    def _close_resources(self, loop) -> None:
        self._api_keys.clear()
        self._adapter = None
        self._active_model_info = None
        if self._dbs is not None:
            try:
                self._dbs.close()
            finally:
                self._dbs = None
        if loop is not None:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()
        self._loop = None

    def _get_api_key_for_profile(self, profile_id: str) -> str:
        """Get API key strictly for profile_id with no fallback between profiles."""
        if not profile_id:
            return ""
        val = self._api_keys.get(profile_id, "")
        if isinstance(val, (str, int, float)):
            return str(val)
        return ""

    def _build_active_adapter(self) -> None:
        if self._dbs is None:
            return
        conn = self._dbs["core.db"]
        info = profiles.get_active_model(conn)
        self._active_model_info = info
        if info:
            profile_id = info["profile_id"]
            key = self._get_api_key_for_profile(profile_id)
            kind = info["profile_kind"]
            model = info["name"]
            cw = info["context_window"]
            base_url = info.get("base_url", "")
            self._adapter = create_adapter(kind, model, key, cw, base_url)
            self.active_model_changed.emit(info)
            return

        # Legacy fallback if no profiles in core.db yet (e.g. unit tests)
        base_url = self._settings.get("provider.base_url", "").strip()
        model = self._settings.get("provider.model", "").strip()
        if base_url or model:
            cw = int(self._settings.get("provider.context_window", 1000000))
            key = self._get_api_key_for_profile("default")
            self._adapter = create_adapter("openai_compatible", model, key, cw, base_url)
            info = {
                "name": model,
                "profile_name": "OpenAI-Compatible",
                "profile_kind": "openai_compatible",
                "context_window": cw,
                "base_url": base_url,
            }
            self._active_model_info = info
            self.active_model_changed.emit(info)
            return

        self._adapter = None
        self._active_model_info = None
        self.active_model_changed.emit({})

    def _configured(self) -> bool:
        if self._active_model_info and self._active_model_info.get("name"):
            kind = self._active_model_info.get("profile_kind", "")
            if kind == "openai_compatible" and not self._active_model_info.get("base_url", "").strip():
                return False
            return True
        return bool(
            self._settings.get("provider.base_url", "").strip()
            and self._settings.get("provider.model", "").strip()
        )

    async def _check_provider(self) -> None:
        adapter = self._adapter
        if adapter is None or not self._active_model_info:
            self.provider_ready.emit(False)
            return
        if not adapter.api_key.strip():
            self.provider_ready.emit(False)
            return
        is_ready = await adapter.check_ready()
        self.provider_ready.emit(is_ready)

    # -- request plumbing ------------------------------------------------------
    def _post(self, fn, *args) -> None:
        loop = self._loop
        if loop is None:
            log.warning("Permintaan UI diabaikan: Core belum berjalan atau sudah berhenti")
            return
        try:
            loop.call_soon_threadsafe(self._run_handler, fn, args)
        except RuntimeError:
            log.warning("Permintaan UI diabaikan: loop Core sudah ditutup")

    def _run_handler(self, fn, args) -> None:
        try:
            result = fn(*args)
            if asyncio.iscoroutine(result):
                self._spawn(result)
        except Exception:
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

    # -- handlers --------------------------------------------------------------
    def _do_new_conversation(self) -> None:
        conv_id = conversations.create_conversation(self._dbs["conversations.db"])
        self.conversation_created.emit(conv_id)

    def _do_load_conversations(self) -> None:
        self.conversations_loaded.emit(
            conversations.list_conversations(self._dbs["conversations.db"]))

    def _do_load_messages(self, conversation_id: str) -> None:
        self.messages_loaded.emit(
            conversation_id,
            conversations.list_messages(self._dbs["conversations.db"], conversation_id),
        )

    def _do_audit(self, event: str, detail: str) -> None:
        audit.record(self._dbs["core.db"], event, detail)

    def _do_cancel(self) -> None:
        if self._current_task is not None:
            self._current_task.cancel()

    def _do_lock_vault(self) -> None:
        if self._current_task is not None:
            self._current_task.cancel()
        if self._adapter is not None:
            self._adapter.api_key = ""
        self._adapter = None
        self._api_key = ""
        self._api_keys.clear()
        if not self._locked:
            audit.record(self._dbs["core.db"], "vault_lock", "idle")
        self._locked = True
        self.vault_locked.emit()

    def _do_unlock(self, keys: dict[str, str] | str) -> None:
        if isinstance(keys, str):
            self._api_keys = {"default": keys}
            self._api_key = keys
        else:
            self._api_keys = dict(keys)
            self._api_key = next(iter(keys.values())) if keys else ""
        self._locked = False
        self._build_active_adapter()
        audit.record(self._dbs["core.db"], "vault_unlock")
        self._spawn(self._check_provider())

    def _do_load_profiles(self) -> None:
        conn = self._dbs["core.db"]
        all_profiles = profiles.list_profiles(conn)
        all_models = profiles.list_models(conn)
        active_m = profiles.get_active_model(conn)
        fallback_m = profiles.get_fallback_model(conn)
        act_id = active_m["id"] if active_m else ""
        fb_id = fallback_m["id"] if fallback_m else ""
        self.profiles_loaded.emit(all_profiles, all_models, act_id, fb_id)

    def _do_save_profile(self, profile_data: dict, api_key: str) -> None:
        conn = self._dbs["core.db"]
        pid = profile_data.get("id")
        kind = profile_data["kind"]
        name = profile_data["name"]
        base_url = profile_data.get("base_url", "")
        if pid:
            profiles.update_profile(conn, pid, name, base_url)
        else:
            created = profiles.create_profile(conn, kind, name, base_url)
            pid = created["id"]

        if api_key:
            self._api_keys[pid] = api_key

        self._do_load_profiles()
        if self._active_model_info and self._active_model_info.get("profile_id") == pid:
            self._build_active_adapter()
            self._spawn(self._check_provider())

    def _do_delete_profile(self, profile_id: str) -> None:
        conn = self._dbs["core.db"]
        profiles.delete_profile(conn, profile_id)
        self._api_keys.pop(profile_id, None)
        self._do_load_profiles()
        self._build_active_adapter()
        self._spawn(self._check_provider())

    def _do_save_model(self, model_data: dict) -> None:
        conn = self._dbs["core.db"]
        mid = model_data.get("id")
        pid = model_data["profile_id"]
        name = model_data["name"]
        cw = int(model_data.get("context_window", 128000))
        can_stream = model_data.get("can_stream", True)
        can_tools = model_data.get("can_tools", False)
        can_vision = model_data.get("can_vision", False)
        if mid:
            profiles.update_model(conn, mid, name, cw, can_stream, can_tools, can_vision)
        else:
            profiles.create_model(conn, pid, name, cw, can_stream, can_tools, can_vision)
        self._do_load_profiles()
        if self._active_model_info and self._active_model_info.get("id") == mid:
            self._build_active_adapter()
            self._spawn(self._check_provider())

    def _do_delete_model(self, model_id: str) -> None:
        conn = self._dbs["core.db"]
        profiles.delete_model(conn, model_id)
        self._do_load_profiles()
        self._build_active_adapter()
        self._spawn(self._check_provider())

    def _do_set_active_model(self, model_id: str) -> None:
        conn = self._dbs["core.db"]
        profiles.set_active_model(conn, model_id)
        self._build_active_adapter()
        self._do_load_profiles()
        self._spawn(self._check_provider())

    def _do_set_fallback_model(self, model_id: str) -> None:
        conn = self._dbs["core.db"]
        profiles.set_fallback_model(conn, model_id if model_id else None)
        self._do_load_profiles()

    def _do_update_settings(self, settings: dict, api_key: str = "") -> None:
        conn = self._dbs["core.db"]
        for key, value in settings.items():
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
        conn.commit()
        self._settings.update(settings)
        if api_key:
            self._api_key = api_key
            self._api_keys["default"] = api_key
        self._build_active_adapter()
        self._spawn(self._check_provider())

    # -- chat send pipeline ----------------------------------------------------
    async def _do_send(self, conversation_id: str, text: str) -> None:
        if self._locked:
            self.vault_locked.emit()
            return
        if not self._configured() or self._adapter is None:
            self.message_failed.emit(
                "", "Provider belum diatur. Buka Pengaturan, isi Base URL dan "
                    "Nama model, lalu coba lagi.")
            return
        if not self._adapter.api_key.strip():
            self.message_failed.emit(
                "", "API key untuk profil ini belum diisi. Buka Dashboard > Provider & Model untuk mengisi API key.")
            return
        if self._current_task is not None:
            log.warning("Pengiriman diabaikan: masih ada jawaban yang berjalan")
            return
        await self._handle_send(conversation_id, text)

    async def _handle_send(
        self,
        conversation_id: str,
        text: str,
        override_adapter: ProviderAdapter | None = None,
        assistant_id: str | None = None,
    ) -> None:
        adapter = override_adapter or self._adapter
        assert self._dbs is not None and adapter is not None
        conv_db = self._dbs["conversations.db"]

        if assistant_id is None:
            conversations.add_message(conv_db, conversation_id, "user", text)
            history = conversations.list_messages(conv_db, conversation_id)
            assistant_id = conversations.add_message(
                conv_db, conversation_id, "assistant", "", status="streaming"
            )
        else:
            history = conversations.list_messages(conv_db, conversation_id)
            conversations.update_message(conv_db, assistant_id, "", "streaming")

        canonical = [
            CanonicalMessage(role=m["role"], content=m["content"])
            for m in history
            if m["id"] != assistant_id
            and m["status"] not in ("interrupted", "failed")
            and bool(m.get("content", "").strip())
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
                    conversations.update_message(conv_db, assistant_id, full_text, "streaming")
                    last_save = now
            conversations.update_message(conv_db, assistant_id, full_text, "done")
            self.message_finished.emit(assistant_id, "done")
        except asyncio.CancelledError:
            conversations.update_message(conv_db, assistant_id, full_text, "cancelled")
            self.message_finished.emit(assistant_id, "cancelled")
            raise
        except Exception as exc:
            log.error(
                "Streaming gagal (provider=%s, model=%s): %s: %s",
                adapter.name,
                adapter.model,
                type(exc).__name__,
                exc,
            )
            conversations.update_message(conv_db, assistant_id, full_text, "failed")
            friendly_err = _friendly_error(exc)

            fallback_info = (
                profiles.get_fallback_model(self._dbs["core.db"])
                if override_adapter is None
                else None
            )
            if fallback_info and fallback_info.get("id") != (self._active_model_info or {}).get("id"):
                fb_label = f"{fallback_info['profile_name']} — {fallback_info['name']}"
                self.fallback_offered.emit(assistant_id, fb_label, friendly_err)
            else:
                self.message_failed.emit(assistant_id, friendly_err)
        finally:
            self._current_task = None

    async def _do_send_fallback(self, assistant_id: str) -> None:
        """Handle fallback approval for a single message (D-64)."""
        if self._dbs is None or self._locked:
            self.vault_locked.emit()
            return
        if self._current_task is not None:
            log.warning("Pengiriman fallback diabaikan: masih ada jawaban yang berjalan")
            return

        conv_db = self._dbs["conversations.db"]
        msg = conversations.get_message(conv_db, assistant_id)
        if not msg:
            log.warning("Pesan %s tidak ditemukan untuk fallback", assistant_id)
            return

        fallback_info = profiles.get_fallback_model(self._dbs["core.db"])
        if not fallback_info:
            self.message_failed.emit(assistant_id, "Model cadangan tidak ditemukan.")
            return

        fb_key = self._get_api_key_for_profile(fallback_info["profile_id"])
        if not fb_key.strip():
            self.message_failed.emit(
                assistant_id,
                "API key untuk profil cadangan belum diisi. Buka Dashboard > Provider & Model untuk mengisi API key.",
            )
            return

        fb_adapter = create_adapter(
            kind=fallback_info["profile_kind"],
            model=fallback_info["name"],
            api_key=fb_key,
            context_window=fallback_info["context_window"],
            base_url=fallback_info.get("base_url", ""),
        )

        conversation_id = msg["conversation_id"]
        await self._handle_send(
            conversation_id=conversation_id,
            text="",
            override_adapter=fb_adapter,
            assistant_id=assistant_id,
        )

    def _do_reject_fallback(self, assistant_id: str) -> None:
        """User rejected fallback card: mark message failed (D-64)."""
        if self._dbs is not None:
            conv_db = self._dbs["conversations.db"]
            msg = conversations.get_message(conv_db, assistant_id)
            content = msg["content"] if msg else ""
            conversations.update_message(conv_db, assistant_id, content, "failed")
        self.message_finished.emit(assistant_id, "failed")


def _friendly_error(exc: Exception) -> str:
    name = type(exc).__name__
    s = str(exc)
    if "terputus" in s:
        return "Jawaban terputus di tengah jalan. Teks sebagian sudah disimpan — coba lagi."
    if "Connection" in name or "Timeout" in name:
        return "Tidak bisa terhubung ke provider. Periksa jaringan dan base_url, lalu coba lagi."
    if "RateLimit" in name or "429" in s:
        return "Provider membatasi permintaan (rate limit). Tunggu sebentar lalu coba lagi."
    if "Authentication" in name or "401" in s or "invalid_api_key" in s or "403" in s:
        return "API key ditolak provider. Periksa API key di Pengaturan."
    if "NotFound" in name or "404" in s:
        return "Model atau endpoint tidak ditemukan. Periksa nama model dan base_url."
    return f"Provider gagal ({name}): {s}"
