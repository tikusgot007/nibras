"""Storage tests: PRAGMAs (D-01), migrations, conversations."""

from __future__ import annotations

from pathlib import Path

from nibras.storage import conversations
from nibras.storage.databases import (
    Databases,
    connect,
    get_schema_version,
    migrate,
)


def test_pragma_four_databases(data_dir: Path):
    dbs = Databases(data_dir).open_all()
    try:
        for name in Databases.NAMES:
            conn = dbs[name]
            assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
            # synchronous=FULL reads back as 2.
            assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2
            assert get_schema_version(conn) == 1
    finally:
        dbs.close()


def test_migration_from_version_0(data_dir: Path):
    # Create a v0 database by hand (only the version table, version 0),
    # then migrate it to the current version.
    path = data_dir / "core.db"
    conn = connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER)")
    conn.execute("INSERT INTO schema_version (version) VALUES (0)")
    conn.commit()
    assert get_schema_version(conn) == 0
    assert migrate(conn, "core.db") == 1
    assert get_schema_version(conn) == 1
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"settings", "session", "audit_log"} <= tables
    conn.close()


def test_conversation_roundtrip(data_dir: Path):
    dbs = Databases(data_dir).open_all()
    try:
        conn = dbs["conversations.db"]
        conv_id = conversations.create_conversation(conn, "Tes")
        conversations.add_message(conn, conv_id, "user", "Halo")
        mid = conversations.add_message(conn, conv_id, "assistant", "Hai", "done")
        msgs = conversations.list_messages(conn, conv_id)
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[1]["content"] == "Hai"
        conversations.update_message(conn, mid, "Hai!", "done")
        assert conversations.list_messages(conn, conv_id)[1]["content"] == "Hai!"
        assert conversations.list_conversations(conn)[0]["id"] == conv_id
    finally:
        dbs.close()


def test_quick_check_all_ok(data_dir: Path):
    dbs = Databases(data_dir).open_all()
    try:
        assert dbs.quick_check_all() == {n: "ok" for n in Databases.NAMES}
    finally:
        dbs.close()
