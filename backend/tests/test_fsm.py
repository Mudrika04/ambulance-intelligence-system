"""Deterministic signal FSM and simulator."""
from __future__ import annotations

import pytest

from app.traffic.fsm import SignalState, TrafficSignalFSM
from app.traffic.green_corridor import ACTIVE_PRIORITY, MONITOR, PREPARE, GreenCorridor
from app.traffic.signal_simulator import SignalSimulator


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


@pytest.fixture
def fsm():
    clock = Clock()
    machine = TrafficSignalFSM(prepare_duration=3, all_red_duration=2,
                               emergency_green_max=10, clearance_duration=5,
                               clock=clock)
    machine.clock = clock
    return machine


def test_starts_in_normal(fsm):
    assert fsm.state is SignalState.NORMAL


def test_direct_jump_to_emergency_green_is_rejected(fsm):
    result = fsm.transition(SignalState.EMERGENCY_GREEN, "unsafe")
    assert not result.accepted
    assert fsm.state is SignalState.NORMAL
    assert fsm.rejected_requests == 1


def test_full_valid_sequence(fsm):
    assert fsm.request_priority("NORTH", 7, 0.9).accepted
    assert fsm.state is SignalState.PREPARE
    fsm.clock.advance(3)
    fsm.tick()
    assert fsm.state is SignalState.ALL_RED
    fsm.clock.advance(2)
    fsm.tick()
    assert fsm.state is SignalState.EMERGENCY_GREEN
    assert fsm.ambulance_cleared(7).accepted
    assert fsm.state is SignalState.CLEARANCE
    fsm.clock.advance(5)
    fsm.tick()
    assert fsm.state is SignalState.NORMAL
    assert fsm.priority_approach is None


def test_conflicting_request_is_rejected(fsm):
    fsm.request_priority("NORTH", 1, 0.9)
    result = fsm.request_priority("EAST", 2, 0.95)
    assert not result.accepted and result.reason == "REQUEST_REJECTED"
    assert fsm.priority_approach == "NORTH"


def test_repeat_request_from_same_track_is_idempotent(fsm):
    fsm.request_priority("NORTH", 1, 0.9)
    assert fsm.request_priority("NORTH", 1, 0.9).reason == "ALREADY_ACTIVE"


def test_clearance_only_from_emergency_green(fsm):
    assert not fsm.ambulance_cleared(1).accepted
    fsm.request_priority("NORTH", 1, 0.9)
    assert not fsm.ambulance_cleared(1).accepted


def test_emergency_green_times_out(fsm):
    fsm.request_priority("NORTH", 1, 0.9)
    fsm.clock.advance(3); fsm.tick()
    fsm.clock.advance(2); fsm.tick()
    assert fsm.state is SignalState.EMERGENCY_GREEN
    fsm.clock.advance(10)
    fsm.tick()
    assert fsm.state is SignalState.CLEARANCE


def test_abort_returns_to_normal_safely(fsm):
    fsm.request_priority("NORTH", 1, 0.9)
    assert fsm.abort("TRACK_LOST").accepted
    assert fsm.state is SignalState.NORMAL


def test_simulator_gives_green_only_to_the_priority_approach(fsm):
    fsm.request_priority("NORTH", 1, 0.9)
    fsm.clock.advance(3); fsm.tick()
    fsm.clock.advance(2); fsm.tick()
    sim = SignalSimulator(fsm)
    lights = sim.lights(fsm.clock())
    assert lights["NORTH"] == "GREEN"
    assert all(lights[d] == "RED" for d in ("SOUTH", "EAST", "WEST"))


def test_simulator_all_red_has_no_green(fsm):
    fsm.request_priority("NORTH", 1, 0.9)
    fsm.clock.advance(3); fsm.tick()
    sim = SignalSimulator(fsm)
    assert set(sim.lights(fsm.clock()).values()) == {"RED"}


def test_green_corridor_progresses_downstream():
    gc = GreenCorridor([{"id": "INT-01"}, {"id": "INT-02"}, {"id": "INT-03"}])
    status = gc.update(SignalState.EMERGENCY_GREEN.value, "NORTH", 1000.0)
    assert status == {"INT-01": ACTIVE_PRIORITY, "INT-02": PREPARE, "INT-03": MONITOR}
    status = gc.update(SignalState.CLEARANCE.value, "NORTH", 1001.0)
    assert status["INT-01"] == "CLEARED" and status["INT-02"] == ACTIVE_PRIORITY
    assert gc.snapshot()["simulated"] is True


def test_green_corridor_resets_on_normal():
    gc = GreenCorridor([{"id": "INT-01"}, {"id": "INT-02"}])
    gc.update(SignalState.EMERGENCY_GREEN.value, "NORTH", 1000.0)
    status = gc.update(SignalState.NORMAL.value, None, 1002.0)
    assert set(status.values()) == {MONITOR}
