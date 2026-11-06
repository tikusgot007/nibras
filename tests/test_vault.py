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


# -- key session (D-39): hold the derived key, never the passphrase ----------

def _make(tmp_path: Path) -> Path:
    path = tmp_path / "vault.bin"
    create_vault(path, "passphrase-yang-benar", {"api_key": API_KEY},
                 params=FAST_PARAMS)
    return path


def test_unlock_returns_session_and_payload(tmp_path: Path):
    path = _make(tmp_path)
    session, payload = vault.unlock_vault(path, "passphrase-yang-benar")
    assert payload == {"api_key": API_KEY}
    assert session.is_open
    assert session.params == FAST_PARAMS


def test_unlock_wrong_passphrase_raises_and_leaves_no_session(tmp_path: Path):
    path = _make(tmp_path)
    with pytest.raises(VaultError):
        vault.unlock_vault(path, "salah")


def test_save_with_session_does_not_run_argon2(tmp_path: Path, monkeypatch):
    """Finding 7: saving settings must reuse the held key. Argon2 would
    freeze the UI thread for seconds, so any call to it is a failure."""
    path = _make(tmp_path)
    session, _ = vault.unlock_vault(path, "passphrase-yang-benar")

    def boom(*a, **k):
        raise AssertionError("Argon2 must not run when saving with a session")

    monkeypatch.setattr(vault, "_derive_key", boom)
    monkeypatch.setattr(vault, "calibrate_argon2", boom)
    vault.save_with_session(path, session, {"api_key": "kunci-baru-tes"})
    assert vault.read_with_session(path, session) == {"api_key": "kunci-baru-tes"}


def test_save_with_session_keeps_header_params_and_fresh_nonce(tmp_path: Path):
    path = _make(tmp_path)
    header_before = path.read_bytes()[:46]
    session, _ = vault.unlock_vault(path, "passphrase-yang-benar")
    vault.save_with_session(path, session, {"api_key": "satu"})
    after1 = path.read_bytes()[:46]
    vault.save_with_session(path, session, {"api_key": "dua"})
    after2 = path.read_bytes()[:46]
    # magic+version+salt+Argon2 params identical; only the nonce (last 12) changes
    assert header_before[:34] == after1[:34] == after2[:34]
    assert len({header_before[34:], after1[34:], after2[34:]}) == 3
    # and the passphrase still opens the re-saved file
    assert open_vault(path, "passphrase-yang-benar") == {"api_key": "dua"}


def test_wipe_zeroes_key_and_blocks_further_use(tmp_path: Path):
    path = _make(tmp_path)
    session, _ = vault.unlock_vault(path, "passphrase-yang-benar")
    held = session._key  # the exact buffer, to prove it is zeroed in place
    assert any(held)
    session.wipe()
    assert not any(held)
    assert not session.is_open
    with pytest.raises(VaultError):
        vault.read_with_session(path, session)
    with pytest.raises(VaultError):
        vault.save_with_session(path, session, {"api_key": "x"})


def test_session_rejects_vault_replaced_by_another_salt(tmp_path: Path):
    path = _make(tmp_path)
    session, _ = vault.unlock_vault(path, "passphrase-yang-benar")
    create_vault(path, "passphrase-yang-benar", {"api_key": "lain"},
                 params=FAST_PARAMS)  # new random salt
    with pytest.raises(VaultError):
        vault.read_with_session(path, session)
