from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.adapters.seed_fixtures import seed_database_if_empty
from app.api.v1.router import api_router
from app.config import settings
from app.realtime.ws_manager import RealtimeTickManager
from app.storage.duckdb_engine import get_db

tick_manager: RealtimeTickManager | None = None
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global tick_manager
    db = get_db()
    seed_database_if_empty(db)
    tick_manager = RealtimeTickManager(db)
    tick_manager.start()
    yield
    if tick_manager is not None:
        await tick_manager.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket) -> None:
    global tick_manager
    if tick_manager is None:
        db = get_db()
        seed_database_if_empty(db)
        tick_manager = RealtimeTickManager(db)
        tick_manager.start()

    await tick_manager.connect(ws)
    try:
        while True:
            msg = await ws.receive_json()
            action = str(msg.get("action", "")).lower()
            ids = msg.get("instrument_ids") or []
            if isinstance(ids, list):
                if action == "subscribe":
                    tick_manager.subscribe(ws, [str(x) for x in ids])
                elif action == "unsubscribe":
                    tick_manager.unsubscribe(ws, [str(x) for x in ids])
    except WebSocketDisconnect:
        tick_manager.disconnect(ws)
    except Exception:  # noqa: BLE001
        tick_manager.disconnect(ws)


# Serve built React production bundle directly when available (single-port unified server)
if (FRONTEND_DIST / "index.html").exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str) -> FileResponse:
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
