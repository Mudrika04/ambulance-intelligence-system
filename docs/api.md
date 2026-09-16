# API

Base URL `http://localhost:8000`. Interactive documentation at `/docs` (OpenAPI 3).

## System
| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Component states: camera, model, tracker, database, api |
| GET | `/api/status` | Full live snapshot (ambulances, decision, signal, corridor, metrics) |
| GET | `/api/metrics` | Measured runtime metrics + stored metrics |
| GET | `/api/config` | Effective configuration |
| POST | `/api/config` | Update dotted config keys; some apply hot |

## Data
| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/detections` | Live ambulances + stored detections |
| GET | `/api/tracks` | Live and stored tracks |
| GET | `/api/events` | Event timeline (`limit`, `track_id`, `event_type`) |
| GET | `/api/priority` | Current decision, per-track scores, history |
| GET | `/api/signal` | Current FSM/lamps + transition history |
| GET | `/api/intersections` | Green-corridor snapshot |
| GET | `/api/replay/tracks` | Track IDs with a recorded emergency event |
| GET | `/api/replay/{track_id}` | Full replay: timeline, priority, signal, trajectory |
| GET | `/api/trajectory/{track_id}` | Recorded trajectory points |

## Control
| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/video/start` | Start the pipeline (`source`, `source_type`, `mode`) |
| POST | `/api/video/stop` | Stop the pipeline |
| POST | `/api/simulation/start` | Start forced into demo mode |
| POST | `/api/simulation/stop` | Stop |
| POST | `/api/simulation/reset` | Stop, reset FSM, tracker, validator, corridor |
| GET | `/api/video/stream` | MJPEG stream of annotated frames (409 if not running) |
| GET | `/api/video/frame` | Latest annotated JPEG |
| POST | `/api/experiments/run` | Fixed-time vs AI-adaptive simulation |
| GET | `/api/experiments` | Stored experiments, else `AWAITING_EXPERIMENT_DATA` |
| GET | `/api/ablation` | Ablation results, else `AWAITING_EXPERIMENT_DATA` |
| GET | `/api/evaluation` | Detection evaluation, else `AWAITING_EXPERIMENT_DATA` |

## WebSocket `/ws/live`

Messages are `{type, payload}`:
- `hello` — snapshot on connect
- `state` — per-frame snapshot
- `event` — system event (detection, validation, priority, FSM transition, rejection)
- `system_health` — heartbeat every 2 s when idle

## Database schema

| Table | Key columns |
| --- | --- |
| `detections` | timestamp, frame_id, track_id, class_name, confidence, bbox, source, simulated |
| `tracks` | track_id, intersection_id, first_seen, last_seen, approach, max_confidence, validated, frames |
| `trajectory_points` | track_id, frame_id, cx, cy, confidence, zone, approach, proximity, relative_eta |
| `priority_events` | track_id, approach, confidence, proximity, relative_eta, priority_score, decision, reason_codes, accepted |
| `signal_events` | from_state, signal_state, approach, track_id, reason, accepted |
| `system_events` | event_type, level, track_id, intersection_id, message, metadata |
| `intersections` | intersection_id, name, role, status, updated_at |
| `experiments` | experiment_id, scenario, mode, configuration, results, notes |
| `metrics` | name, value, unit, experiment_id, context |
