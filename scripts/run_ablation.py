#!/usr/bin/env python3
"""Ablation study: how much does each pipeline stage actually contribute?

Four variants are run over the SAME detection stream from the configured
video/detector:

    A  detection only
    B  detection + tracking
    C  detection + tracking + temporal validation
    D  full pipeline (validation + priority threshold)

Ground truth for this clip: priority is warranted only while the inbound
ambulance is travelling toward the intersection on the NORTH approach
(scenario seconds 3-15). Any activation outside that window is counted as a
false activation. Results are written to data/experiments/ablation.json and
served by GET /api/ablation.

Usage:  python scripts/run_ablation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_config                     # noqa: E402
from app.core.types import Approach, MotionState           # noqa: E402
from app.decision.priority import PriorityEngine           # noqa: E402
from app.decision.proximity import ProximityEstimator      # noqa: E402
from app.decision.roi import ROIManager                    # noqa: E402
from app.decision.trajectory import TrajectoryAnalyzer     # noqa: E402
from app.decision.validation import TemporalValidator      # noqa: E402
from app.tracking.bytetrack import build_tracker           # noqa: E402
from app.vision.detector import build_detector, is_ambulance  # noqa: E402
from app.vision.scenario import PERIOD_S                   # noqa: E402
from app.vision.video_source import build_video_source     # noqa: E402

TRUE_WINDOW = (3.0, 15.5)   # scenario seconds where priority is warranted


def in_true_window(t: float) -> bool:
    return TRUE_WINDOW[0] <= (t % PERIOD_S) <= TRUE_WINDOW[1]


def run(frames: int = 900) -> dict:
    cfg = get_config()
    cfg.set("video.target_fps", 0)
    fps = 15.0
    source = build_video_source(cfg)
    source.open()
    detector = build_detector(cfg, "demo")
    tracker = build_tracker(cfg)
    roi = ROIManager(cfg)
    traj = TrajectoryAnalyzer(roi, min_points=int(cfg.get("trajectory.min_points", 4)))
    validator = TemporalValidator(
        required_frames=int(cfg.get("validation.required_frames", 5)),
        min_confidence=float(cfg.get("validation.min_confidence", 0.55)))
    prox = ProximityEstimator(roi)
    engine = PriorityEngine(cfg.get("priority.weights"),
                            float(cfg.get("priority.threshold", 0.7)))

    stats = {k: {"activations": 0, "false_activations": 0, "first_frame": None}
             for k in "ABCD"}
    # an "activation" is counted once per contiguous run per variant
    latched = {k: False for k in "ABCD"}
    frames_seen = 0

    for _ in range(frames):
        frame, meta = source.read()
        if frame is None:
            break
        frames_seen += 1
        t = meta.frame_id / fps
        dets = [d for d in detector.detect(frame, meta) if is_ambulance(d)]
        tracks = tracker.update(dets, meta)

        fired = {"A": bool(dets), "B": False, "C": False, "D": False}
        for tr in tracks:
            cx, cy = tr.centroid
            r = roi.classify(cx, cy, meta.width, meta.height)
            tinfo = traj.analyse(tr, meta.width, meta.height)
            p = prox.estimate(cx, cy, meta.width, meta.height, tinfo)
            v = validator.update(tr, r, tinfo, meta.timestamp)
            fired["B"] = True
            if v.validated:
                fired["C"] = True
                score = engine.score(
                    detection_confidence=tr.confidence,
                    temporal_frames=v.consecutive_frames,
                    required_frames=validator.required_frames,
                    approach_known=r.approach != Approach.UNKNOWN.value,
                    proximity_urgency=prox.proximity_urgency(p),
                    eta_urgency=prox.eta_urgency(p),
                    trajectory_confidence=tinfo.confidence)
                if score.exceeds_threshold and tinfo.motion_state == MotionState.APPROACHING.value:
                    fired["D"] = True

        for key, active in fired.items():
            if active and not latched[key]:
                stats[key]["activations"] += 1
                if stats[key]["first_frame"] is None:
                    stats[key]["first_frame"] = meta.frame_id
                if not in_true_window(t):
                    stats[key]["false_activations"] += 1
            latched[key] = active

    source.release()
    names = {
        "A": "Detection only",
        "B": "Detection + tracking",
        "C": "Detection + tracking + temporal validation",
        "D": "Full pipeline (validation + priority threshold)",
    }
    return {
        "status": "OK",
        "frames_evaluated": frames_seen,
        "detector": detector.name,
        "simulated": detector.simulated,
        "true_priority_window_s": list(TRUE_WINDOW),
        "note": ("Measured on the synthetic demo clip with the demo detector. "
                 "Numbers describe pipeline behaviour, not model accuracy."),
        "variants": [
            {"variant": k, "name": names[k],
             "activations": stats[k]["activations"],
             "false_activations": stats[k]["false_activations"],
             "frames_to_decision": stats[k]["first_frame"]}
            for k in "ABCD"
        ],
    }


def main() -> int:
    result = run()
    out = ROOT / "data/experiments/ablation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result["variants"], indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
