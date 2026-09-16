# Temporal validation

A single-frame detection must never activate emergency priority. `TemporalValidator` counts consecutive frames in which a track satisfies every criterion:

- the tracker has confirmed the track
- confidence ≥ `validation.min_confidence`
- the centroid is inside a configured ROI (`validation.require_roi`)
- the approach is identified and has not changed
- motion is APPROACHING (`validation.require_inbound`)

Any failure resets the counter to zero and records a failure code (`LOW_CONFIDENCE`, `OUTSIDE_ROI`, `APPROACH_CHANGED`, `MOTION_MOVING_AWAY`, …) which flows into the decision explanation.

`validation.required_frames` defaults to 5. **Five is a configurable prototype parameter, not a scientifically established optimum.** At 15 fps it costs roughly 0.33 s. The right value depends on camera frame rate, detector stability and the tolerated false-activation rate, and must be determined experimentally.

## Measured effect

From `scripts/run_ablation.py` over 900 frames of the demo clip (two scenario loops):

| Variant | Activations | False activations | First decision frame |
| --- | --- | --- | --- |
| A detection only | 10 | 4 | 45 |
| B + tracking | 4 | 2 | 46 |
| C + temporal validation | 2 | 0 | 59 |
| D full pipeline | 2 | 0 | 59 |

Validation removed the remaining false activations at a cost of 13 frames of latency.
