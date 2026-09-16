"""The ten mandatory prototype scenarios.

Each test drives the real Pipeline object with a scripted detector, so the
detection -> tracking -> ROI -> validation -> trajectory -> proximity ->
priority -> decision -> FSM path is exercised exactly as it runs in production.
"""
from __future__ import annotations

import time

from conftest import approach_script, departing_script, run_frames
from app.traffic.fsm import SignalState


def _decisions(states):
    out = []
    for s in states:
        for a in s["ambulances"]:
            out.append(a["decision"]["decision"])
    return out


def test_1_single_frame_detection_does_not_activate_priority(pipeline_factory):
    script = [[]] * 3 + approach_script(1) + [[]] * 10
    p = pipeline_factory(script)
    states = run_frames(p, len(script))
    assert p.fsm.state is SignalState.NORMAL
    assert "PRIORITY_REQUESTED" not in _decisions(states)


def test_2_persistent_inbound_ambulance_passes_validation(pipeline_factory):
    p = pipeline_factory(approach_script(30))
    states = run_frames(p, 30)
    validated = [a for s in states for a in s["ambulances"] if a["validated"]]
    assert validated, "a persistent inbound ambulance must pass temporal validation"
    assert validated[0]["validation"]["frames"] >= p.validator.required_frames


def test_3_validated_inbound_ambulance_requests_priority(pipeline_factory):
    p = pipeline_factory(approach_script(30))
    states = run_frames(p, 30)
    assert "PRIORITY_REQUESTED" in _decisions(states)
    assert p.fsm.state is not SignalState.NORMAL
    assert p.fsm.priority_approach == "NORTH"


def test_4_outbound_ambulance_gets_no_priority(pipeline_factory):
    p = pipeline_factory(departing_script(30))
    states = run_frames(p, 30)
    assert "PRIORITY_REQUESTED" not in _decisions(states)
    assert p.fsm.state is SignalState.NORMAL


def test_5_low_confidence_gets_no_priority(pipeline_factory):
    p = pipeline_factory(approach_script(30, conf=0.35))
    states = run_frames(p, 30)
    assert all(not a["validated"] for s in states for a in s["ambulances"])
    assert p.fsm.state is SignalState.NORMAL


def test_6_lost_tracking_falls_back_safely(pipeline_factory):
    script = approach_script(30) + [[]] * 40
    p = pipeline_factory(script, **{"signal.emergency_green_max": 30})
    run_frames(p, len(script))
    # the ambulance vanished: the machine must not stay in EMERGENCY_GREEN
    assert p.fsm.state in (SignalState.CLEARANCE, SignalState.NORMAL,
                           SignalState.PREPARE, SignalState.ALL_RED)
    assert p.tracker.status == "ACTIVE"


def test_7_invalid_fsm_transition_is_rejected(pipeline_factory):
    p = pipeline_factory([[]])
    result = p.fsm.transition(SignalState.EMERGENCY_GREEN, "unsafe jump")
    assert not result.accepted
    assert p.fsm.state is SignalState.NORMAL


def test_8_conflicting_signal_request_is_rejected(pipeline_factory):
    p = pipeline_factory([[]])
    assert p.fsm.request_priority("NORTH", 1, 0.9).accepted
    second = p.fsm.request_priority("EAST", 2, 0.95)
    assert not second.accepted
    lights = p.signals.lights(time.time())
    assert list(lights.values()).count("GREEN") <= 1


def test_9_ambulance_clearing_the_intersection_triggers_clearance(pipeline_factory):
    # inbound until validated, then the same vehicle departs the far side
    script = approach_script(24, start_y=40, end_y=290) + \
        [[__import__("conftest").ambulance(470, 300 + i * 14)] for i in range(14)]
    p = pipeline_factory(script, **{"signal.prepare_duration": 0.01,
                                    "signal.all_red_duration": 0.01})
    states = run_frames(p, len(script), sleep=0.005)
    seen = {s["signal"]["fsm"]["state"] for s in states}
    assert "EMERGENCY_GREEN" in seen
    assert p.fsm.state in (SignalState.CLEARANCE, SignalState.NORMAL)


def test_10_clearance_completes_back_to_normal(pipeline_factory):
    p = pipeline_factory([[]] * 5, **{"signal.clearance_duration": 0.02})
    p.fsm.request_priority("NORTH", 1, 0.9)
    for _ in range(3):
        time.sleep(0.06)
        p.fsm.tick()
    assert p.fsm.state is SignalState.EMERGENCY_GREEN
    p.fsm.ambulance_cleared(1)
    time.sleep(0.06)
    p.fsm.tick()
    assert p.fsm.state is SignalState.NORMAL
    assert p.fsm.priority_approach is None
