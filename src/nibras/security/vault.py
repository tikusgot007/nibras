"""Credential vault (D-09, D-10, D-39).

File format (``Data/vault.bin``)::

    magic   8 bytes  b"NBRVAULT"
    version 1 byte   0x01
    salt    16 bytes random
    time    4 bytes  Argon2id time cost (big-endian uint32)
    memory  4 bytes  Argon2id memory cost in KiB (big-endian uint32)
    lanes   1 byte   Argon2id parallelism
    nonce   12 bytes random (AES-256-GCM)
    ct      rest     ciphertext + 16-byte GCM tag

The payload is JSON (currently ``{"api_key": "..."}``). The derived key
lives only in memory. A wrong passphrase raises :class:`VaultError` with
a clear message, never a crash and never a stack trace to the user. The
API key is never written to any log, database, or other file.
"""

from __future__ import annotations

import json
import os
import struct
import time
from pathlib import Path

from argon2.low_level import hash_secret_raw, Type
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"NBRVAULT"
VERSION = 0x01
SALT_LEN = 16
NONCE_LEN = 12
HEADER_LEN = 8 + 1 + SALT_LEN + 4 + 4 + 1 + NONCE_LEN  # 46 bytes

# Calibration target from D-39: key derivation takes ~0.5-1 s.
CALIBRATION_TARGET_SECONDS = 0.75


class VaultError(Exception):
    """Vault cannot be opened (wrong passphrase, corrupt or unknown file)."""


def _derive_key(passphrase: str, salt: bytes, time_cost: int,
                memory_cost: int, lanes: int) -> bytes:
    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=lanes,
        hash_len=32,
        type=Type.ID,
    )


def calibrate_argon2(target_seconds: float = CALIBRATION_TARGET_SECONDS,
                     memory_cost: int = 65536, lanes: int = 4) -> dict:
    """Pick an Argon2id time cost that takes ~target_seconds on this PC.

    Memory is fixed at 64 MiB; the time cost is doubled until the target
    is reached (capped at 32 iterations). Run once at first setup on the
    developer PC; the chosen parameters are stored in the vault header.
    """
    salt = os.urandom(SALT_LEN)
    time_cost = 1
    while time_cost <= 32:
        start = time.monotonic()
        _derive_key("calibration-probe", salt, time_cost, memory_cost, lanes)
        elapsed = time.monotonic() - start
        if elapsed >= target_seconds:
            break
        time_cost *= 2
    return {"time_cost": time_cost, "memory_cost": memory_cost, "lanes": lanes}


