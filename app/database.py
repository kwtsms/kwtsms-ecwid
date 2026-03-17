"""SQLite database connection, table creation, and migrations."""

import json
import os
from contextlib import asynccontextmanager

import aiosqlite

from app.config import get_settings

_db_path: str = ""


def _get_db_path() -> str:
    global _db_path
    if not _db_path:
        _db_path = get_settings().database_path
    return _db_path


async def init_db() -> None:
    """Create database file, enable WAL, create tables and indexes."""
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS sms_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME DEFAULT (datetime('now')),
                event_type TEXT NOT NULL,
                recipient TEXT NOT NULL,
                message TEXT NOT NULL,
                template_key TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                api_response TEXT,
                msg_id TEXT,
                points_charged INTEGER DEFAULT 0,
                balance_after INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                lang TEXT NOT NULL DEFAULT 'en',
                body TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                updated_at DATETIME DEFAULT (datetime('now')),
                UNIQUE(event_type, lang)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS sync_data (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                synced_at DATETIME DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS debug_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME DEFAULT (datetime('now')),
                level TEXT NOT NULL DEFAULT 'INFO',
                module TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT
            )
        """)

        # Indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sms_log_created ON sms_log(created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sms_log_status ON sms_log(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sms_log_event ON sms_log(event_type)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_debug_log_created ON debug_log(created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_debug_log_level ON debug_log(level)")

        await db.commit()


@asynccontextmanager
async def get_db():
    """Yield an aiosqlite connection."""
    db = await aiosqlite.connect(_get_db_path())
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def execute_query(query: str, params: tuple | None = None) -> None:
    """Run a single write query with optional params."""
    async with get_db() as db:
        await db.execute(query, params or ())
        await db.commit()


async def fetch_one(query: str, params: tuple | None = None) -> dict | None:
    """Return one row as a dict."""
    async with get_db() as db:
        cursor = await db.execute(query, params or ())
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def fetch_all(query: str, params: tuple | None = None) -> list[dict]:
    """Return all rows as dicts."""
    async with get_db() as db:
        cursor = await db.execute(query, params or ())
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_setting(key: str) -> str | None:
    """Get a single setting value by key."""
    row = await fetch_one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else None


async def set_setting(key: str, value: str) -> None:
    """Upsert a setting."""
    await execute_query(
        "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now')) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
        (key, value),
    )


async def get_sync_data(key: str) -> dict | None:
    """Get cached sync data by key, parsed from JSON."""
    row = await fetch_one("SELECT data, synced_at FROM sync_data WHERE key = ?", (key,))
    if row is None:
        return None
    return {"data": json.loads(row["data"]), "synced_at": row["synced_at"]}


async def set_sync_data(key: str, data) -> None:
    """Upsert sync data as JSON."""
    await execute_query(
        "INSERT INTO sync_data (key, data, synced_at) VALUES (?, ?, datetime('now')) "
        "ON CONFLICT(key) DO UPDATE SET data = excluded.data, synced_at = datetime('now')",
        (key, json.dumps(data)),
    )
