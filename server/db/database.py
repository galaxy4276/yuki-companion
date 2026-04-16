import os
import asyncio
import aiosqlite
import config

_db: aiosqlite.Connection | None = None
_write_lock = asyncio.Lock()

async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
        _db = await aiosqlite.connect(config.DB_PATH)
        await _db.execute("PRAGMA journal_mode=WAL")
        _db.row_factory = aiosqlite.Row
    return _db

def write_lock() -> asyncio.Lock:
    return _write_lock

async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            event_type TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS terminal_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT,
            exit_code INTEGER,
            duration_ms INTEGER,
            cwd TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            content TEXT NOT NULL,
            turn_range TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_summary_session ON summaries(session_id, created_at);
    """)
    await db.commit()
