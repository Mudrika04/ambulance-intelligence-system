# Signal finite state machine

States: `NORMAL`, `PREPARE`, `ALL_RED`, `EMERGENCY_GREEN`, `CLEARANCE`.

```
NORMAL → PREPARE → ALL_RED → EMERGENCY_GREEN → CLEARANCE → NORMAL
```

Permitted transitions are declared in a table. `PREPARE → NORMAL` and `ALL_RED → NORMAL` exist as fail-safe aborts (camera failure, lost track). Everything else is rejected, counted in `rejected_requests` and logged as `TRANSITION_REJECTED`. `NORMAL → EMERGENCY_GREEN` is structurally impossible.

## Requests

`request_priority(approach, track_id, score)` is the only entry point for the AI layer.

- from `NORMAL`: accepted, the machine enters `PREPARE`, the episode counter increments
- from any other state, same track: `ALREADY_ACTIVE` (no log noise)
- from any other state, different track: `REQUEST_REJECTED`, logged as a conflict

`ambulance_cleared()` is honoured only from `EMERGENCY_GREEN`. `EMERGENCY_GREEN` also times out after `signal.emergency_green_max`, so the junction cannot be held green indefinitely by a stuck track.

## Simulator

`SignalSimulator` maps state to lamps: emergency green gives GREEN to the priority approach and RED to the other three; `ALL_RED` and `CLEARANCE` are all red; `PREPARE` turns currently-green approaches amber; `NORMAL` runs a fixed NS/EW cycle. At most one direction can be green at any time, which `test_8_conflicting_signal_request_is_rejected` asserts.
