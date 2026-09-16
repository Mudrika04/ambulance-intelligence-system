from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...core.logging_conf import get_logger
from ..deps import get_bus, get_pipeline

router = APIRouter()
log = get_logger(__name__)


@router.websocket("/ws/live")
async def live(ws: WebSocket):
    await ws.accept()
    bus = get_bus()
    bus.bind_loop(asyncio.get_running_loop())
    queue = bus.subscribe()
    pipeline = get_pipeline()
    try:
        await ws.send_text(json.dumps({"type": "hello",
                                       "payload": pipeline.snapshot()}))
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=2.0)
            except asyncio.TimeoutError:
                msg = {"type": "system_health",
                       "payload": {"health": pipeline.health(),
                                   "running": pipeline.running,
                                   "metrics": pipeline.perf.snapshot()}}
            await ws.send_text(json.dumps(msg, default=str))
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("websocket error", extra={"event": "WS_ERROR"})
    finally:
        bus.unsubscribe(queue)
