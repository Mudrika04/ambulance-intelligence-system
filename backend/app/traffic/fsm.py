"""Deterministic traffic-signal finite state machine.

The AI layer only *requests* priority. This deterministic safety layer decides
whether a transition is permitted. Invalid transitions are always rejected and
logged; the machine can never sit in an undefined state.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple


class SignalState(str, Enum):
    NORMAL = "NORMAL"
    PREPARE = "PREPARE"
    ALL_RED = "ALL_RED"
    EMERGENCY_GREEN = "EMERGENCY_GREEN"
    CLEARANCE = "CLEARANCE"


# Forward path plus explicit fail-safe aborts back to NORMAL.
ALLOWED: Dict[SignalState, Tuple[SignalState, ...]] = {
    SignalState.NORMAL: (SignalState.PREPARE,),
    SignalState.PREPARE: (SignalState.ALL_RED, SignalState.NORMAL),
    SignalState.ALL_RED: (SignalState.EMERGENCY_GREEN, SignalState.NORMAL),
    SignalState.EMERGENCY_GREEN: (SignalState.CLEARANCE,),
    SignalState.CLEARANCE: (SignalState.NORMAL,),
}


@dataclass
class TransitionResult:
    accepted: bool
    state: str
    reason: str
    previous: str = ""

    def to_dict(self) -> dict:
        return {"accepted": self.accepted, "state": self.state,
                "reason": self.reason, "previous": self.previous}


@dataclass
class FSMSnapshot:
    state: str
    priority_approach: Optional[str]
    track_id: Optional[int]
    phase_elapsed: float
    phase_duration: float
    remaining: float
    emergency_active: bool
    rejected_requests: int

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "priority_approach": self.priority_approach,
            "track_id": self.track_id,
            "phase_elapsed": round(self.phase_elapsed, 1),
            "phase_duration": round(self.phase_duration, 1),
            "remaining": round(self.remaining, 1),
            "emergency_active": self.emergency_active,
            "rejected_requests": self.rejected_requests,
        }


class TrafficSignalFSM:
    def __init__(self, prepare_duration: float = 3, all_red_duration: float = 2,
                 emergency_green_max: float = 25, clearance_duration: float = 5,
                 normal_phase_duration: float = 12,
                 on_event: Optional[Callable[[str, dict], None]] = None,
                 clock: Callable[[], float] = time.time):
        self.durations = {
            SignalState.NORMAL: float(normal_phase_duration),
            SignalState.PREPARE: float(prepare_duration),
            SignalState.ALL_RED: float(all_red_duration),
            SignalState.EMERGENCY_GREEN: float(emergency_green_max),
            SignalState.CLEARANCE: float(clearance_duration),
        }
        self._clock = clock
        self._on_event = on_event or (lambda *_: None)
        self.state = SignalState.NORMAL
        self.priority_approach: Optional[str] = None
        self.track_id: Optional[int] = None
        self.entered_at = self._clock()
        self.rejected_requests = 0
        self.episode = 0          # increments on every accepted priority sequence
        self.history: List[dict] = []
        self._cleared = False

    # ------------------------------------------------------------------
    def can_transition(self, target: SignalState) -> bool:
        return target in ALLOWED.get(self.state, ())

    def transition(self, target: SignalState, reason: str = "") -> TransitionResult:
        previous = self.state
        if not self.can_transition(target):
            self.rejected_requests += 1
            self._emit("TRANSITION_REJECTED",
                       {"from": previous.value, "to": target.value, "reason": reason})
            return TransitionResult(False, previous.value,
                                    f"INVALID_TRANSITION {previous.value}->{target.value}",
                                    previous.value)
        self.state = target
        self.entered_at = self._clock()
        self.history.append({"from": previous.value, "to": target.value,
                             "at": self.entered_at, "reason": reason})
        self._emit(f"FSM_{target.value}", {"from": previous.value, "reason": reason,
                                           "approach": self.priority_approach})
        if target is SignalState.NORMAL:
            self.priority_approach = None
            self.track_id = None
            self._cleared = False
        return TransitionResult(True, target.value, reason or "OK", previous.value)

    # ------------------------------------------------------------------
    def request_priority(self, approach: str, track_id: Optional[int] = None,
                         score: float = 0.0) -> TransitionResult:
        """AI layer entry point. Only NORMAL may begin a priority sequence."""
        if self.state is not SignalState.NORMAL:
            if self.track_id == track_id and self.priority_approach == approach:
                return TransitionResult(False, self.state.value, "ALREADY_ACTIVE",
                                        self.state.value)
            self.rejected_requests += 1
            self._emit("REQUEST_REJECTED",
                       {"approach": approach, "track_id": track_id,
                        "state": self.state.value, "reason": "CONFLICTING_REQUEST"})
            return TransitionResult(False, self.state.value, "REQUEST_REJECTED",
                                    self.state.value)
        self.priority_approach = approach
        self.track_id = track_id
        self._cleared = False
        self.episode += 1
        self._emit("PRIORITY_REQUESTED", {"approach": approach, "track_id": track_id,
                                          "score": score})
        return self.transition(SignalState.PREPARE, reason="PRIORITY_REQUESTED")

    def ambulance_cleared(self, track_id: Optional[int] = None) -> TransitionResult:
        if self.state is not SignalState.EMERGENCY_GREEN:
            return TransitionResult(False, self.state.value, "NOT_IN_EMERGENCY_GREEN",
                                    self.state.value)
        self._cleared = True
        self._emit("AMBULANCE_CLEARED", {"track_id": track_id or self.track_id})
        return self.transition(SignalState.CLEARANCE, reason="AMBULANCE_CLEARED")

    def abort(self, reason: str = "TRACK_LOST") -> TransitionResult:
        """Fail-safe: return to normal operation from a pre-green state."""
        if self.state in (SignalState.PREPARE, SignalState.ALL_RED):
            return self.transition(SignalState.NORMAL, reason=reason)
        if self.state is SignalState.EMERGENCY_GREEN:
            return self.transition(SignalState.CLEARANCE, reason=reason)
        return TransitionResult(False, self.state.value, "NO_ABORT_NEEDED", self.state.value)

    # ------------------------------------------------------------------
    def tick(self, now: Optional[float] = None) -> Optional[TransitionResult]:
        now = now if now is not None else self._clock()
        elapsed = now - self.entered_at
        duration = self.durations[self.state]
        if self.state is SignalState.NORMAL:
            return None
        if elapsed < duration:
            return None
        nxt = {
            SignalState.PREPARE: SignalState.ALL_RED,
            SignalState.ALL_RED: SignalState.EMERGENCY_GREEN,
            SignalState.EMERGENCY_GREEN: SignalState.CLEARANCE,
            SignalState.CLEARANCE: SignalState.NORMAL,
        }[self.state]
        reason = "PHASE_TIMEOUT" if self.state is SignalState.EMERGENCY_GREEN else "PHASE_COMPLETE"
        return self.transition(nxt, reason=reason)

    # ------------------------------------------------------------------
    def snapshot(self, now: Optional[float] = None) -> FSMSnapshot:
        now = now if now is not None else self._clock()
        elapsed = now - self.entered_at
        duration = self.durations[self.state]
        return FSMSnapshot(
            state=self.state.value,
            priority_approach=self.priority_approach,
            track_id=self.track_id,
            phase_elapsed=elapsed,
            phase_duration=duration,
            remaining=max(0.0, duration - elapsed),
            emergency_active=self.state is not SignalState.NORMAL,
            rejected_requests=self.rejected_requests,
        )

    def _emit(self, event: str, payload: dict) -> None:
        try:
            self._on_event(event, payload)
        except Exception:  # pragma: no cover - listener must never break the FSM
            pass
