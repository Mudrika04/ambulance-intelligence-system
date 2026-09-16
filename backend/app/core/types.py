"""Core domain types shared by every layer."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

BBox = Tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels


class Approach(str, Enum):
    NORTH = "NORTH"
    SOUTH = "SOUTH"
    EAST = "EAST"
    WEST = "WEST"
    UNKNOWN = "UNKNOWN"


class Zone(str, Enum):
    FAR_ZONE = "FAR_ZONE"
    MEDIUM_ZONE = "MEDIUM_ZONE"
    NEAR_ZONE = "NEAR_ZONE"
    CONTROL_ZONE = "CONTROL_ZONE"
    CLEARANCE_ZONE = "CLEARANCE_ZONE"
    OUTSIDE = "OUTSIDE"


class MotionState(str, Enum):
    APPROACHING = "APPROACHING"
    STATIONARY = "STATIONARY"
    MOVING_AWAY = "MOVING_AWAY"
    UNCERTAIN = "UNCERTAIN"


class Proximity(str, Enum):
    FAR = "FAR"
    MEDIUM = "MEDIUM"
    NEAR = "NEAR"
    UNKNOWN = "UNKNOWN"


class SourceKind(str, Enum):
    FILE = "file"
    WEBCAM = "webcam"
    RTSP = "rtsp"


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox: BBox
    timestamp: float
    frame_id: int
    source: str = "unknown"      # "yolo" or "demo-simulation"
    simulated: bool = False

    @property
    def centroid(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def to_dict(self) -> dict:
        return {
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": [round(v, 1) for v in self.bbox],
            "timestamp": self.timestamp,
            "frame_id": self.frame_id,
            "source": self.source,
            "simulated": self.simulated,
        }


@dataclass
class TrackPoint:
    frame_id: int
    timestamp: float
    cx: float
    cy: float
    confidence: float
    zone: str = Zone.OUTSIDE.value
    approach: str = Approach.UNKNOWN.value


@dataclass
class Track:
    track_id: int
    bbox: BBox
    confidence: float
    frame_id: int
    timestamp: float
    hits: int = 0
    age: int = 0
    time_since_update: int = 0
    confirmed: bool = False
    history: List[TrackPoint] = field(default_factory=list)

    @property
    def centroid(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "bbox": [round(v, 1) for v in self.bbox],
            "confidence": round(self.confidence, 4),
            "hits": self.hits,
            "age": self.age,
            "time_since_update": self.time_since_update,
            "confirmed": self.confirmed,
        }


@dataclass
class FrameMeta:
    frame_id: int
    timestamp: float
    width: int
    height: int
    fps: float
    source_status: str = "ONLINE"


def now() -> float:
    return time.time()
