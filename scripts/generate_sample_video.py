#!/usr/bin/env python3
"""Render the demo scenario to an MP4 plus a ground-truth JSON file.

The clip is SYNTHETIC: a schematic intersection with vehicle rectangles. It
exists so the video pipeline, tracker and ROI logic can be exercised without a
licensed traffic dataset. It is not real road footage and must never be
presented as one.

Usage:
    python scripts/generate_sample_video.py [--seconds 30] [--fps 15]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.vision import scenario  # noqa: E402

ROAD = (78, 78, 82)
GROUND = (108, 122, 112)
MARK = (226, 226, 220)
CAR_COLORS = ((170, 140, 90), (90, 95, 180))


def draw_background(w: int, h: int) -> np.ndarray:
    img = np.full((h, w, 3), GROUND, dtype=np.uint8)
    cv2.rectangle(img, (int(0.36 * w), 0), (int(0.64 * w), h), ROAD, -1)
    cv2.rectangle(img, (0, int(0.45 * h)), (w, int(0.68 * h)), ROAD, -1)
    for y in range(0, h, 40):
        cv2.line(img, (int(0.50 * w), y), (int(0.50 * w), y + 18), MARK, 2)
    for x in range(0, w, 40):
        cv2.line(img, (x, int(0.565 * h)), (x + 18, int(0.565 * h)), MARK, 2)
    cv2.rectangle(img, (int(0.36 * w), int(0.45 * h)),
                  (int(0.64 * w), int(0.68 * h)), ROAD, -1)
    return img


def draw_vehicle(img: np.ndarray, obj, w: int, h: int, tick: int) -> None:
    x1, y1, x2, y2 = (int(v) for v in scenario.to_pixel_bbox(obj, w, h))
    if obj.cls == "ambulance":
        cv2.rectangle(img, (x1, y1), (x2, y2), (245, 245, 245), -1)
        cv2.rectangle(img, (x1, y1), (x2, y2), (40, 40, 40), 1)
        band = int((y2 - y1) * 0.34)
        cv2.rectangle(img, (x1, (y1 + y2) // 2 - band // 2),
                      (x2, (y1 + y2) // 2 + band // 2), (40, 40, 210), -1)
        # alternating beacons
        left = (60, 60, 240) if tick % 8 < 4 else (250, 160, 60)
        right = (250, 160, 60) if tick % 8 < 4 else (60, 60, 240)
        cv2.circle(img, (x1 + 5, y1 + 5), 3, left, -1)
        cv2.circle(img, (x2 - 5, y1 + 5), 3, right, -1)
        cv2.line(img, (x1 + 6, y2 - 6), (x2 - 6, y2 - 6), (40, 40, 210), 2)
        if obj.occluded:
            cv2.rectangle(img, (x1 - 6, y1 + (y2 - y1) // 3),
                          (x2 + 6, y2), (70, 90, 70), -1)  # simulated occluder
    else:
        color = CAR_COLORS[hash(obj.label) % len(CAR_COLORS)]
        cv2.rectangle(img, (x1, y1), (x2, y2), color, -1)
        cv2.rectangle(img, (x1, y1), (x2, y2), (35, 35, 35), 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=scenario.PERIOD_S)
    ap.add_argument("--fps", type=float, default=15.0)
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=540)
    ap.add_argument("--out", default=str(ROOT / "data/sample/demo_intersection.mp4"))
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"),
                             args.fps, (args.width, args.height))
    if not writer.isOpened():
        print("ERROR: could not open the video writer (missing mp4v codec)")
        return 1

    background = draw_background(args.width, args.height)
    total = int(args.seconds * args.fps)
    ground_truth = []
    for i in range(total):
        t = i / args.fps
        frame = background.copy()
        objs = scenario.objects_at(t)
        for obj in objs:
            draw_vehicle(frame, obj, args.width, args.height, i)
        cv2.putText(frame, "SYNTHETIC DEMO CLIP - NOT REAL FOOTAGE",
                    (12, args.height - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (235, 235, 235), 1, cv2.LINE_AA)
        writer.write(frame)
        ground_truth.append({
            "frame_id": i + 1,
            "time_s": round(t, 3),
            "objects": [{"class": o.cls,
                         "bbox": [round(v, 1) for v in
                                  scenario.to_pixel_bbox(o, args.width, args.height)],
                         "occluded": o.occluded, "label": o.label} for o in objs],
        })
    writer.release()

    gt_path = out_path.with_suffix(".groundtruth.json")
    gt_path.write_text(json.dumps({
        "source": "synthetic",
        "fps": args.fps,
        "width": args.width,
        "height": args.height,
        "frames": ground_truth,
    }))
    size_mb = out_path.stat().st_size / 1e6
    print(f"wrote {out_path} ({total} frames, {size_mb:.2f} MB)")
    print(f"wrote {gt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
