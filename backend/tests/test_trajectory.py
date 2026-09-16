from __future__ import annotations

from app.core.types import MotionState, Track, TrackPoint
from app.decision.roi import ROIManager
from app.decision.trajectory import TrajectoryAnalyzer


def make_track(points, tid=1):
    tr = Track(track_id=tid, bbox=(0, 0, 10, 10), confidence=0.9, frame_id=len(points),
               timestamp=1000.0, hits=len(points), confirmed=True)
    tr.history = [TrackPoint(i, 1000.0 + i * 0.0667, x, y, 0.9)
                  for i, (x, y) in enumerate(points)]
    return tr


def analyser(cfg):
    return TrajectoryAnalyzer(ROIManager(cfg), min_points=4)


def test_approaching_detected(cfg):
    a = analyser(cfg)
    tr = make_track([(470, 40 + i * 12) for i in range(12)])
    info = a.analyse(tr, 960, 540)
    assert info.motion_state == MotionState.APPROACHING.value
    assert info.closing_speed_px_s > 0


def test_moving_away_detected(cfg):
    a = analyser(cfg)
    tr = make_track([(480, 300 - i * 12) for i in range(12)], tid=2)
    info = a.analyse(tr, 960, 540)
    assert info.motion_state == MotionState.MOVING_AWAY.value


def test_stationary_detected(cfg):
    a = analyser(cfg)
    tr = make_track([(470, 120) for _ in range(12)], tid=3)
    assert a.analyse(tr, 960, 540).motion_state == MotionState.STATIONARY.value


def test_insufficient_evidence_is_uncertain(cfg):
    a = analyser(cfg)
    tr = make_track([(470, 40), (470, 52)], tid=4)
    info = a.analyse(tr, 960, 540)
    assert info.motion_state == MotionState.UNCERTAIN.value
    assert info.confidence == 0.0


def test_zone_transitions_are_recorded(cfg):
    a = analyser(cfg)
    for i in range(6, 40, 3):
        tr = make_track([(470, 30 + k * 10) for k in range(i)], tid=5)
        info = a.analyse(tr, 960, 540)
    assert len(info.zone_transitions) >= 2