def create_vault(path: Path, passphrase: str, payload: dict,
                 params: dict | None = None) -> dict:
    """Create a new vault file. Returns the Argon2id parameters used."""
    if not passphrase:
        raise VaultError("Passphrase tidak boleh kosong.")
    params = params or calibrate_argon2()
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = _derive_key(passphrase, salt, params["time_cost"],
                      params["memory_cost"], params["lanes"])
    try:
        ct = AESGCM(key).encrypt(nonce, json.dumps(payload).encode("utf-8"), None)
    finally:
        _wipe(key)
    header = struct.pack(
        ">8sB16sIIB12s",
        MAGIC, VERSION, salt,
        params["time_cost"], params["memory_cost"], params["lanes"], nonce,
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(header + ct)
    os.replace(tmp, path)
    return params


def open_vault(path: Path, passphrase: str) -> dict:
    """Decrypt and return the vault payload. Raises VaultError on failure."""
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise VaultError(f"Tidak bisa membaca file vault: {exc}") from exc
    if len(raw) < HEADER_LEN or raw[:8] != MAGIC:
        raise VaultError("File vault rusak atau bukan file vault Nibras.")
    if raw[8] != VERSION:
        raise VaultError("Versi file vault tidak dikenali.")
    salt = raw[9:25]
    time_cost, memory_cost, lanes = struct.unpack(">IIB", raw[25:34])
    nonce = raw[34:46]
    ct = raw[46:]
    key = _derive_key(passphrase, salt, time_cost, memory_cost, lanes)
    try:
        pt = AESGCM(key).decrypt(nonce, ct, None)
    except InvalidTag as exc:
        raise VaultError("Passphrase salah. Silakan coba lagi.") from exc
    finally:
        _wipe(key)
    try:
        payload = json.loads(pt.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise VaultError("File vault rusak (isi tidak bisa dibaca).") from exc
    if not isinstance(payload, dict):
        raise VaultError("File vault rusak (format isi salah).")
    return payload


class VaultSession:
    """The derived key (NOT the passphrase) while the vault is open (D-39).

    The application keeps only this object after unlock. It lets Settings
    re-encrypt the payload without asking for the passphrase again and
    without re-running Argon2 (no UI freeze). :meth:`wipe` zeroes the key
    when the vault locks; afterwards every operation raises VaultError.
    Honest note (D-39): Python cannot guarantee no other copy of the key
    remains in RAM; this removes the references the application controls.
    """

    def __init__(self, key: bytearray, salt: bytes, params: dict):
        self._key: bytearray | None = key
        self.salt = salt
        self.params = dict(params)

    @property
    def is_open(self) -> bool:
        return self._key is not None

    def key(self) -> bytearray:
        if self._key is None:
            raise VaultError("Vault terkunci.")
        return self._key

    def wipe(self) -> None:
        if self._key is not None:
            _wipe(self._key)
            self._key = None


def _parse(raw: bytes) -> tuple[bytes, dict, bytes, bytes]:
    """Validate the header; return (salt, params, nonce, ciphertext)."""
    if len(raw) < HEADER_LEN or raw[:8] != MAGIC:
        raise VaultError("File vault rusak atau bukan file vault Nibras.")
    if raw[8] != VERSION:
        raise VaultError("Versi file vault tidak dikenali.")
    salt = raw[9:25]
    time_cost, memory_cost, lanes = struct.unpack(">IIB", raw[25:34])
    params = {"time_cost": time_cost, "memory_cost": memory_cost, "lanes": lanes}
    return salt, params, raw[34:46], raw[46:]


def _decrypt_payload(key, nonce: bytes, ct: bytes) -> dict:
    try:
        pt = AESGCM(bytes(key)).decrypt(nonce, ct, None)
    except InvalidTag as exc:
        raise VaultError("Passphrase salah. Silakan coba lagi.") from exc
    try:
        payload = json.loads(pt.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise VaultError("File vault rusak (isi tidak bisa dibaca).") from exc
    if not isinstance(payload, dict):
        raise VaultError("File vault rusak (format isi salah).")
    return payload


def _read_raw(path: Path) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise VaultError(f"Tidak bisa membaca file vault: {exc}") from exc


def unlock_vault(path: Path, passphrase: str) -> tuple[VaultSession, dict]:
    """Open the vault with the passphrase. Returns (session, payload); the
    caller keeps the session and drops the passphrase."""
    salt, params, nonce, ct = _parse(_read_raw(path))
    key = bytearray(_derive_key(passphrase, salt, params["time_cost"],
                                params["memory_cost"], params["lanes"]))
    try:
        payload = _decrypt_payload(key, nonce, ct)
    except VaultError:
        _wipe(key)
        raise
    return VaultSession(key, salt, params), payload


def read_with_session(path: Path, session: VaultSession) -> dict:
    """Decrypt the current payload with the held key (no Argon2)."""
    salt, _params, nonce, ct = _parse(_read_raw(path))
    if salt != session.salt:
        raise VaultError("File vault berubah di luar aplikasi. Buka ulang vault.")
    return _decrypt_payload(session.key(), nonce, ct)


def save_with_session(path: Path, session: VaultSession, payload: dict) -> None:
    """Re-encrypt the payload with the held key: same salt and Argon2
    parameters (from the vault header), fresh random nonce, no Argon2 run."""
    key = session.key()
    nonce = os.urandom(NONCE_LEN)
    ct = AESGCM(bytes(key)).encrypt(nonce, json.dumps(payload).encode("utf-8"), None)
    header = struct.pack(
        ">8sB16sIIB12s", MAGIC, VERSION, session.salt,
        session.params["time_cost"], session.params["memory_cost"],
        session.params["lanes"], nonce,
    )
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(header + ct)
    os.replace(tmp, path)


def vault_exists(path: Path) -> bool:
    return Path(path).is_file()


def get_profile_api_key(payload: dict, profile_id: str) -> str:
    """Retrieve API key for profile_id. No fallback between profiles."""
    if not profile_id or not isinstance(payload, dict):
        return ""
    keys = payload.get("api_keys")
    if isinstance(keys, dict) and profile_id in keys:
        val = keys[profile_id]
        return str(val) if isinstance(val, (str, int, float)) else ""
    return ""


def set_profile_api_key(payload: dict, profile_id: str, api_key: str) -> None:
    """Store API key for profile_id in vault payload."""
    keys = payload.setdefault("api_keys", {})
    if not isinstance(keys, dict):
        keys = {}
        payload["api_keys"] = keys
    keys[profile_id] = api_key


def delete_profile_api_key(payload: dict, profile_id: str) -> None:
    """Remove API key for profile_id from vault payload."""
    keys = payload.get("api_keys")
    if isinstance(keys, dict):
        keys.pop(profile_id, None)


def has_profile_api_key(payload: dict, profile_id: str) -> bool:
    return bool(get_profile_api_key(payload, profile_id).strip())


def _wipe(buf: bytearray | bytes) -> None:
    """Best-effort overwrite of a key buffer (D-39 honest note: Python
    cannot guarantee the key is truly gone from RAM)."""
    try:
        if isinstance(buf, bytearray):
            for i in range(len(buf)):
                buf[i] = 0
    except Exception:
        pass
