"""Tracker tests: persistent IDs, ageing, fail-safe behaviour."""
from __future__ import annotations

from app.core.types import Detection, FrameMeta
from app.tracking.bytetrack import ByteTrackTracker, greedy_match, iou


def det(cx, cy, conf=0.9, fid=1):
    return Detection("ambulance", conf, (cx - 30, cy - 20, cx + 30, cy + 20),
                     1000.0 + fid * 0.066, fid, "scripted", True)


def meta(fid):
    return FrameMeta(fid, 1000.0 + fid * 0.066, 960, 540, 15.0)


def test_iou_basic():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0


def test_greedy_match_handles_empty():
    m, ut, ud = greedy_match([], [], 0.3)
    assert (m, ut, ud) == ([], [], [])


def test_track_id_is_stable_across_frames():
    t = ByteTrackTracker(min_hits=2, max_age=5)
    ids = set()
    for i in range(30):
        tracks = t.update([det(400, 100 + i * 4, fid=i)], meta(i))
        ids.update(tr.track_id for tr in tracks)
    assert ids == {1}, f"track fragmented into {ids}"


def test_second_ambulance_receives_its_own_id():
    t = ByteTrackTracker(min_hits=2, max_age=5)
    for i in range(10):
        tracks = t.update([det(400, 100 + i * 4, fid=i), det(700, 300, fid=i)], meta(i))
    assert {tr.track_id for tr in tracks} == {1, 2}


def test_track_is_dropped_after_max_age():
    t = ByteTrackTracker(min_hits=2, max_age=3)
    for i in range(6):
        t.update([det(400, 100 + i * 4, fid=i)], meta(i))
    for i in range(6, 14):
        tracks = t.update([], meta(i))
    assert tracks == []
    assert 1 in t.lost_track_ids or not t.tracks


def test_low_confidence_detection_does_not_create_track():
    t = ByteTrackTracker(high_threshold=0.6, low_threshold=0.2, min_hits=2)
    for i in range(10):
        tracks = t.update([det(400, 100 + i * 3, conf=0.35, fid=i)], meta(i))
    assert tracks == [], "detections below the high threshold must not start a track"


def test_tracker_reports_active_status():
    t = ByteTrackTracker()
    t.update([], meta(1))
    assert t.status == "ACTIVE"
