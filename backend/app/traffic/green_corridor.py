"""PROTOTYPE GREEN CORRIDOR SIMULATION.

Coordinates a chain of three simulated intersections. Nothing here is connected
to real traffic infrastructure; every state is a simulation.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

from .fsm import SignalState

MONITOR = "MONITOR"
PREPARE = "PREPARE"
ACTIVE_PRIORITY = "ACTIVE_PRIORITY"
CLEARED = "CLEARED"

HANDOVER_SECONDS = 6.0   # simulated travel time between intersections


class GreenCorridor:
    def __init__(self, intersections: List[dict], handover_s: float = HANDOVER_SECONDS):
        self.intersections = intersections or []
        self.handover_s = handover_s
        self._status: Dict[str, str] = {i["id"]: MONITOR for i in self.intersections}
        self._active_index = 0
        self._cleared_at: Optional[float] = None
        self.simulated = True

    def reset(self) -> None:
        self._status = {i["id"]: MONITOR for i in self.intersections}
        self._active_index = 0
        self._cleared_at = None

    def update(self, fsm_state: str, approach: Optional[str],
               now: Optional[float] = None) -> Dict[str, str]:
        now = now if now is not None else time.time()
        ids = [i["id"] for i in self.intersections]
        if not ids:
            return {}

        if fsm_state in (SignalState.PREPARE.value, SignalState.ALL_RED.value,
                         SignalState.EMERGENCY_GREEN.value):
            self._cleared_at = None
            idx = self._active_index
            for k, iid in enumerate(ids):
                if k == idx:
                    self._status[iid] = ACTIVE_PRIORITY
                elif k == idx + 1:
                    self._status[iid] = PREPARE
                else:
                    self._status[iid] = MONITOR
        elif fsm_state == SignalState.CLEARANCE.value:
            if self._cleared_at is None:
                self._cleared_at = now
            idx = self._active_index
            self._status[ids[idx]] = CLEARED
            if idx + 1 < len(ids):
                self._status[ids[idx + 1]] = ACTIVE_PRIORITY
            if idx + 2 < len(ids):
                self._status[ids[idx + 2]] = PREPARE
            # simulated progression downstream
            if now - self._cleared_at >= self.handover_s and idx + 1 < len(ids):
                self._active_index += 1
                self._cleared_at = now
        else:
            self.reset()
        return dict(self._status)

    def snapshot(self) -> dict:
        return {
            "label": "PROTOTYPE GREEN CORRIDOR SIMULATION",
            "simulated": True,
            "intersections": [
                {"id": i["id"], "name": i.get("name", i["id"]),
                 "role": i.get("role", "downstream"),
                 "status": self._status.get(i["id"], MONITOR)}
                for i in self.intersections
            ],
        }
