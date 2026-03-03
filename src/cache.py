"""Local SQLite cache for offline access to calendar events and tasks.

Stores the most recent sync snapshot so the widget can render even when
the network is unavailable.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "cache.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id          TEXT PRIMARY KEY,
            date        TEXT NOT NULL,
            summary     TEXT NOT NULL,
            source      TEXT NOT NULL,
            raw_json    TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def save_events(events: list[dict[str, Any]]) -> None:
    """Upsert a batch of events/tasks into the local cache."""
    conn = _get_conn()
    now = datetime.utcnow().isoformat()
    conn.executemany(
        """
        INSERT OR REPLACE INTO events (id, date, summary, source, raw_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                e["id"],
                e["date"],
                e["summary"],
                e["source"],
                json.dumps(e, ensure_ascii=False),
                now,
            )
            for e in events
        ],
    )
    conn.execute(
        "INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('last_sync', ?)",
        (now,),
    )
    conn.commit()
    conn.close()


def load_events(year: int, month: int) -> list[dict[str, Any]]:
    """Return cached events for the given year/month."""
    conn = _get_conn()
    prefix = f"{year}-{month:02d}"
    rows = conn.execute(
        "SELECT raw_json FROM events WHERE date LIKE ?",
        (f"{prefix}%",),
    ).fetchall()
    conn.close()
    return [json.loads(r[0]) for r in rows]


def clear_month(year: int, month: int) -> None:
    """Remove cached events for a specific month before re-syncing."""
    conn = _get_conn()
    prefix = f"{year}-{month:02d}"
    conn.execute("DELETE FROM events WHERE date LIKE ?", (f"{prefix}%",))
    conn.commit()
    conn.close()


def get_last_sync() -> str | None:
    """Return the ISO timestamp of the last successful sync, or None."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT value FROM sync_meta WHERE key = 'last_sync'"
    ).fetchone()
    conn.close()
    return row[0] if row else None
