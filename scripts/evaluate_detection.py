#!/usr/bin/env python3
"""Evaluate the configured detector against a ground-truth file.

    python scripts/evaluate_detection.py                 # demo detector
    python scripts/evaluate_detection.py --mode real     # trained YOLOv8 model

Computes precision, recall, F1 and AP@0.5 (plus AP averaged over IoU 0.50:0.95)
for the ambulance class, writing data/experiments/detection_eval.json, which is
served by GET /api/evaluation.

Honest reading of the output:
* With the DEMO detector the ground truth is the same script the detector
  samples, so the numbers only verify that the evaluation code and the demo
  scenario agree. They are NOT a model accuracy claim.
* Real accuracy numbers require a trained model and an independently labelled
  dataset. Until that exists the dashboard shows AWAITING EXPERIMENT DATA.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_config                     # noqa: E402
from app.tracking.bytetrack import iou                     # noqa: E402
from app.vision.detector import build_detector, is_ambulance  # noqa: E402
from app.vision.video_source import build_video_source     # noqa: E402


def match(preds, gts, thr: float) -> Tuple[int, int, int]:
    """Greedy IoU matching -> (true positives, false positives, false negatives)."""
    used = set()
    tp = 0
    for p in sorted(preds, key=lambda d: -d.confidence):
        best, best_i = 0.0, -1
        for i, g in enumerate(gts):
            if i in used:
                continue
            score = iou(p.bbox, tuple(g))
            if score > best:
                best, best_i = score, i
        if best >= thr and best_i >= 0:
            used.add(best_i)
            tp += 1
    return tp, len(preds) - tp, len(gts) - len(used)


def average_precision(records: List[Tuple[float, int]], total_gt: int) -> float:
    """11-point-free AP: precision-recall integration over sorted confidences."""
    if total_gt == 0:
        return 0.0
    records.sort(key=lambda r: -r[0])
    tp = fp = 0
    prev_recall = 0.0
    ap = 0.0
    for _, is_tp in records:
        tp += is_tp
        fp += 1 - is_tp
        recall = tp / total_gt
        precision = tp / max(1, tp + fp)
        ap += (recall - prev_recall) * precision
        prev_recall = recall
    return ap


def main() -> int:
    ap_args = argparse.ArgumentParser()
    ap_args.add_argument("--mode", default=None, choices=["demo", "real"])
    ap_args.add_argument("--frames", type=int, default=450)
    args = ap_args.parse_args()

    cfg = get_config()
    cfg.set("video.target_fps", 0)
    gt_path = Path(str(cfg.resolve("video.source"))).with_suffix(".groundtruth.json")
    if not gt_path.exists():
        print(f"No ground truth beside the video ({gt_path}).")
        print("Generate the demo clip first: python scripts/generate_sample_video.py")
        return 1
    truth = json.loads(gt_path.read_text())
    by_frame = {f["frame_id"]: [o["bbox"] for o in f["objects"] if o["class"] == "ambulance"]
                for f in truth["frames"]}

    source = build_video_source(cfg)
    source.open()
    detector = build_detector(cfg, args.mode)

    tp = fp = fn = 0
    total_gt = 0
    records: List[Tuple[float, int]] = []
    per_iou = {round(t, 2): 0 for t in [0.5 + 0.05 * i for i in range(10)]}
    frames = 0

    for _ in range(args.frames):
        frame, meta = source.read()
        if frame is None:
            break
        frames += 1
        gts = by_frame.get(meta.frame_id, [])
        preds = [d for d in detector.detect(frame, meta) if is_ambulance(d)]
        total_gt += len(gts)
        f_tp, f_fp, f_fn = match(preds, gts, 0.5)
        tp += f_tp
        fp += f_fp
        fn += f_fn
        matched = 0
        for p in sorted(preds, key=lambda d: -d.confidence):
            hit = any(iou(p.bbox, tuple(g)) >= 0.5 for g in gts) and matched < len(gts)
            if hit:
                matched += 1
            records.append((p.confidence, 1 if hit else 0))
        for thr in per_iou:
            per_iou[thr] += match(preds, gts, thr)[0]

    source.release()
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    ap50 = average_precision(records, total_gt)
    ap_range = sum(v / max(1, total_gt) for v in per_iou.values()) / len(per_iou)

    demo = detector.simulated
    result = {
        "status": "OK",
        "detector": detector.name,
        "simulated": demo,
        "frames_evaluated": frames,
        "ground_truth_boxes": total_gt,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "ap50": round(ap50, 4),
        "ap50_95_approx": round(ap_range, 4),
        "note": ("DEMO DETECTOR: ground truth is the same script the detector samples, so "
                 "these figures verify the evaluation pipeline only and are not a model "
                 "accuracy claim." if demo else
                 "Measured with the configured trained model against the supplied ground truth."),
    }
    out = ROOT / "data/experiments/detection_eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
