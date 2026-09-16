"""Traffic-signal simulator driven by the FSM state."""
from __future__ import annotations

import time
from typing import Dict, Optional

from .fsm import SignalState, TrafficSignalFSM

DIRECTIONS = ("NORTH", "SOUTH", "EAST", "WEST")
RED, YELLOW, GREEN = "RED", "YELLOW", "GREEN"


class SignalSimulator:
    """Maps FSM state + priority approach to per-direction lamp states."""

    def __init__(self, fsm: TrafficSignalFSM, normal_phase: float = 12.0,
                 yellow: float = 3.0):
        self.fsm = fsm
        self.normal_phase = normal_phase
        self.yellow = yellow

    def lights(self, now: Optional[float] = None) -> Dict[str, str]:
        now = now if now is not None else time.time()
        state = self.fsm.state
        approach = self.fsm.priority_approach

        if state is SignalState.EMERGENCY_GREEN and approach in DIRECTIONS:
            return {d: (GREEN if d == approach else RED) for d in DIRECTIONS}
        if state in (SignalState.ALL_RED, SignalState.CLEARANCE):
            return {d: RED for d in DIRECTIONS}
        if state is SignalState.PREPARE:
            # everything currently green goes amber before the all-red interval
            base = self._normal_lights(now)
            return {d: (YELLOW if base[d] == GREEN else RED) for d in DIRECTIONS}
        return self._normal_lights(now)

    def _normal_lights(self, now: float) -> Dict[str, str]:
        cycle = 2 * (self.normal_phase + self.yellow)
        t = now % cycle
        ns_green = t < self.normal_phase
        ns_yellow = self.normal_phase <= t < self.normal_phase + self.yellow
        ew_start = self.normal_phase + self.yellow
        ew_green = ew_start <= t < ew_start + self.normal_phase
        if ns_green:
            return {"NORTH": GREEN, "SOUTH": GREEN, "EAST": RED, "WEST": RED}
        if ns_yellow:
            return {"NORTH": YELLOW, "SOUTH": YELLOW, "EAST": RED, "WEST": RED}
        if ew_green:
            return {"NORTH": RED, "SOUTH": RED, "EAST": GREEN, "WEST": GREEN}
        return {"NORTH": RED, "SOUTH": RED, "EAST": YELLOW, "WEST": YELLOW}

    def snapshot(self, now: Optional[float] = None) -> dict:
        now = now if now is not None else time.time()
        fsm = self.fsm.snapshot(now)
        return {
            "fsm": fsm.to_dict(),
            "lights": self.lights(now),
            "priority_approach": fsm.priority_approach,
            "emergency": fsm.emergency_active,
            "simulated": True,
            "note": "Simulated signal head - not connected to real infrastructure.",
        }
