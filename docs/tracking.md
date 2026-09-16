# Tracking

`ByteTrackTracker` implements ByteTrack-style two-stage association:

1. Age every track, then extrapolate its box with the last velocity estimate.
2. Associate high-confidence detections (`tracking.high_threshold`) by greedy IoU.
3. Associate remaining tracks against low-confidence detections at a relaxed IoU.
4. Spawn new tracks from unmatched high-confidence detections.
5. Drop tracks that exceed `tracking.max_age` without an update and record them in `lost_track_ids`.

A track becomes `confirmed` after `tracking.min_hits` hits; only confirmed tracks leave the tracker. This is what prevents a one-frame false positive from ever reaching the decision stack.

## Velocity

Velocity is computed from the last *observed* centroid, not the current (possibly predicted) box, and smoothed 50/50 with the previous estimate. An earlier version used the predicted box; the estimate oscillated, IoU association failed after ~25 frames, and one ambulance fragmented into four track IDs. `test_track_id_is_stable_across_frames` guards against a regression.

## Not implemented

BoT-SORT. Requesting it logs `TRACKER_FALLBACK` and uses ByteTrack. Appearance embeddings and Kalman filtering are future work.
