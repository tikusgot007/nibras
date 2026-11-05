"""Conversations and messages (conversations.db).

Only the Agent Core thread calls these functions (D-11).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_conversation(conn: sqlite3.Connection, title: str = "Percakapan baru") -> str:
    conv_id = uuid.uuid4().hex
    now = _now()
    conn.execute(
        "INSERT INTO conversations (id, title, created_at, updated_at) "
        "VALUES (?, ?, ?, ?)",
        (conv_id, title, now, now),
    )
    conn.commit()
    return conv_id


def list_conversations(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, title, created_at, updated_at FROM conversations "
        "ORDER BY updated_at DESC"
    ).fetchall()
    return [
        {"id": r[0], "title": r[1], "created_at": r[2], "updated_at": r[3]}
        for r in rows
    ]


def add_message(
    conn: sqlite3.Connection,
    conversation_id: str,
    role: str,
    content: str,
    status: str = "done",
) -> str:
    msg_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO messages (id, conversation_id, role, content, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (msg_id, conversation_id, role, content, status, _now()),
    )
    conn.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        (_now(), conversation_id),
    )
    conn.commit()
    return msg_id


def update_message(
    conn: sqlite3.Connection, message_id: str, content: str, status: str
) -> None:
    conn.execute(
        "UPDATE messages SET content = ?, status = ? WHERE id = ?",
        (content, status, message_id),
    )
    conn.commit()


def list_messages(conn: sqlite3.Connection, conversation_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, role, content, status, created_at FROM messages "
        "WHERE conversation_id = ? ORDER BY rowid",
        (conversation_id,),
    ).fetchall()
    return [
        {"id": r[0], "role": r[1], "content": r[2], "status": r[3], "created_at": r[4]}
        for r in rows
    ]


def rename_conversation(conn: sqlite3.Connection, conv_id: str, title: str) -> None:
    conn.execute(
        "UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id)
    )
    conn.commit()
