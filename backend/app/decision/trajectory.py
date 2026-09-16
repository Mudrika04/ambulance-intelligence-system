"""Trajectory analysis: direction, image-space velocity, zone transitions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.types import MotionState, Track
from .roi import ROIManager


@dataclass
class TrajectoryInfo:
    motion_state: str = MotionState.UNCERTAIN.value
    closing_speed_px_s: float = 0.0     # >0 = moving toward intersection centre
    speed_px_s: float = 0.0
    confidence: float = 0.0
    points: List[Tuple[float, float]] = field(default_factory=list)
    zone_transitions: List[str] = field(default_factory=list)
    samples: int = 0

    def to_dict(self) -> dict:
        return {
            "motion_state": self.motion_state,
            "closing_speed_px_s": round(self.closing_speed_px_s, 2),
            "speed_px_s": round(self.speed_px_s, 2),
            "confidence": round(self.confidence, 3),
            "samples": self.samples,
            "zone_transitions": self.zone_transitions,
            "points": [[round(x, 1), round(y, 1)] for x, y in self.points[-60:]],
        }


class TrajectoryAnalyzer:
    def __init__(self, roi: ROIManager, min_points: int = 4,
                 stationary_speed: float = 6.0, consistency_min: float = 0.55):
        self.roi = roi
        self.min_points = min_points
        self.stationary_speed = stationary_speed
        self.consistency_min = consistency_min
        self._zones: Dict[int, List[str]] = {}

    def reset(self) -> None:
        self._zones.clear()

    def analyse(self, track: Track, width: int, height: int) -> TrajectoryInfo:
        pts = track.history
        info = TrajectoryInfo(samples=len(pts))
        info.points = [(p.cx, p.cy) for p in pts]
        if len(pts) < self.min_points:
            info.motion_state = MotionState.UNCERTAIN.value
            info.confidence = 0.0
            return info

        window = pts[-min(len(pts), 12):]
        cx0, cy0 = window[0].cx, window[0].cy
        cx1, cy1 = window[-1].cx, window[-1].cy
        dt = max(1e-3, window[-1].timestamp - window[0].timestamp)

        d0 = self.roi.distance_to_center(cx0, cy0, width, height)
        d1 = self.roi.distance_to_center(cx1, cy1, width, height)
        scale = min(width, height)
        info.closing_speed_px_s = ((d0 - d1) * scale) / dt
        info.speed_px_s = (((cx1 - cx0) ** 2 + (cy1 - cy0) ** 2) ** 0.5) / dt

        # direction consistency over consecutive samples
        signs = []
        for a, b in zip(window, window[1:]):
            da = self.roi.distance_to_center(a.cx, a.cy, width, height)
            db = self.roi.distance_to_center(b.cx, b.cy, width, height)
            if abs(da - db) * scale < 0.5:
                signs.append(0)
            else:
                signs.append(1 if db < da else -1)
        nonzero = [s for s in signs if s != 0]
        if nonzero:
            dominant = 1 if sum(nonzero) > 0 else -1
            consistency = sum(1 for s in nonzero if s == dominant) / len(nonzero)
        else:
            dominant, consistency = 0, 0.0
        info.confidence = round(consistency * min(1.0, len(window) / 8.0), 3)

        if abs(info.closing_speed_px_s) < self.stationary_speed and info.speed_px_s < self.stationary_speed:
            info.motion_state = MotionState.STATIONARY.value
        elif consistency < self.consistency_min:
            info.motion_state = MotionState.UNCERTAIN.value
        elif dominant > 0 and info.closing_speed_px_s > 0:
            info.motion_state = MotionState.APPROACHING.value
        elif dominant < 0 and info.closing_speed_px_s < 0:
            info.motion_state = MotionState.MOVING_AWAY.value
        else:
            info.motion_state = MotionState.UNCERTAIN.value

        # zone transitions
        zones = self._zones.setdefault(track.track_id, [])
        current = self.roi.zone_of(d1)
        if not zones or zones[-1] != current:
            zones.append(current)
        info.zone_transitions = zones[-8:]
        return info
