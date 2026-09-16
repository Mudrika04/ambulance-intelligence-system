"""In-process event bus bridging the pipeline thread and WebSocket clients."""
from __future__ import annotations

import asyncio
import threading
from typing import Any, Dict, List, Optional


class EventBus:
    def __init__(self, maxsize: int = 200):
        self._queues: List[asyncio.Queue] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()
        self._maxsize = maxsize

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        with self._lock:
            self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            if q in self._queues:
                self._queues.remove(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._queues)

    def publish(self, type_: str, payload: Dict[str, Any]) -> None:
        """Thread-safe publish from the pipeline worker thread."""
        msg = {"type": type_, "payload": payload}
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        with self._lock:
            queues = list(self._queues)
        for q in queues:
            def _put(q=q, msg=msg):
                if q.full():
                    try:
                        q.get_nowait()
                    except Exception:
                        pass
                try:
                    q.put_nowait(msg)
                except Exception:
                    pass
            try:
                loop.call_soon_threadsafe(_put)
            except RuntimeError:
                pass
