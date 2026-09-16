"""ByteTrack-style multi-object tracker.

Two-stage association (high-confidence detections first, then low-confidence
leftovers) with IoU matching, constant-velocity prediction and track ageing.
Pure NumPy so the prototype has no extra runtime dependency.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np

from ..core.logging_conf import get_logger
from ..core.types import BBox, Detection, FrameMeta, Track, TrackPoint
from .base import Tracker

log = get_logger(__name__)


def iou(a: BBox, b: BBox) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def greedy_match(tracks: Sequence[Track], dets: Sequence[Detection],
                 thr: float) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
    """Greedy IoU association. Returns (matches, unmatched_tracks, unmatched_dets)."""
    if not tracks or not dets:
        return [], list(range(len(tracks))), list(range(len(dets)))
    cost = np.zeros((len(tracks), len(dets)), dtype=np.float32)
    for i, t in enumerate(tracks):
        for j, d in enumerate(dets):
            cost[i, j] = iou(t.bbox, d.bbox)
    matches: List[Tuple[int, int]] = []
    used_t, used_d = set(), set()
    while True:
        i, j = np.unravel_index(int(np.argmax(cost)), cost.shape)
        if cost[i, j] < thr:
            break
        matches.append((int(i), int(j)))
        used_t.add(int(i))
        used_d.add(int(j))
        cost[i, :] = -1
        cost[:, j] = -1
        if len(used_t) == len(tracks) or len(used_d) == len(dets):
            break
    ut = [i for i in range(len(tracks)) if i not in used_t]
    ud = [j for j in range(len(dets)) if j not in used_d]
    return matches, ut, ud


class ByteTrackTracker(Tracker):
    name = "bytetrack"

    def __init__(self, high_threshold: float = 0.6, low_threshold: float = 0.2,
                 match_iou: float = 0.25, max_age: int = 15, min_hits: int = 2,
                 max_history: int = 300):
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.match_iou = match_iou
        self.max_age = max_age
        self.min_hits = min_hits
        self.max_history = max_history
        self._tracks: Dict[int, Track] = {}
        self._velocity: Dict[int, Tuple[float, float]] = {}
        self._next_id = 1
        self._status = "ACTIVE"
        self.lost_track_ids: List[int] = []

    # ------------------------------------------------------------------
    @property
    def status(self) -> str:
        return self._status

    def reset(self) -> None:
        self._tracks.clear()
        self._velocity.clear()
        self._next_id = 1
        self.lost_track_ids = []

    @property
    def tracks(self) -> List[Track]:
        return list(self._tracks.values())

    # ------------------------------------------------------------------
    def _predict(self) -> None:
        for tid, tr in self._tracks.items():
            vx, vy = self._velocity.get(tid, (0.0, 0.0))
            if tr.time_since_update > 0 and (vx or vy):
                x1, y1, x2, y2 = tr.bbox
                tr.bbox = (x1 + vx, y1 + vy, x2 + vx, y2 + vy)

    def _spawn(self, det: Detection, meta: FrameMeta) -> Track:
        tid = self._next_id
        self._next_id += 1
        tr = Track(track_id=tid, bbox=det.bbox, confidence=det.confidence,
                   frame_id=meta.frame_id, timestamp=meta.timestamp,
                   hits=1, age=1, time_since_update=0,
                   confirmed=self.min_hits <= 1)
        cx, cy = det.centroid
        tr.history.append(TrackPoint(meta.frame_id, meta.timestamp, cx, cy, det.confidence))
        self._tracks[tid] = tr
        return tr

    def _update_track(self, tr: Track, det: Detection, meta: FrameMeta) -> None:
        # velocity must come from the last OBSERVED centroid; using the current
        # (already predicted) box makes the estimate oscillate and breaks IoU
        # association after a few frames.
        missed = max(1, tr.time_since_update)
        if tr.history:
            pcx, pcy = tr.history[-1].cx, tr.history[-1].cy
        else:
            pcx, pcy = tr.centroid
        tr.bbox = det.bbox
        tr.confidence = det.confidence
        tr.frame_id = meta.frame_id
        tr.timestamp = meta.timestamp
        tr.hits += 1
        tr.time_since_update = 0
        if tr.hits >= self.min_hits:
            tr.confirmed = True
        cx, cy = det.centroid
        vx, vy = (cx - pcx) / missed, (cy - pcy) / missed
        prev = self._velocity.get(tr.track_id)
        if prev is not None:
            vx, vy = 0.5 * prev[0] + 0.5 * vx, 0.5 * prev[1] + 0.5 * vy
        self._velocity[tr.track_id] = (vx, vy)
        tr.history.append(TrackPoint(meta.frame_id, meta.timestamp, cx, cy, det.confidence))
        if len(tr.history) > self.max_history:
            del tr.history[0: len(tr.history) - self.max_history]

    # ------------------------------------------------------------------
    def update(self, detections: List[Detection], meta: FrameMeta) -> List[Track]:
        self.lost_track_ids = []
        try:
            for tr in self._tracks.values():
                tr.age += 1
                tr.time_since_update += 1
            self._predict()

            high = [d for d in detections if d.confidence >= self.high_threshold]
            low = [d for d in detections
                   if self.low_threshold <= d.confidence < self.high_threshold]

            active = list(self._tracks.values())
            matches, unmatched_t, unmatched_d = greedy_match(active, high, self.match_iou)
            for ti, di in matches:
                self._update_track(active[ti], high[di], meta)

            # second association: leftover tracks against low-score detections
            leftover_tracks = [active[i] for i in unmatched_t]
            m2, ut2, _ = greedy_match(leftover_tracks, low, self.match_iou * 0.8)
            for ti, di in m2:
                self._update_track(leftover_tracks[ti], low[di], meta)

            for di in unmatched_d:
                self._spawn(high[di], meta)

            for tid in [t.track_id for t in self._tracks.values()
                        if t.time_since_update > self.max_age]:
                self.lost_track_ids.append(tid)
                self._tracks.pop(tid, None)
                self._velocity.pop(tid, None)
                log.info("track lost", extra={"event": "TRACK_LOST", "track_id": tid})

            self._status = "ACTIVE"
            return [t for t in self._tracks.values() if t.confirmed]
        except Exception:  # pragma: no cover - defensive, tracker must fail safe
            self._status = "TRACKER_ERROR"
            log.exception("tracker failure", extra={"event": "TRACKER_ERROR"})
            return []


def build_tracker(cfg) -> Tracker:
    algo = str(cfg.get("tracking.algorithm", "bytetrack")).lower()
    if algo not in ("bytetrack", "botsort"):
        raise ValueError(f"Unsupported tracker: {algo}")
    if algo == "botsort":
        log.warning("BoT-SORT not implemented in this prototype; using ByteTrack",
                    extra={"event": "TRACKER_FALLBACK"})
    return ByteTrackTracker(
        high_threshold=float(cfg.get("tracking.high_threshold", 0.6)),
        low_threshold=float(cfg.get("tracking.low_threshold", 0.2)),
        match_iou=float(cfg.get("tracking.match_iou", 0.25)),
        max_age=int(cfg.get("tracking.max_age", 15)),
        min_hits=int(cfg.get("tracking.min_hits", 2)),
    )
