# Priority engine

```
PriorityScore = Σ wᵢ · componentᵢ      (components normalised to 0..1)
```

| Component | Source |
| --- | --- |
| `detection_confidence` | tracker's current confidence |
| `temporal_consistency` | consecutive validated frames / required frames |
| `approach_certainty` | 1 if the approach is identified, else 0 |
| `proximity_urgency` | NEAR 1.0 · MEDIUM 0.6 · FAR 0.25 |
| `eta_urgency` | from the camera-based relative ETA |
| `trajectory_confidence` | direction consistency × sample sufficiency |

Weights are read from `priority.weights` and normalised to sum to 1. The score is compared against `priority.threshold` (default 0.70). The API returns components, weights and per-component contributions so the dashboard can show exactly where a score came from.

**The weights and the threshold are prototype values. They are not claimed to be optimal.**

## Proximity and relative ETA

Proximity comes from ROI zone membership. Relative ETA is `remaining_pixels / closing_speed_px_per_s`, returned only while the vehicle is actually closing. Without camera calibration this is an image-space estimate: the API attaches the note "Camera-based relative ETA estimate (image-space). Not equivalent to GPS-level positioning." and the dashboard prints it.

## Explanation

`DecisionEngine` returns `decision` ∈ {`PRIORITY_REQUESTED`, `MONITORING`, `NO_PRIORITY`} plus reason codes such as `AMBULANCE_DETECTED`, `TRACK_PERSISTENT`, `INBOUND_APPROACH`, `VALID_ROI`, `HIGH_PROXIMITY`, `THRESHOLD_EXCEEDED`, and negative codes like `SINGLE_FRAME_ONLY` or `MOTION_MOVING_AWAY`. Each code has a human-readable sentence; the console renders both.
