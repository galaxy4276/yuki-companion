import json
from db.database import get_db

async def save_message(session_id: str, role: str, content: str,
                       event_type: str = "text", metadata: dict = None):
    db = await get_db()
    await db.execute(
        "INSERT INTO conversations (session_id, role, content, event_type, metadata) VALUES (?,?,?,?,?)",
        (session_id, role, content, event_type, json.dumps(metadata or {}))
    )
    await db.commit()

async def get_recent(session_id: str, limit: int = 10) -> list[dict]:
    db = await get_db()
    async with db.execute(
        "SELECT role, content FROM conversations WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
        (session_id, limit)
    ) as cursor:
        rows = await cursor.fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

async def save_terminal_event(command: str, exit_code: int, duration_ms: int, cwd: str):
    db = await get_db()
    await db.execute(
        "INSERT INTO terminal_events (command, exit_code, duration_ms, cwd) VALUES (?,?,?,?)",
        (command, exit_code, duration_ms, cwd)
    )
    await db.commit()
