import asyncio
from fastapi import APIRouter
from pydantic import BaseModel

import core.orchestrator as orchestrator

router = APIRouter(prefix="/hooks")

class TerminalEvent(BaseModel):
    command: str = ""
    exit_code: int = 0
    duration_ms: int = 0
    cwd: str = ""
    session_id: str = "default"

class ClaudeHookEvent(BaseModel):
    hook_type: str
    tool_name: str = ""
    tool_input: dict = {}
    session_id: str = "default"

@router.post("/terminal")
async def terminal_hook(event: TerminalEvent):
    asyncio.create_task(orchestrator.handle_terminal_event(
        event.command, event.exit_code, event.duration_ms, event.cwd, event.session_id
    ))
    return {"ok": True}

@router.post("/claude")
async def claude_hook(event: ClaudeHookEvent):
    asyncio.create_task(orchestrator.handle_claude_hook(
        event.hook_type, event.model_dump(), event.session_id
    ))
    return {"ok": True}
