"""Decision engine: turns pipeline evidence into an explainable decision."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..core.types import Approach, MotionState, Proximity

REASON_TEXT = {
    "AMBULANCE_DETECTED": "Ambulance detected",
    "TRACK_PERSISTENT": "Persistent tracking across frames",
    "INBOUND_APPROACH": "Inbound movement toward the intersection",
    "VALID_ROI": "Inside a configured approach ROI",
    "APPROACH_IDENTIFIED": "Approach identified",
    "HIGH_PROXIMITY": "High proximity urgency",
    "THRESHOLD_EXCEEDED": "Priority threshold exceeded",
    "NOT_VALIDATED": "Temporal validation not yet satisfied",
    "SINGLE_FRAME_ONLY": "Detection not persistent across frames",
    "LOW_CONFIDENCE": "Detection confidence below the configured minimum",
    "OUTSIDE_ROI": "Outside every configured approach ROI",
    "APPROACH_UNKNOWN": "Approach could not be identified",
    "MOTION_MOVING_AWAY": "Ambulance is moving away from the intersection",
    "MOTION_STATIONARY": "Ambulance is stationary",
    "MOTION_UNCERTAIN": "Movement direction is uncertain",
    "TRACK_NOT_CONFIRMED": "Track not yet confirmed by the tracker",
    "APPROACH_CHANGED": "Approach changed during validation",
    "BELOW_THRESHOLD": "Priority score below the configured threshold",
}


@dataclass
class DecisionExplanation:
    decision: str                       # PRIORITY_REQUESTED | MONITORING | NO_PRIORITY
    reason_codes: List[str] = field(default_factory=list)
    track_id: int | None = None
    approach: str = Approach.UNKNOWN.value
    priority_score: float = 0.0
    threshold: float = 0.0

    @property
    def reasons(self) -> List[str]:
        return [REASON_TEXT.get(c, c) for c in self.reason_codes]

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason_codes": self.reason_codes,
            "reasons": self.reasons,
            "track_id": self.track_id,
            "approach": self.approach,
            "priority_score": round(self.priority_score, 3),
            "threshold": self.threshold,
        }


class DecisionEngine:
    def decide(self, *, track, roi_result, trajectory, proximity, validation,
               priority) -> DecisionExplanation:
        codes: List[str] = ["AMBULANCE_DETECTED"]

        if validation.validated:
            codes.append("TRACK_PERSISTENT")
        elif validation.consecutive_frames <= 1:
            codes.append("SINGLE_FRAME_ONLY")
        else:
            codes.append("NOT_VALIDATED")

        for f in validation.failures:
            if f not in codes:
                codes.append(f)

        if roi_result.in_roi:
            codes.append("VALID_ROI")
        if roi_result.approach != Approach.UNKNOWN.value:
            codes.append("APPROACH_IDENTIFIED")
        if trajectory.motion_state == MotionState.APPROACHING.value:
            codes.append("INBOUND_APPROACH")
        if proximity.proximity == Proximity.NEAR.value:
            codes.append("HIGH_PROXIMITY")

        if priority.exceeds_threshold:
            codes.append("THRESHOLD_EXCEEDED")
        else:
            codes.append("BELOW_THRESHOLD")

        if validation.validated and priority.exceeds_threshold:
            decision = "PRIORITY_REQUESTED"
        elif validation.consecutive_frames > 0:
            decision = "MONITORING"
        else:
            decision = "NO_PRIORITY"

        return DecisionExplanation(
            decision=decision,
            reason_codes=codes,
            track_id=track.track_id,
            approach=roi_result.approach,
            priority_score=priority.score,
            threshold=priority.threshold,
        )
