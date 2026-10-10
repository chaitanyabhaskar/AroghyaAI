"""Minimal SQLite persistence for chat sessions - stdlib only, no ORM."""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

# GenAI Generated code - Start

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    user_name   TEXT,
    language    TEXT NOT NULL DEFAULT 'en',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    has_image   INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages(session_id, id);
"""


def init(db_path: Path) -> None:
    """Open the database and create tables. Safe to call more than once."""
    global _conn
    with _lock:
        if _conn is not None:
            return
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(db_path), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _conn.executescript(_SCHEMA)
        _conn.commit()


def _db() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("store.init() was not called")
    return _conn


def create_session(user_name: str | None, language: str) -> str:
    session_id = uuid.uuid4().hex
    now = time.time()
    with _lock:
        _db().execute(
            "INSERT INTO sessions (id, user_name, language, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (session_id, user_name, language, now, now),
        )
        _db().commit()
    return session_id


def ensure_session(
    session_id: str | None, user_name: str | None, language: str
) -> str:
    """Return a valid session id, creating the row when needed."""
    if session_id:
        with _lock:
            row = _db().execute(
                "SELECT id FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row:
            return session_id
        # Client holds an id we no longer have (fresh container / cleared db).
        now = time.time()
        with _lock:
            _db().execute(
                "INSERT INTO sessions (id, user_name, language, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (session_id, user_name, language, now, now),
            )
            _db().commit()
        return session_id
    return create_session(user_name, language)


def add_message(
    session_id: str, role: str, content: str, has_image: bool = False
) -> None:
    now = time.time()
    with _lock:
        _db().execute(
            "INSERT INTO messages (session_id, role, content, has_image, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, 1 if has_image else 0, now),
        )
        _db().execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id)
        )
        _db().commit()


def recent_messages(session_id: str, limit: int = 12) -> list[dict[str, Any]]:
    """Last ``limit`` messages in chronological order."""
    with _lock:
        rows = _db().execute(
            "SELECT role, content, has_image, created_at FROM messages"
            " WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def session_history(session_id: str, limit: int = 200) -> list[dict[str, Any]]:
    with _lock:
        rows = _db().execute(
            "SELECT role, content, has_image, created_at FROM messages"
            " WHERE session_id = ? ORDER BY id ASC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_session(session_id: str) -> None:
    with _lock:
        _db().execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        _db().execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        _db().commit()
# GenAI Generated code - End
