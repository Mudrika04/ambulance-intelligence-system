"""Explainable weighted priority scoring."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

DEFAULT_WEIGHTS = {
    "detection_confidence": 0.20,
    "temporal_consistency": 0.20,
    "approach_certainty": 0.15,
    "proximity_urgency": 0.20,
    "eta_urgency": 0.15,
    "trajectory_confidence": 0.10,
}


@dataclass
class PriorityResult:
    score: float
    threshold: float
    components: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    exceeds_threshold: bool = False

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 3),
            "threshold": self.threshold,
            "exceeds_threshold": self.exceeds_threshold,
            "components": {k: round(v, 3) for k, v in self.components.items()},
            "weights": self.weights,
            "contributions": {k: round(self.weights.get(k, 0) * v, 3)
                              for k, v in self.components.items()},
        }


class PriorityEngine:
    """PriorityScore = Σ wi * normalised_component_i.

    The weights and threshold are configurable prototype values. They are not
    claimed to be optimal and must be validated experimentally.
    """

    def __init__(self, weights: Dict[str, float] | None = None, threshold: float = 0.70):
        w = dict(DEFAULT_WEIGHTS)
        w.update(weights or {})
        total = sum(w.values()) or 1.0
        self.weights = {k: round(v / total, 4) for k, v in w.items()}
        self.threshold = threshold

    @staticmethod
    def _clamp(v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    def score(self, *, detection_confidence: float, temporal_frames: int,
              required_frames: int, approach_known: bool, proximity_urgency: float,
              eta_urgency: float, trajectory_confidence: float) -> PriorityResult:
        components = {
            "detection_confidence": self._clamp(detection_confidence),
            "temporal_consistency": self._clamp(
                temporal_frames / max(1, required_frames)),
            "approach_certainty": 1.0 if approach_known else 0.0,
            "proximity_urgency": self._clamp(proximity_urgency),
            "eta_urgency": self._clamp(eta_urgency),
            "trajectory_confidence": self._clamp(trajectory_confidence),
        }
        total = sum(self.weights.get(k, 0.0) * v for k, v in components.items())
        return PriorityResult(score=round(total, 4), threshold=self.threshold,
                              components=components, weights=self.weights,
                              exceeds_threshold=total >= self.threshold)
