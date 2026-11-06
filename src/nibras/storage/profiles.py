"""Provider profiles and models storage (D-15, D-64).

Profiles and models live in ``core.db``. API keys live only in the vault
keyed by profile id.

Kind is one of:
- ``openai``
- ``anthropic``
- ``openai_compatible``
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

KEY_ACTIVE_MODEL_ID = "active_model_id"
KEY_FALLBACK_MODEL_ID = "fallback_model_id"

VALID_KINDS = ("openai", "anthropic", "openai_compatible")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_profile(
    conn: sqlite3.Connection,
    kind: str,
    name: str,
    base_url: str = "",
    profile_id: str | None = None,
) -> dict:
    if kind not in VALID_KINDS:
        raise ValueError(f"Jenis provider tidak valid: {kind}")
    pid = profile_id or uuid.uuid4().hex
    ts = _now()
    conn.execute(
        "INSERT INTO provider_profiles (id, kind, name, base_url, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (pid, kind, name.strip(), base_url.strip(), ts),
    )
    conn.commit()
    return {
        "id": pid,
        "kind": kind,
        "name": name.strip(),
        "base_url": base_url.strip(),
        "created_at": ts,
    }


def update_profile(
    conn: sqlite3.Connection,
    profile_id: str,
    name: str,
    base_url: str = "",
) -> None:
    conn.execute(
        "UPDATE provider_profiles SET name = ?, base_url = ? WHERE id = ?",
        (name.strip(), base_url.strip(), profile_id),
    )
    conn.commit()


def delete_profile(conn: sqlite3.Connection, profile_id: str) -> None:
    # If the active or fallback model belongs to this profile, clear the setting
    active_m = get_active_model(conn)
    if active_m and active_m.get("profile_id") == profile_id:
        set_active_model(conn, "")
    fallback_m = get_fallback_model(conn)
    if fallback_m and fallback_m.get("profile_id") == profile_id:
        set_fallback_model(conn, None)

    conn.execute("DELETE FROM provider_models WHERE profile_id = ?", (profile_id,))
    conn.execute("DELETE FROM provider_profiles WHERE id = ?", (profile_id,))
    conn.commit()


def get_profile(conn: sqlite3.Connection, profile_id: str) -> dict | None:
    row = conn.execute(
        "SELECT id, kind, name, base_url, created_at FROM provider_profiles WHERE id = ?",
        (profile_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "kind": row[1],
        "name": row[2],
        "base_url": row[3],
        "created_at": row[4],
    }


def list_profiles(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, kind, name, base_url, created_at FROM provider_profiles ORDER BY created_at ASC"
    ).fetchall()
    return [
        {
            "id": r[0],
            "kind": r[1],
            "name": r[2],
            "base_url": r[3],
            "created_at": r[4],
        }
        for r in rows
    ]


def create_model(
    conn: sqlite3.Connection,
    profile_id: str,
    name: str,
    context_window: int = 128000,
    can_stream: bool = True,
    can_tools: bool = False,
    can_vision: bool = False,
    model_id: str | None = None,
) -> dict:
    mid = model_id or uuid.uuid4().hex
    ts = _now()
    conn.execute(
        "INSERT INTO provider_models "
        "(id, profile_id, name, context_window, can_stream, can_tools, can_vision, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            mid,
            profile_id,
            name.strip(),
            int(context_window),
            1 if can_stream else 0,
            1 if can_tools else 0,
            1 if can_vision else 0,
            ts,
        ),
    )
    conn.commit()
    return {
        "id": mid,
        "profile_id": profile_id,
        "name": name.strip(),
        "context_window": int(context_window),
        "can_stream": bool(can_stream),
        "can_tools": bool(can_tools),
        "can_vision": bool(can_vision),
        "created_at": ts,
    }


def update_model(
    conn: sqlite3.Connection,
    model_id: str,
    name: str,
    context_window: int,
    can_stream: bool = True,
    can_tools: bool = False,
    can_vision: bool = False,
) -> None:
    conn.execute(
        "UPDATE provider_models SET "
        "name = ?, context_window = ?, can_stream = ?, can_tools = ?, can_vision = ? "
        "WHERE id = ?",
        (
            name.strip(),
            int(context_window),
            1 if can_stream else 0,
            1 if can_tools else 0,
            1 if can_vision else 0,
            model_id,
        ),
    )
    conn.commit()


def delete_model(conn: sqlite3.Connection, model_id: str) -> None:
    active_m = get_active_model(conn)
    if active_m and active_m.get("id") == model_id:
        set_active_model(conn, "")
    fallback_m = get_fallback_model(conn)
    if fallback_m and fallback_m.get("id") == model_id:
        set_fallback_model(conn, None)

    conn.execute("DELETE FROM provider_models WHERE id = ?", (model_id,))
    conn.commit()


def get_model(conn: sqlite3.Connection, model_id: str) -> dict | None:
    row = conn.execute(
        "SELECT id, profile_id, name, context_window, can_stream, can_tools, can_vision, created_at "
        "FROM provider_models WHERE id = ?",
        (model_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "profile_id": row[1],
        "name": row[2],
        "context_window": row[3],
        "can_stream": bool(row[4]),
        "can_tools": bool(row[5]),
        "can_vision": bool(row[6]),
        "created_at": row[7],
    }


def list_models(conn: sqlite3.Connection, profile_id: str | None = None) -> list[dict]:
    if profile_id:
        rows = conn.execute(
            "SELECT id, profile_id, name, context_window, can_stream, can_tools, can_vision, created_at "
            "FROM provider_models WHERE profile_id = ? ORDER BY created_at ASC",
            (profile_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, profile_id, name, context_window, can_stream, can_tools, can_vision, created_at "
            "FROM provider_models ORDER BY created_at ASC"
        ).fetchall()
    return [
        {
            "id": r[0],
            "profile_id": r[1],
            "name": r[2],
            "context_window": r[3],
            "can_stream": bool(r[4]),
            "can_tools": bool(r[5]),
            "can_vision": bool(r[6]),
            "created_at": r[7],
        }
        for r in rows
    ]


def get_model_with_profile(conn: sqlite3.Connection, model_id: str) -> dict | None:
    row = conn.execute(
        "SELECT m.id, m.profile_id, m.name, m.context_window, m.can_stream, m.can_tools, m.can_vision, "
        "p.kind, p.name, p.base_url "
        "FROM provider_models m JOIN provider_profiles p ON m.profile_id = p.id "
        "WHERE m.id = ?",
        (model_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "profile_id": row[1],
        "name": row[2],
        "context_window": row[3],
        "can_stream": bool(row[4]),
        "can_tools": bool(row[5]),
        "can_vision": bool(row[6]),
        "profile_kind": row[7],
        "profile_name": row[8],
        "base_url": row[9],
    }


def get_active_model(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (KEY_ACTIVE_MODEL_ID,)
    ).fetchone()
    if not row or not row[0]:
        return None
    return get_model_with_profile(conn, row[0])


def set_active_model(conn: sqlite3.Connection, model_id: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (KEY_ACTIVE_MODEL_ID, model_id or ""),
    )
    conn.commit()


def get_fallback_model(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (KEY_FALLBACK_MODEL_ID,)
    ).fetchone()
    if not row or not row[0]:
        return None
    return get_model_with_profile(conn, row[0])


def set_fallback_model(conn: sqlite3.Connection, model_id: str | None) -> None:
    val = model_id or ""
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (KEY_FALLBACK_MODEL_ID, val),
    )
    conn.commit()
