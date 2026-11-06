"""Tests for Tahap 2 profiles, models, vault keys, and v1->v2 migration (D-15, D-42, D-64)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from nibras.security.vault import (
    create_vault,
    delete_profile_api_key,
    get_profile_api_key,
    has_profile_api_key,
    open_vault,
    save_with_session,
    set_profile_api_key,
    unlock_vault,
)
from nibras.storage.databases import Databases
from nibras.storage.migration_v2 import migrate_tahap1_to_tahap2
from nibras.storage.profiles import (
    create_model,
    create_profile,
    delete_model,
    delete_profile,
    get_active_model,
    get_fallback_model,
    get_model,
    get_profile,
    list_models,
    list_profiles,
    set_active_model,
    set_fallback_model,
    update_model,
    update_profile,
)

FAST_PARAMS = {"time_cost": 1, "memory_cost": 1024, "lanes": 1}


def test_profile_crud(data_dir: Path):
    dbs = Databases(data_dir).open_all()
    try:
        conn = dbs["core.db"]
        p1 = create_profile(conn, kind="openai", name="OpenAI Official", base_url="https://api.openai.com/v1")
        assert p1["name"] == "OpenAI Official"
        assert p1["kind"] == "openai"
        assert p1["base_url"] == "https://api.openai.com/v1"

        p2 = create_profile(conn, kind="anthropic", name="Anthropic Official")
        assert p2["kind"] == "anthropic"

        profiles = list_profiles(conn)
        assert len(profiles) == 2
        assert [p["name"] for p in profiles] == ["OpenAI Official", "Anthropic Official"]

        # Update
        update_profile(conn, p1["id"], name="OpenAI Custom", base_url="https://custom.openai/v1")
        fetched = get_profile(conn, p1["id"])
        assert fetched is not None
        assert fetched["name"] == "OpenAI Custom"
        assert fetched["base_url"] == "https://custom.openai/v1"

        # Delete
        delete_profile(conn, p2["id"])
        assert len(list_profiles(conn)) == 1
        assert get_profile(conn, p2["id"]) is None
    finally:
        dbs.close()


def test_model_crud_and_selection(data_dir: Path):
    dbs = Databases(data_dir).open_all()
    try:
        conn = dbs["core.db"]
        prof = create_profile(conn, kind="openai", name="OpenAI")
        prof_id = prof["id"]

        m1 = create_model(conn, profile_id=prof_id, name="gpt-4o", context_window=128000)
        m2 = create_model(conn, profile_id=prof_id, name="gpt-4o-mini", context_window=64000)

        models = list_models(conn, profile_id=prof_id)
        assert len(models) == 2

        # Update model
        update_model(conn, m1["id"], name="gpt-4o-2024-11", context_window=200000)
        updated_m1 = get_model(conn, m1["id"])
        assert updated_m1 is not None
        assert updated_m1["name"] == "gpt-4o-2024-11"
        assert updated_m1["context_window"] == 200000

        # Set active and fallback
        set_active_model(conn, m1["id"])
        set_fallback_model(conn, m2["id"])

        active_info = get_active_model(conn)
        assert active_info is not None
        assert active_info["profile_id"] == prof_id
        assert active_info["id"] == m1["id"]
        assert active_info["name"] == "gpt-4o-2024-11"
        assert active_info["profile_kind"] == "openai"

        fallback_info = get_fallback_model(conn)
        assert fallback_info is not None
        assert fallback_info["profile_id"] == prof_id
        assert fallback_info["id"] == m2["id"]
        assert fallback_info["name"] == "gpt-4o-mini"

        # Clear fallback
        set_fallback_model(conn, None)
        assert get_fallback_model(conn) is None
    finally:
        dbs.close()


def test_profile_deletion_cascades(data_dir: Path):
    dbs = Databases(data_dir).open_all()
    try:
        conn = dbs["core.db"]
        prof = create_profile(conn, kind="openai", name="Test Cascade")
        m = create_model(conn, profile_id=prof["id"], name="test-m")
        set_active_model(conn, m["id"])
        set_fallback_model(conn, m["id"])

        assert get_active_model(conn) is not None

        # Delete profile
        delete_profile(conn, prof["id"])

        # Model should be deleted
        assert get_model(conn, m["id"]) is None
        # Active and fallback settings pointing to that profile should be cleared
        assert get_active_model(conn) is None
        assert get_fallback_model(conn) is None
    finally:
        dbs.close()


def test_vault_profile_api_keys():
    payload = {}

    assert has_profile_api_key(payload, "prof-1") is False
    assert get_profile_api_key(payload, "prof-1") == ""

    set_profile_api_key(payload, "prof-1", "sk-prof-key-1")
    set_profile_api_key(payload, "prof-2", "sk-ant-key-2")

    assert has_profile_api_key(payload, "prof-1") is True
    assert has_profile_api_key(payload, "prof-2") is True
    assert get_profile_api_key(payload, "prof-1") == "sk-prof-key-1"
    assert get_profile_api_key(payload, "prof-2") == "sk-ant-key-2"

    delete_profile_api_key(payload, "prof-1")
    assert has_profile_api_key(payload, "prof-1") is False
    assert get_profile_api_key(payload, "prof-1") == ""
    assert get_profile_api_key(payload, "prof-2") == "sk-ant-key-2"


def test_tahap1_to_tahap2_migration(root_dir: Path):
    data_dir = root_dir / "Data"
    backups_dir = root_dir / "Backups"

    # 1. Setup a legacy v1 core.db
    core_db_path = data_dir / "core.db"
    conn = sqlite3.connect(core_db_path)
    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("PRAGMA synchronous=FULL;")
    conn.execute("""
        CREATE TABLE schema_version (
            db_name TEXT PRIMARY KEY,
            version INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    conn.execute("""
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    conn.execute("""
        CREATE TABLE provider_profiles (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
    """)
    conn.execute("""
        CREATE TABLE provider_models (
            id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL,
            name TEXT NOT NULL,
            context_window INTEGER NOT NULL DEFAULT 128000,
            can_stream INTEGER NOT NULL DEFAULT 1,
            can_tools INTEGER NOT NULL DEFAULT 0,
            can_vision INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (profile_id) REFERENCES provider_profiles(id) ON DELETE CASCADE
        );
    """)
    conn.execute("INSERT INTO schema_version VALUES ('core', 2, '2026-11-01T00:00:00+00:00')")
    conn.execute("INSERT INTO settings VALUES ('provider.type', 'openai_compatible')")
    conn.execute("INSERT INTO settings VALUES ('provider.base_url', 'http://127.0.0.1:8000/v1')")
    conn.execute("INSERT INTO settings VALUES ('provider.model', 'llama-3-8b')")
    conn.execute("INSERT INTO settings VALUES ('provider.context_window', '8192')")
    conn.commit()

    # 2. Setup a legacy vault.bin with legacy 'api_key'
    vault_path = data_dir / "vault.bin"
    initial_payload = {"api_key": "sk-legacy-test-key"}
    create_vault(vault_path, "operator-pass", initial_payload, params=FAST_PARAMS)

    session, _ = unlock_vault(vault_path, "operator-pass")
    try:
        # 3. Perform migration
        updated_payload = migrate_tahap1_to_tahap2(
            conn=conn,
            vault_path=vault_path,
            session=session,
            payload=initial_payload,
            data_dir=data_dir,
            backups_dir=backups_dir,
        )

        # 4. Verify backup files were created in Backups/
        backups = list(backups_dir.glob("core_backup_v1_*.db"))
        assert len(backups) == 1
        vault_backups = list(backups_dir.glob("vault_backup_v1_*.bin"))
        assert len(vault_backups) == 1

        # 5. Verify core.db now has migrated profile & active model
        profiles = list_profiles(conn)
        assert len(profiles) == 1
        prof = profiles[0]
        assert prof["kind"] == "openai_compatible"
        assert prof["base_url"] == "http://127.0.0.1:8000/v1"

        models = list_models(conn, prof["id"])
        assert len(models) == 1
        m = models[0]
        assert m["name"] == "llama-3-8b"
        assert m["context_window"] == 8192

        active = get_active_model(conn)
        assert active is not None
        assert active["profile_id"] == prof["id"]
        assert active["id"] == m["id"]

        # 6. Verify vault payload has the profile key and kept legacy key
        assert get_profile_api_key(updated_payload, prof["id"]) == "sk-legacy-test-key"
        assert updated_payload.get("api_key") == "sk-legacy-test-key"

        # Verify reading vault from disk has updated payload
        disk_payload = open_vault(vault_path, "operator-pass")
        assert get_profile_api_key(disk_payload, prof["id"]) == "sk-legacy-test-key"

        # 7. Idempotence: calling migration again returns same payload without modifying
        second_call = migrate_tahap1_to_tahap2(
            conn=conn,
            vault_path=vault_path,
            session=session,
            payload=updated_payload,
            data_dir=data_dir,
            backups_dir=backups_dir,
        )
        assert second_call == updated_payload
    finally:
        session.wipe()
        conn.close()
