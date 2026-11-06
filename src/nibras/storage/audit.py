"""Append-only audit log (D-40).

Stored as a table in ``core.db``. Records approvals, L2+ actions, Policy
Engine rejections, and every vault open/lock. Rows are never updated or
deleted by the application.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def record(conn: sqlite3.Connection, event: str, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO audit_log (ts, event, detail) VALUES (?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"), event, detail),
    )
    conn.commit()


def list_events(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    rows = conn.execute(
        "SELECT id, ts, event, detail FROM audit_log "
        "ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        {"id": r[0], "ts": r[1], "event": r[2], "detail": r[3]} for r in rows
    ]
