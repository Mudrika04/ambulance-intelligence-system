"""Runtime performance measurement. Values are measured, never asserted."""
from __future__ import annotations

import statistics
import time
from collections import deque
from typing import Deque, Dict, Optional


class RollingMetric:
    def __init__(self, maxlen: int = 240):
        self.values: Deque[float] = deque(maxlen=maxlen)

    def add(self, v: float) -> None:
        self.values.append(v)

    def summary(self) -> Dict[str, Optional[float]]:
        if not self.values:
            return {"mean": None, "p95": None, "last": None, "samples": 0}
        vals = sorted(self.values)
        idx = max(0, int(0.95 * len(vals)) - 1)
        return {
            "mean": round(statistics.fmean(self.values), 2),
            "p95": round(vals[idx], 2),
            "last": round(self.values[-1], 2),
            "samples": len(self.values),
        }


class PerformanceMonitor:
    NAMES = ("detection_ms", "tracking_ms", "decision_ms", "end_to_end_ms", "fps")

    def __init__(self):
        self.metrics: Dict[str, RollingMetric] = {n: RollingMetric() for n in self.NAMES}
        self._last_frame_ts: Optional[float] = None
        self.frames = 0
        self.started_at: Optional[float] = None

    def start(self) -> None:
        self.started_at = time.time()
        self.frames = 0
        self._last_frame_ts = None
        for m in self.metrics.values():
            m.values.clear()

    def record(self, name: str, value: float) -> None:
        if name in self.metrics:
            self.metrics[name].add(value)

    def frame_done(self) -> None:
        now = time.perf_counter()
        self.frames += 1
        if self._last_frame_ts is not None:
            dt = now - self._last_frame_ts
            if dt > 0:
                self.record("fps", 1.0 / dt)
        self._last_frame_ts = now

    def snapshot(self) -> dict:
        out = {name: m.summary() for name, m in self.metrics.items()}
        out["frames_processed"] = self.frames
        out["uptime_s"] = round(time.time() - self.started_at, 1) if self.started_at else 0.0
        out["measured"] = self.frames > 0
        return out
