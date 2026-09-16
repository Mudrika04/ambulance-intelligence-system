"""Deterministic demo scenario.

A single source of truth for the synthetic demonstration:
* scripts/generate_sample_video.py renders these objects into an MP4
* DemoDetector samples the same script (with noise/dropouts) when no trained
  model is available
* scripts/evaluate_detection.py uses it as ground truth

Everything produced from this module is SIMULATED and is labelled as such
throughout the system. It is never presented as a real ML result.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

PERIOD_S = 30.0  # scenario loops every 30 seconds


@dataclass
class ScenarioObject:
    cls: str            # "ambulance" | "car"
    cx: float           # normalised centre x
    cy: float           # normalised centre y
    w: float            # normalised width
    h: float            # normalised height
    label: str = ""     # scenario phase label (documentation only)
    occluded: bool = False


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def objects_at(t: float) -> List[ScenarioObject]:
    """Ground-truth objects at scenario time t (seconds, auto-wrapped)."""
    t = t % PERIOD_S
    objs: List[ScenarioObject] = []

    # --- background traffic on the east-west carriageway -------------
    for i, (y, speed, phase) in enumerate(((0.505, 0.075, 0.0), (0.615, -0.062, 0.5))):
        x = (phase + speed * t) % 1.3 - 0.15
        if speed < 0:
            x = 1.15 - ((phase + abs(speed) * t) % 1.3)
        objs.append(ScenarioObject("car", x, y, 0.075, 0.048, f"car{i}"))

    # --- phase A: inbound ambulance on the NORTH approach ------------
    if 3.0 <= t < 15.0:
        p = (t - 3.0) / 12.0
        cy = _lerp(-0.06, 1.06, p)
        cx = 0.485 + 0.012 * (p - 0.5)
        size = _lerp(0.070, 0.115, p)
        occluded = 6.0 <= t < 6.7          # short occlusion / detection loss
        objs.append(ScenarioObject("ambulance", cx, cy, size, size * 0.78,
                                   "inbound_north", occluded))

    # --- phase B: outbound ambulance leaving via the EAST approach ---
    if 21.0 <= t < 28.0:
        p = (t - 21.0) / 7.0
        cx = _lerp(0.52, 1.10, p)
        cy = 0.545
        size = _lerp(0.100, 0.070, p)
        objs.append(ScenarioObject("ambulance", cx, cy, size, size * 0.78,
                                   "outbound_east"))

    return [o for o in objs if -0.2 < o.cx < 1.2 and -0.2 < o.cy < 1.2]


def to_pixel_bbox(o: ScenarioObject, width: int, height: int) -> Tuple[float, float, float, float]:
    x1 = (o.cx - o.w / 2) * width
    y1 = (o.cy - o.h / 2) * height
    x2 = (o.cx + o.w / 2) * width
    y2 = (o.cy + o.h / 2) * height
    return (x1, y1, x2, y2)
