"""Repository / persistence tests."""
from __future__ import annotations

import time

from app.core.types import Detection
from app.database.db import healthy
from app.database.repository import SQLiteRepository


def repo():
    return SQLiteRepository()


def test_database_initialises_and_reports_health():
    assert healthy() is True
    assert repo().status == "CONNECTED"


def test_system_event_roundtrip():
    r = repo()
    r.log_system_event("UNIT_TEST_EVENT", message="hello", track_id=99)
    events = r.recent_events(20)
    assert any(e["event_type"] == "UNIT_TEST_EVENT" for e in events)


def test_detection_and_track_persistence():
    r = repo()
    d = Detection("ambulance", 0.91, (1, 2, 3, 4), time.time(), 5, "scripted", True)
    r.log_detection(d, track_id=42)
    r.upsert_track(42, "NORTH", 0.91, True, True, time.time())
    r.upsert_track(42, "UNKNOWN", 0.70, False, True, time.time())
    stored = [t for t in r.tracks(50) if t["track_id"] == 42][0]
    assert stored["approach"] == "NORTH", "last known approach must be preserved"
    assert stored["validated"] is True
    assert stored["frames"] >= 2


def test_priority_and_signal_events_and_replay():
    r = repo()
    ts = time.time()
    r.log_priority_event(track_id=77, approach="NORTH", confidence=0.9,
                         proximity="NEAR", relative_eta=5.0, priority_score=0.83,
                         decision="PRIORITY_REQUESTED",
                         reason_codes=["AMBULANCE_DETECTED", "THRESHOLD_EXCEEDED"],
                         accepted=True, simulated=True, timestamp=ts)
    r.log_signal_event(from_state="NORMAL", signal_state="PREPARE",
                       reason="PRIORITY_REQUESTED", approach="NORTH", track_id=77)
    r.log_system_event("AMBULANCE_VALIDATED", track_id=77, timestamp=ts)
    r.log_trajectory_point(77, 10, 470.0, 120.0, 0.9, "NEAR_ZONE", "NORTH",
                           "NEAR", 5.0, ts)
    replay = r.replay(77)
    assert replay["timeline"] and replay["priority_events"] and replay["trajectory"]
    assert replay["priority_events"][0]["decision"] == "PRIORITY_REQUESTED"


def test_experiment_and_metric_persistence():
    r = repo()
    r.save_experiment(experiment_id="EXP-TEST01", scenario="unit", mode="simulation",
                      configuration={"a": 1}, results={"b": 2}, notes="simulation")
    r.save_metric("unit_metric", 1.23, "s", "EXP-TEST01")
    assert any(e["experiment_id"] == "EXP-TEST01" for e in r.experiments(10))
    assert any(m["name"] == "unit_metric" for m in r.metrics(50))
