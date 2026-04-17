import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

import config
from db.database import init_db
from services import persona
from services.stt import load_whisper
from api.ws_handler import handle_ws
from api.hooks import router as hooks_router
import core.proactive as proactive
from core import events
from core.logging import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    events.init(os.path.join(os.path.dirname(__file__), "logs"))
    await init_db()
    persona.load_persona()
    load_whisper()
    asyncio.create_task(proactive.run())
    asyncio.create_task(persona.watch_persona())
    logger.info(f"기동 완료 — http://{config.HOST}:{config.PORT}")
    yield

app = FastAPI(title="VTuber Companion Orchestrator", lifespan=lifespan)
app.include_router(hooks_router)
app.mount("/static", StaticFiles(directory="static"), name="static")
_DEBUG_DIR = os.path.join(os.path.dirname(__file__), "static", "debug")
os.makedirs(_DEBUG_DIR, exist_ok=True)
app.mount("/debug", StaticFiles(directory=_DEBUG_DIR, html=True), name="debug")

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await handle_ws(websocket)

@app.get("/")
async def root():
    from fastapi.responses import FileResponse
    return FileResponse("static/index.html")

@app.get("/health")
async def health():
    from services.health import check
    return await check()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False)
