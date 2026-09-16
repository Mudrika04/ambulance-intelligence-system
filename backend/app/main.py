"""FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.deps import get_bus, get_pipeline, get_repo
from .api.routes import control, data, system, ws
from .core.config import get_config
from .core.logging_conf import get_logger, setup_logging
from .database.db import init_db

cfg = get_config()
setup_logging(str(cfg.get("logging.level", "INFO")))
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    get_bus().bind_loop(asyncio.get_running_loop())
    repo = get_repo()
    repo.sync_intersections(cfg.get("green_corridor.intersections") or [])
    repo.log_system_event("API_STARTED", message="backend online")
    log.info("backend ready", extra={"event": "API_STARTED"})
    yield
    p = get_pipeline()
    if p.running:
        p.stop()
    repo.log_system_event("API_STOPPED", message="backend offline")


app = FastAPI(
    title="AI-Based Real-Time Ambulance Detection, Tracking and Predictive Traffic Signal Control",
    description=("Explainable computer-vision platform for ambulance detection, "
                 "tracking, priority scoring and safety-aware signal control. "
                 "Project 27_CSAI_4B_04, PSIT Kanpur."),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.get("api.cors_origins", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router, prefix="/api")
app.include_router(data.router, prefix="/api")
app.include_router(control.router, prefix="/api")
app.include_router(ws.router)


@app.get("/")
def root():
    return {"name": "ambulance-intelligence-system", "docs": "/docs",
            "mode": cfg.mode, "websocket": "/ws/live"}
