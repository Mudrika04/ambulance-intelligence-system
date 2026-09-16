"""Temporal validation: a single-frame detection can never trigger priority."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..core.types import Approach, MotionState


@dataclass
class ValidationState:
    track_id: int
    consecutive_frames: int = 0
    validated: bool = False
    first_seen: float = 0.0
    validated_at: float = 0.0
    approach: str = Approach.UNKNOWN.value
    failures: List[str] = field(default_factory=list)

    @property
    def consistency(self) -> float:
        return self.consecutive_frames

    def to_dict(self, required: int) -> dict:
        return {
            "track_id": self.track_id,
            "frames": self.consecutive_frames,
            "required_frames": required,
            "validated": self.validated,
            "approach": self.approach,
            "failures": self.failures,
        }


class TemporalValidator:
    """Counts consecutive frames where a track satisfies every criterion.

    `required_frames` is a configurable prototype parameter. It has NOT been
    experimentally established as an optimum.
    """

    def __init__(self, required_frames: int = 5, min_confidence: float = 0.55,
                 require_inbound: bool = True, require_roi: bool = True):
        self.required_frames = required_frames
        self.min_confidence = min_confidence
        self.require_inbound = require_inbound
        self.require_roi = require_roi
        self._states: Dict[int, ValidationState] = {}

    def reset(self) -> None:
        self._states.clear()

    def drop(self, track_id: int) -> None:
        self._states.pop(track_id, None)

    def state(self, track_id: int) -> ValidationState | None:
        return self._states.get(track_id)

    def update(self, track, roi_result, trajectory, timestamp: float) -> ValidationState:
        st = self._states.get(track.track_id)
        if st is None:
            st = ValidationState(track_id=track.track_id, first_seen=timestamp)
            self._states[track.track_id] = st

        failures: List[str] = []
        if not track.confirmed:
            failures.append("TRACK_NOT_CONFIRMED")
        if track.confidence < self.min_confidence:
            failures.append("LOW_CONFIDENCE")
        if self.require_roi and not roi_result.in_roi:
            failures.append("OUTSIDE_ROI")
        if roi_result.approach == Approach.UNKNOWN.value:
            failures.append("APPROACH_UNKNOWN")
        if st.approach not in (Approach.UNKNOWN.value, roi_result.approach):
            failures.append("APPROACH_CHANGED")
        if self.require_inbound and trajectory.motion_state != MotionState.APPROACHING.value:
            failures.append(f"MOTION_{trajectory.motion_state}")

        st.failures = failures
        st.approach = roi_result.approach
        if failures:
            st.consecutive_frames = 0
            st.validated = False
            st.validated_at = 0.0
        else:
            st.consecutive_frames += 1
            if st.consecutive_frames >= self.required_frames and not st.validated:
                st.validated = True
                st.validated_at = timestamp
        return st
