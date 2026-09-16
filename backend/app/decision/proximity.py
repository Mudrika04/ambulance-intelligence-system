"""Camera-based proximity and relative ETA.

IMPORTANT: this is an image-space prototype estimate produced from ROI zone
membership and observed pixel motion. Without camera calibration it is NOT a
metric distance and NOT equivalent to GPS-level positioning. The API and the
dashboard always carry that qualifier.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..core.types import Proximity, Zone
from .roi import ROIManager
from .trajectory import TrajectoryInfo

ESTIMATE_NOTE = ("Camera-based relative ETA estimate (image-space). "
                 "Not equivalent to GPS-level positioning.")

ZONE_TO_PROXIMITY = {
    Zone.CLEARANCE_ZONE.value: Proximity.NEAR.value,
    Zone.CONTROL_ZONE.value: Proximity.NEAR.value,
    Zone.NEAR_ZONE.value: Proximity.NEAR.value,
    Zone.MEDIUM_ZONE.value: Proximity.MEDIUM.value,
    Zone.FAR_ZONE.value: Proximity.FAR.value,
    Zone.OUTSIDE.value: Proximity.UNKNOWN.value,
}


@dataclass
class ProximityInfo:
    proximity: str = Proximity.UNKNOWN.value
    relative_eta_s: Optional[float] = None
    zone: str = Zone.OUTSIDE.value
    note: str = ESTIMATE_NOTE
    calibrated: bool = False

    def to_dict(self) -> dict:
        return {
            "proximity": self.proximity,
            "relative_eta_s": None if self.relative_eta_s is None else round(self.relative_eta_s, 1),
            "zone": self.zone,
            "calibrated": self.calibrated,
            "note": self.note,
        }


class ProximityEstimator:
    def __init__(self, roi: ROIManager, near_eta: float = 6.0,
                 medium_eta: float = 15.0, max_eta: float = 120.0):
        self.roi = roi
        self.near_eta = near_eta
        self.medium_eta = medium_eta
        self.max_eta = max_eta

    def estimate(self, cx: float, cy: float, width: int, height: int,
                 trajectory: TrajectoryInfo) -> ProximityInfo:
        d = self.roi.distance_to_center(cx, cy, width, height)
        zone = self.roi.zone_of(d)
        info = ProximityInfo(proximity=ZONE_TO_PROXIMITY.get(zone, Proximity.UNKNOWN.value),
                             zone=zone)
        scale = min(width, height)
        remaining_px = max(0.0, (d - self.roi.control_radius) * scale)
        closing = trajectory.closing_speed_px_s
        if closing > 1e-3:
            eta = remaining_px / closing
            info.relative_eta_s = min(self.max_eta, max(0.0, eta))
        return info

    def eta_urgency(self, info: ProximityInfo) -> float:
        """Normalised 0..1 urgency derived from the relative ETA."""
        if info.relative_eta_s is None:
            return 0.0
        eta = info.relative_eta_s
        if eta <= self.near_eta:
            return 1.0
        if eta >= self.medium_eta * 2:
            return 0.0
        span = (self.medium_eta * 2) - self.near_eta
        return max(0.0, min(1.0, 1.0 - (eta - self.near_eta) / span))

    @staticmethod
    def proximity_urgency(info: ProximityInfo) -> float:
        return {Proximity.NEAR.value: 1.0, Proximity.MEDIUM.value: 0.6,
                Proximity.FAR.value: 0.25}.get(info.proximity, 0.0)
