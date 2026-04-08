import aiosqlite
import config

_db: aiosqlite.Connection | None = None

async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(config.DB_PATH)
        await _db.execute("PRAGMA journal_mode=WAL")
        _db.row_factory = aiosqlite.Row
    return _db

async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            role        TEXT NOT NULL,
            content     TEXT NOT NULL,
            event_type  TEXT,
            metadata    TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS terminal_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            command     TEXT,
            exit_code   INTEGER,
            duration_ms INTEGER,
            cwd         TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_conv_session
            ON conversations(session_id, created_at);
    """)
    await db.commit()
