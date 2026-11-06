"""Data migration from Tahap 1 to Tahap 2 (D-05, D-15, D-64).

Migrates legacy provider.* settings and vault api_key into a single
openai_compatible provider profile and sets it as active model.
Existing data is kept intact. Core.db and vault.bin are backed up to
Backups/ before migration.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..security.vault import (
    VaultSession,
    save_with_session,
    set_profile_api_key,
)
from .profiles import (
    create_model,
    create_profile,
    list_profiles,
    set_active_model,
)

log = logging.getLogger("nibras.migration")


def backup_pre_migration(data_dir: Path, backups_dir: Path, conn: sqlite3.Connection) -> None:
    backups_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest_db = backups_dir / f"core_backup_v1_{ts}.db"
    bck = sqlite3.connect(str(dest_db))
    try:
        conn.backup(bck)
    finally:
        bck.close()

    vault_file = data_dir / "vault.bin"
    if vault_file.exists():
        shutil.copy2(vault_file, backups_dir / f"vault_backup_v1_{ts}.bin")
    log.info("Backup sebelum migrasi Tahap 1 -> Tahap 2 dibuat di %s", backups_dir)


def migrate_tahap1_to_tahap2(
    conn: sqlite3.Connection,
    vault_path: Path,
    session: VaultSession,
    payload: dict,
    data_dir: Path,
    backups_dir: Path,
) -> dict:
    """Migrate legacy provider settings and API key to profile format.

    Returns the updated vault payload.
    """
    # If profiles already exist, migration has already been executed.
    if list_profiles(conn):
        return payload

    # Read legacy settings from settings table
    rows = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    has_legacy_settings = (
        "provider.base_url" in rows or "provider.model" in rows or "api_key" in payload
    )
    if not has_legacy_settings:
        return payload

    log.info("Memulai migrasi data Tahap 1 ke profil provider Tahap 2...")
    backup_pre_migration(data_dir, backups_dir, conn)

    base_url = rows.get("provider.base_url", "")
    model_name = rows.get("provider.model", "")
    try:
        context_window = int(rows.get("provider.context_window", 1_000_000))
    except (ValueError, TypeError):
        context_window = 1_000_000

    display_name = "OpenAI-Compatible (Tahap 1)"
    profile = create_profile(
        conn,
        kind="openai_compatible",
        name=display_name,
        base_url=base_url,
    )
    model = create_model(
        conn,
        profile_id=profile["id"],
        name=model_name or "default",
        context_window=context_window,
        can_stream=True,
    )
    set_active_model(conn, model["id"])

    # Migrate API key into payload["api_keys"][profile_id]
    legacy_key = str(payload.get("api_key", ""))
    set_profile_api_key(payload, profile["id"], legacy_key)
    save_with_session(vault_path, session, payload)

    log.info("Migrasi Tahap 1 selesai: profile_id=%s, model_id=%s", profile["id"], model["id"])
    return payload
