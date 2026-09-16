"""Configurable intersection ROIs, approaches and proximity zones."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from ..core.types import Approach, Zone

ZONE_ORDER = [Zone.CLEARANCE_ZONE, Zone.CONTROL_ZONE, Zone.NEAR_ZONE,
              Zone.MEDIUM_ZONE, Zone.FAR_ZONE]


def point_in_polygon(px: float, py: float, poly: List[Tuple[float, float]]) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            xin = (x2 - x1) * (py - y1) / (y2 - y1 + 1e-12) + x1
            if px < xin:
                inside = not inside
    return inside


@dataclass
class ROIResult:
    approach: str
    zone: str
    normalised_distance: float     # 0 = intersection centre, 1 = frame corner
    in_roi: bool


class ROIManager:
    """Holds normalised ROI geometry; converts to pixels on demand."""

    def __init__(self, cfg):
        self.center = tuple(cfg.get("roi.intersection_center", [0.5, 0.5]))
        self.approaches: Dict[str, List[Tuple[float, float]]] = {
            k: [tuple(p) for p in v] for k, v in (cfg.get("roi.approaches") or {}).items()
        }
        self.zones: Dict[str, float] = dict(cfg.get("roi.zones") or {})
        self.control_radius = float(cfg.get("roi.control_radius", 0.13))

    # --- geometry ----------------------------------------------------
    def normalised(self, cx: float, cy: float, width: int, height: int) -> Tuple[float, float]:
        return (cx / max(1, width), cy / max(1, height))

    def distance_to_center(self, cx: float, cy: float, width: int, height: int) -> float:
        nx, ny = self.normalised(cx, cy, width, height)
        return math.hypot(nx - self.center[0], ny - self.center[1])

    def zone_of(self, distance: float) -> str:
        for zone in ZONE_ORDER:
            radius = self.zones.get(zone.value)
            if radius is not None and distance <= radius:
                return zone.value
        return Zone.OUTSIDE.value

    def approach_of(self, cx: float, cy: float, width: int, height: int) -> str:
        nx, ny = self.normalised(cx, cy, width, height)
        for name, poly in self.approaches.items():
            if point_in_polygon(nx, ny, poly):
                return name
        return Approach.UNKNOWN.value

    def classify(self, cx: float, cy: float, width: int, height: int) -> ROIResult:
        d = self.distance_to_center(cx, cy, width, height)
        zone = self.zone_of(d)
        approach = self.approach_of(cx, cy, width, height)
        in_roi = approach != Approach.UNKNOWN.value or zone in (
            Zone.CONTROL_ZONE.value, Zone.CLEARANCE_ZONE.value, Zone.NEAR_ZONE.value)
        return ROIResult(approach=approach, zone=zone, normalised_distance=d, in_roi=in_roi)

    # --- rendering helpers -------------------------------------------
    def polygons_px(self, width: int, height: int) -> Dict[str, np.ndarray]:
        return {name: np.array([[int(x * width), int(y * height)] for x, y in poly],
                               dtype=np.int32)
                for name, poly in self.approaches.items()}

    def center_px(self, width: int, height: int) -> Tuple[int, int]:
        return int(self.center[0] * width), int(self.center[1] * height)

    def zone_radii_px(self, width: int, height: int) -> Dict[str, int]:
        scale = min(width, height)
        return {k: int(v * scale) for k, v in self.zones.items()}

    def to_dict(self) -> dict:
        return {"center": list(self.center), "approaches": {k: [list(p) for p in v]
                for k, v in self.approaches.items()}, "zones": self.zones}
