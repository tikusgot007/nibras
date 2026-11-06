"""SQLite storage (D-01, D-05).

Four databases, all with rollback journal (no WAL) and ``synchronous=FULL``:

- ``core.db``: settings, session markers, audit log, schema version.
- ``conversations.db``: conversations and messages.
- ``memory.db`` / ``index.db``: created empty in Tahap 1 (only the schema
  version table); used in Tahap 3.

Every database has a ``schema_version`` table and a simple integer-based
migration mechanism. Only the Agent Core thread may access these databases
(D-11); UI code must never import this module directly for writes.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# PRAGMA values required by D-01. ``synchronous=FULL`` reads back as 2.
PRAGMA_JOURNAL_MODE = "DELETE"
PRAGMA_SYNCHRONOUS = "FULL"

SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
"""

CORE_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS session (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    event TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
"""

CORE_SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS provider_profiles (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS provider_models (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES provider_profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    context_window INTEGER NOT NULL DEFAULT 128000,
    can_stream INTEGER NOT NULL DEFAULT 1,
    can_tools INTEGER NOT NULL DEFAULT 0,
    can_vision INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_provider_models_profile
    ON provider_models(profile_id);
"""

CONVERSATIONS_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'Percakapan baru',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'done',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);
"""

# Empty schemas for Tahap 3 databases: only the version table.
EMPTY_SCHEMA_V1 = ""

# name -> (current version, {version: sql})
SCHEMAS: dict[str, tuple[int, dict[int, str]]] = {
    "core.db": (2, {1: CORE_SCHEMA_V1, 2: CORE_SCHEMA_V2}),
    "conversations.db": (1, {1: CONVERSATIONS_SCHEMA_V1}),
    "memory.db": (1, {1: EMPTY_SCHEMA_V1}),
    "index.db": (1, {1: EMPTY_SCHEMA_V1}),
}


def connect(path: Path) -> sqlite3.Connection:
    """Open a database with the D-01 PRAGMAs applied."""
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def get_schema_version(conn: sqlite3.Connection) -> int:
    conn.execute(SCHEMA_VERSION_TABLE)
    row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    return int(row[0]) if row else 0


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))


def migrate(conn: sqlite3.Connection, name: str) -> int:
    """Apply pending migrations for ``name``. Returns the new version."""
    target, steps = SCHEMAS[name]
    current = get_schema_version(conn)
    if current > target:
        raise ValueError(f"{name}: schema version {current} > known {target}")
    for version in range(current + 1, target + 1):
        sql = steps[version]
        if sql.strip():
            conn.executescript(sql)
        set_schema_version(conn, version)
    conn.commit()
    return target


class Databases:
    """The four Nibras databases for one USB root."""

    NAMES = ("core.db", "conversations.db", "memory.db", "index.db")

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._conns: dict[str, sqlite3.Connection] = {}

    def open_all(self) -> "Databases":
        for name in self.NAMES:
            conn = connect(self.data_dir / name)
            if name == "core.db" and get_schema_version(conn) == 1:
                self._backup_v1(conn)
            migrate(conn, name)
            self._conns[name] = conn
        return self

    def _backup_v1(self, conn: sqlite3.Connection) -> None:
        """Backup core.db and vault.bin to Backups/ before migrating from v1."""
        backups = self.data_dir.parent / "Backups"
        backups.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest_db = backups / f"core_backup_v1_{ts}.db"
        bck = sqlite3.connect(str(dest_db))
        try:
            conn.backup(bck)
        finally:
            bck.close()

        vault_file = self.data_dir / "vault.bin"
        if vault_file.exists():
            shutil.copy2(vault_file, backups / f"vault_backup_v1_{ts}.bin")

    def __getitem__(self, name: str) -> sqlite3.Connection:
        return self._conns[name]

    def close(self) -> None:
        for conn in self._conns.values():
            try:
                conn.close()
            except sqlite3.Error:
                pass
        self._conns.clear()

    def quick_check_all(self) -> dict[str, str]:
        """Run PRAGMA quick_check on every database. Returns name -> result."""
        results: dict[str, str] = {}
        for name, conn in self._conns.items():
            row = conn.execute("PRAGMA quick_check").fetchone()
            results[name] = str(row[0]) if row else "unknown"
        return results
