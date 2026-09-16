"""Temporal validation, proximity, priority scoring and explainability."""
from __future__ import annotations

from app.core.types import Approach, MotionState
from app.decision.engine import DecisionEngine
from app.decision.priority import PriorityEngine
from app.decision.proximity import ProximityEstimator
from app.decision.roi import ROIManager
from app.decision.trajectory import TrajectoryInfo
from app.decision.validation import TemporalValidator


class FakeTrack:
    def __init__(self, tid=1, conf=0.9, confirmed=True):
        self.track_id, self.confidence, self.confirmed = tid, conf, confirmed


class FakeROI:
    def __init__(self, approach="NORTH", in_roi=True, zone="NEAR_ZONE"):
        self.approach, self.in_roi, self.zone = approach, in_roi, zone
        self.normalised_distance = 0.2


def traj(state=MotionState.APPROACHING.value, conf=0.9):
    t = TrajectoryInfo(motion_state=state, closing_speed_px_s=60.0, confidence=conf)
    t.samples = 12
    return t


def test_validation_requires_configured_frame_count():
    v = TemporalValidator(required_frames=5)
    for i in range(1, 5):
        st = v.update(FakeTrack(), FakeROI(), traj(), 1000.0 + i)
        assert not st.validated, f"validated too early at frame {i}"
    st = v.update(FakeTrack(), FakeROI(), traj(), 1005.0)
    assert st.validated and st.consecutive_frames == 5


def test_validation_resets_when_a_criterion_fails():
    v = TemporalValidator(required_frames=5)
    for i in range(4):
        v.update(FakeTrack(), FakeROI(), traj(), 1000.0 + i)
    st = v.update(FakeTrack(), FakeROI(approach=Approach.UNKNOWN.value, in_roi=False),
                  traj(), 1005.0)
    assert st.consecutive_frames == 0
    assert "OUTSIDE_ROI" in st.failures


def test_outbound_never_validates():
    v = TemporalValidator(required_frames=3)
    for i in range(10):
        st = v.update(FakeTrack(), FakeROI(), traj(MotionState.MOVING_AWAY.value), 1000.0 + i)
    assert not st.validated
    assert "MOTION_MOVING_AWAY" in st.failures


def test_low_confidence_never_validates():
    v = TemporalValidator(required_frames=3, min_confidence=0.55)
    for i in range(10):
        st = v.update(FakeTrack(conf=0.4), FakeROI(), traj(), 1000.0 + i)
    assert not st.validated and "LOW_CONFIDENCE" in st.failures


def test_priority_weights_are_normalised():
    e = PriorityEngine({"detection_confidence": 2.0, "eta_urgency": 2.0}, threshold=0.7)
    assert abs(sum(e.weights.values()) - 1.0) < 1e-6


def test_priority_score_bounds_and_threshold():
    e = PriorityEngine(threshold=0.7)
    high = e.score(detection_confidence=0.95, temporal_frames=5, required_frames=5,
                   approach_known=True, proximity_urgency=1.0, eta_urgency=1.0,
                   trajectory_confidence=0.9)
    low = e.score(detection_confidence=0.3, temporal_frames=0, required_frames=5,
                  approach_known=False, proximity_urgency=0.0, eta_urgency=0.0,
                  trajectory_confidence=0.0)
    assert 0.0 <= low.score <= high.score <= 1.0
    assert high.exceeds_threshold and not low.exceeds_threshold
    assert set(high.components) == set(high.weights)


def test_proximity_eta_is_labelled_as_camera_based(cfg):
    roi = ROIManager(cfg)
    est = ProximityEstimator(roi)
    info = est.estimate(470, 60, 960, 540, traj())
    assert info.calibrated is False
    assert "GPS" in info.note
    assert info.relative_eta_s is not None and info.relative_eta_s > 0


def test_eta_urgency_zero_when_not_closing(cfg):
    est = ProximityEstimator(ROIManager(cfg))
    info = est.estimate(470, 60, 960, 540,
                        TrajectoryInfo(motion_state=MotionState.MOVING_AWAY.value,
                                       closing_speed_px_s=-40.0))
    assert info.relative_eta_s is None
    assert est.eta_urgency(info) == 0.0


def test_decision_carries_reason_codes():
    v = TemporalValidator(required_frames=1)
    st = v.update(FakeTrack(), FakeROI(), traj(), 1000.0)
    prio = PriorityEngine(threshold=0.1).score(
        detection_confidence=0.9, temporal_frames=1, required_frames=1,
        approach_known=True, proximity_urgency=1.0, eta_urgency=1.0,
        trajectory_confidence=0.9)
    d = DecisionEngine().decide(track=FakeTrack(), roi_result=FakeROI(), trajectory=traj(),
                                proximity=type("P", (), {"proximity": "NEAR"})(),
                                validation=st, priority=prio)
    assert d.decision == "PRIORITY_REQUESTED"
    for code in ("AMBULANCE_DETECTED", "TRACK_PERSISTENT", "INBOUND_APPROACH",
                 "VALID_ROI", "HIGH_PROXIMITY", "THRESHOLD_EXCEEDED"):
        assert code in d.reason_codes
    assert len(d.reasons) == len(d.reason_codes)
