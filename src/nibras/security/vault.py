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


def vault_exists(path: Path) -> bool:
    return Path(path).is_file()


def _wipe(buf: bytearray | bytes) -> None:
    """Best-effort overwrite of a key buffer (D-39 honest note: Python
    cannot guarantee the key is truly gone from RAM)."""
    try:
        if isinstance(buf, bytearray):
            for i in range(len(buf)):
                buf[i] = 0
    except Exception:
        pass
