import json
from db.database import get_db, write_lock

async def save_message(session_id: str, role: str, content: str,
                       event_type: str = "text", metadata: dict = None):
    async with write_lock():
        db = await get_db()
        await db.execute(
            "INSERT INTO conversations (session_id, role, content, event_type, metadata) VALUES (?,?,?,?,?)",
            (session_id, role, content, event_type, json.dumps(metadata or {}))
        )
        await db.commit()

async def get_recent(session_id: str, limit: int = 10) -> list[dict]:
    db = await get_db()
    async with db.execute(
        "SELECT role, content FROM conversations "
        "WHERE session_id=? AND (event_type IS NULL OR event_type NOT LIKE 'proactive_%') "
        "ORDER BY created_at DESC LIMIT ?",
        (session_id, limit)
    ) as cursor:
        rows = await cursor.fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

async def save_terminal_event(command: str, exit_code: int, duration_ms: int, cwd: str):
    async with write_lock():
        db = await get_db()
        await db.execute(
            "INSERT INTO terminal_events (command, exit_code, duration_ms, cwd) VALUES (?,?,?,?)",
            (command, exit_code, duration_ms, cwd)
        )
        await db.commit()

async def save_summary(session_id: str, content: str, turn_range: str):
    async with write_lock():
        db = await get_db()
        await db.execute(
            "INSERT INTO summaries (session_id, content, turn_range) VALUES (?,?,?)",
            (session_id, content, turn_range)
        )
        await db.commit()

async def get_latest_summary(session_id: str) -> str | None:
    db = await get_db()
    async with db.execute(
        "SELECT content FROM summaries WHERE session_id=? ORDER BY created_at DESC LIMIT 1",
        (session_id,)
    ) as cur:
        row = await cur.fetchone()
    return row["content"] if row else None

async def count_turns(session_id: str) -> int:
    db = await get_db()
    async with db.execute(
        "SELECT COUNT(*) as c FROM conversations WHERE session_id=?",
        (session_id,)
    ) as cur:
        row = await cur.fetchone()
    return row["c"] if row else 0

async def get_turns_range(session_id: str, offset: int, limit: int) -> list[dict]:
    db = await get_db()
    async with db.execute(
        "SELECT role, content FROM conversations WHERE session_id=? ORDER BY created_at ASC LIMIT ? OFFSET ?",
        (session_id, limit, offset)
    ) as cur:
        rows = await cur.fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


async def load_proactive_snapshot(tool_name: str) -> dict:
    """Return dict keyed by topic for a given tool. Empty if none."""
    db = await get_db()
    async with db.execute(
        "SELECT topic, last_value, last_triggered_at FROM proactive_state WHERE tool_name=?",
        (tool_name,)
    ) as cur:
        rows = await cur.fetchall()
    return {
        r["topic"]: {"last_value": r["last_value"], "last_triggered_at": r["last_triggered_at"]}
        for r in rows
    }


async def save_proactive_snapshot(topic: str, tool_name: str, last_value: str,
                                  triggered: bool = False):
    async with write_lock():
        db = await get_db()
        if triggered:
            await db.execute(
                "INSERT INTO proactive_state (topic, tool_name, last_value, last_triggered_at) "
                "VALUES (?,?,?,CURRENT_TIMESTAMP) "
                "ON CONFLICT(topic) DO UPDATE SET last_value=excluded.last_value, "
                "last_triggered_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP",
                (topic, tool_name, last_value)
            )
        else:
            await db.execute(
                "INSERT INTO proactive_state (topic, tool_name, last_value) VALUES (?,?,?) "
                "ON CONFLICT(topic) DO UPDATE SET last_value=excluded.last_value, "
                "updated_at=CURRENT_TIMESTAMP",
                (topic, tool_name, last_value)
            )
        await db.commit()


async def is_proactive_throttled(topic: str, throttle_seconds: int) -> bool:
    db = await get_db()
    async with db.execute(
        "SELECT last_triggered_at FROM proactive_state WHERE topic=? "
        "AND last_triggered_at IS NOT NULL "
        "AND (strftime('%s','now') - strftime('%s',last_triggered_at)) < ?",
        (topic, throttle_seconds)
    ) as cur:
        row = await cur.fetchone()
    return row is not None
