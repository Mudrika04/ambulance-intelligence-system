from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ..core.types import Detection, FrameMeta, Track


class Tracker(ABC):
    name = "tracker"

    @abstractmethod
    def update(self, detections: List[Detection], meta: FrameMeta) -> List[Track]:
        """Associate detections with existing tracks and return active tracks."""

    @abstractmethod
    def reset(self) -> None: ...

    @property
    def status(self) -> str:
        return "ACTIVE"
