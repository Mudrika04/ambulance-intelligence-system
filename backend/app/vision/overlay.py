"""Frame annotation for the live view."""
from __future__ import annotations

from typing import Dict, List

import cv2
import numpy as np

INK = (36, 28, 20)
WHITE = (255, 255, 255)
ROI_COLOR = (150, 130, 90)
TRACK_COLOR = (90, 170, 255)
AMB_COLOR = (60, 90, 235)
OK_COLOR = (90, 175, 90)
WARN = (40, 170, 240)


def _label(img, text, org, color=WHITE, bg=INK, scale=0.45, pad=4):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    x, y = int(org[0]), int(org[1])
    cv2.rectangle(img, (x, y - th - pad * 2), (x + tw + pad * 2, y), bg, -1)
    cv2.putText(img, text, (x + pad, y - pad), cv2.FONT_HERSHEY_SIMPLEX, scale,
                color, 1, cv2.LINE_AA)


def draw_rois(frame: np.ndarray, roi) -> np.ndarray:
    h, w = frame.shape[:2]
    overlay = frame.copy()
    for name, poly in roi.polygons_px(w, h).items():
        cv2.polylines(overlay, [poly], True, ROI_COLOR, 1, cv2.LINE_AA)
        cx, cy = poly.mean(axis=0).astype(int)
        cv2.putText(overlay, name, (cx - 22, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    ROI_COLOR, 1, cv2.LINE_AA)
    ccx, ccy = roi.center_px(w, h)
    for zone, r in roi.zone_radii_px(w, h).items():
        if zone in ("CONTROL_ZONE", "NEAR_ZONE", "MEDIUM_ZONE"):
            cv2.circle(overlay, (ccx, ccy), r, ROI_COLOR, 1, cv2.LINE_AA)
    return cv2.addWeighted(overlay, 0.55, frame, 0.45, 0)


def annotate(frame: np.ndarray, roi, ambulances: List[dict], others: List[dict],
             signal: Dict[str, str], fsm_state: str, simulated: bool,
             fps: float, frame_id: int) -> np.ndarray:
    img = draw_rois(frame, roi)
    h, w = img.shape[:2]

    for d in others:
        x1, y1, x2, y2 = (int(v) for v in d["bbox"])
        cv2.rectangle(img, (x1, y1), (x2, y2), (150, 150, 150), 1)

    for a in ambulances:
        x1, y1, x2, y2 = (int(v) for v in a["bbox"])
        color = OK_COLOR if a.get("validated") else AMB_COLOR
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        _label(img, f"AMBULANCE #{a['track_id']}  {a['confidence']:.2f}",
               (x1, max(16, y1)), WHITE, color)
        _label(img, f"{a['approach']} / {a['motion_state']} / {a['proximity']}",
               (x1, min(h - 2, y2 + 20)), WHITE, INK, 0.4)
        pts = a.get("trajectory") or []
        if len(pts) > 1:
            arr = np.array([[int(x), int(y)] for x, y in pts], dtype=np.int32)
            cv2.polylines(img, [arr], False, TRACK_COLOR, 2, cv2.LINE_AA)

    # signal heads
    x0, y0 = w - 150, 14
    _label(img, f"FSM: {fsm_state}", (x0, y0 + 16), WHITE, INK, 0.45)
    for i, d in enumerate(("NORTH", "SOUTH", "EAST", "WEST")):
        state = signal.get(d, "RED")
        col = {"RED": (60, 60, 220), "YELLOW": (40, 190, 230),
               "GREEN": (80, 180, 80)}[state]
        cv2.circle(img, (x0 + 10, y0 + 38 + i * 20), 6, col, -1)
        cv2.putText(img, f"{d}", (x0 + 24, y0 + 43 + i * 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, WHITE, 1, cv2.LINE_AA)

    _label(img, f"frame {frame_id}  |  {fps:.1f} fps", (10, h - 10), WHITE, INK, 0.45)
    if simulated:
        _label(img, "DEMO / SIMULATION MODE", (10, 22), (255, 255, 255), (30, 110, 200), 0.5)
    return img


def encode_jpeg(frame: np.ndarray, quality: int = 72) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return buf.tobytes() if ok else b""
