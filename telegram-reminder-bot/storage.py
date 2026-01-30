"""SQLite persistence for reminders. Survives bot restarts."""

import sqlite3
from datetime import datetime
from typing import Optional

from config import DB_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            task       TEXT    NOT NULL,
            fire_at    TEXT    NOT NULL,   -- ISO-8601 UTC
            created_at TEXT    NOT NULL,   -- ISO-8601 UTC
            fired      INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    return conn


_conn: Optional[sqlite3.Connection] = None


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _connect()
    return _conn


def add_reminder(task: str, fire_at: datetime) -> int:
    """Store a reminder and return its ID."""
    db = _db()
    cur = db.execute(
        "INSERT INTO reminders (task, fire_at, created_at) VALUES (?, ?, ?)",
        (task, fire_at.isoformat(), datetime.utcnow().isoformat()),
    )
    db.commit()
    return cur.lastrowid


def mark_fired(reminder_id: int) -> None:
    db = _db()
    db.execute("UPDATE reminders SET fired = 1 WHERE id = ?", (reminder_id,))
    db.commit()


def delete_reminder(reminder_id: int) -> bool:
    """Delete a reminder. Returns True if it existed."""
    db = _db()
    cur = db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    db.commit()
    return cur.rowcount > 0


def list_pending() -> list[dict]:
    """Return all unfired reminders, sorted by fire_at."""
    rows = _db().execute(
        "SELECT id, task, fire_at FROM reminders WHERE fired = 0 ORDER BY fire_at"
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_unfired() -> list[dict]:
    """Return all unfired reminders (used at startup to reload scheduler)."""
    rows = _db().execute(
        "SELECT id, task, fire_at FROM reminders WHERE fired = 0"
    ).fetchall()
    return [dict(r) for r in rows]
