"""Vault tests (D-09, D-10, D-39).

The API key must never appear in plaintext in the vault file. Tests use
fast Argon2id parameters so the suite stays quick; calibration itself is
covered by a timing smoke test with a small target.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nibras.security import vault
from nibras.security.vault import VaultError, create_vault, open_vault

FAST_PARAMS = {"time_cost": 1, "memory_cost": 1024, "lanes": 1}
API_KEY = "sk-test-tidak-asli-1234567890"


def test_create_and_open_roundtrip(tmp_path: Path):
    path = tmp_path / "vault.bin"
    create_vault(path, "passphrase-yang-benar", {"api_key": API_KEY},
                 params=FAST_PARAMS)
    payload = open_vault(path, "passphrase-yang-benar")
    assert payload == {"api_key": API_KEY}


def test_wrong_passphrase_rejected(tmp_path: Path):
    path = tmp_path / "vault.bin"
    create_vault(path, "benar", {"api_key": API_KEY}, params=FAST_PARAMS)
    with pytest.raises(VaultError, match="Passphrase salah"):
        open_vault(path, "salah")


def test_corrupt_vault_detected(tmp_path: Path):
    path = tmp_path / "vault.bin"
    create_vault(path, "benar", {"api_key": API_KEY}, params=FAST_PARAMS)
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 0xFF
    path.write_bytes(bytes(raw))
    with pytest.raises(VaultError):
        open_vault(path, "benar")


def test_truncated_vault_detected(tmp_path: Path):
    path = tmp_path / "vault.bin"
    path.write_bytes(b"NBRVAULT\x01terpotong")
    with pytest.raises(VaultError):
        open_vault(path, "benar")


def test_api_key_not_in_vault_file_plaintext(tmp_path: Path):
    path = tmp_path / "vault.bin"
    create_vault(path, "benar", {"api_key": API_KEY}, params=FAST_PARAMS)
    assert API_KEY.encode() not in path.read_bytes()
    assert b"sk-test" not in path.read_bytes()


def test_empty_passphrase_rejected(tmp_path: Path):
    with pytest.raises(VaultError):
        create_vault(tmp_path / "vault.bin", "", {"api_key": API_KEY},
                     params=FAST_PARAMS)


def test_calibrate_returns_usable_params():
    params = vault.calibrate_argon2(target_seconds=0.05,
                                    memory_cost=1024, lanes=1)
    assert params["time_cost"] >= 1
    assert params["memory_cost"] == 1024
    assert params["lanes"] == 1
