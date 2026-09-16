"""Pipeline orchestrator.

CAMERA -> DETECTION -> TRACKING -> ROI -> TEMPORAL VALIDATION -> TRAJECTORY ->
PROXIMITY -> PRIORITY -> EXPLAINABLE DECISION -> SIGNAL FSM -> GREEN CORRIDOR ->
EVENT LOGGING.

Runs in a background worker thread; publishes snapshots on the event bus and
keeps the latest annotated JPEG for the MJPEG endpoint.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional

from ..core.config import Config, get_config
from ..core.logging_conf import get_logger
from ..core.types import Approach, MotionState, Proximity, Zone
from ..database.repository import SQLiteRepository
from ..decision.engine import DecisionEngine
from ..decision.priority import PriorityEngine
from ..decision.proximity import ProximityEstimator
from ..decision.roi import ROIManager
from ..decision.trajectory import TrajectoryAnalyzer
from ..decision.validation import TemporalValidator
from ..tracking.bytetrack import build_tracker
from ..traffic.fsm import SignalState, TrafficSignalFSM
from ..traffic.green_corridor import GreenCorridor
from ..traffic.signal_simulator import SignalSimulator
from ..vision.detector import (Detector, ModelNotFoundError, build_detector,
                               is_ambulance)
from ..vision.overlay import annotate, encode_jpeg
from ..vision.video_source import VideoSource, VideoSourceError, build_video_source
from .events import EventBus
from .metrics import PerformanceMonitor

log = get_logger(__name__)


class Pipeline:
    def __init__(self, cfg: Optional[Config] = None, bus: Optional[EventBus] = None,
                 repo: Optional[SQLiteRepository] = None):
        self.cfg = cfg or get_config()
        self.bus = bus or EventBus()
        self.repo = repo or SQLiteRepository()

        self.roi = ROIManager(self.cfg)
        self.tracker = build_tracker(self.cfg)
        self.trajectory = TrajectoryAnalyzer(
            self.roi,
            min_points=int(self.cfg.get("trajectory.min_points", 4)),
            stationary_speed=float(self.cfg.get("trajectory.stationary_speed_px_s", 6.0)),
            consistency_min=float(self.cfg.get("trajectory.direction_consistency_min", 0.55)),
        )
        self.validator = TemporalValidator(
            required_frames=int(self.cfg.get("validation.required_frames", 5)),
            min_confidence=float(self.cfg.get("validation.min_confidence", 0.55)),
            require_inbound=bool(self.cfg.get("validation.require_inbound", True)),
            require_roi=bool(self.cfg.get("validation.require_roi", True)),
        )
        self.proximity = ProximityEstimator(
            self.roi,
            near_eta=float(self.cfg.get("proximity.near_eta_s", 6.0)),
            medium_eta=float(self.cfg.get("proximity.medium_eta_s", 15.0)),
            max_eta=float(self.cfg.get("proximity.max_eta_s", 120.0)),
        )
        self.priority = PriorityEngine(
            weights=self.cfg.get("priority.weights"),
            threshold=float(self.cfg.get("priority.threshold", 0.70)),
        )
        self.decider = DecisionEngine()
        self.fsm = TrafficSignalFSM(
            prepare_duration=float(self.cfg.get("signal.prepare_duration", 3)),
            all_red_duration=float(self.cfg.get("signal.all_red_duration", 2)),
            emergency_green_max=float(self.cfg.get("signal.emergency_green_max", 25)),
            clearance_duration=float(self.cfg.get("signal.clearance_duration", 5)),
            normal_phase_duration=float(self.cfg.get("signal.normal_phase_duration", 12)),
            on_event=self._on_fsm_event,
        )
        self.signals = SignalSimulator(
            self.fsm,
            normal_phase=float(self.cfg.get("signal.normal_phase_duration", 12)),
            yellow=float(self.cfg.get("signal.yellow_duration", 3)),
        )
        self.corridor = GreenCorridor(self.cfg.get("green_corridor.intersections") or [])
        self.perf = PerformanceMonitor()

        self.mode = self.cfg.mode
        self.detector: Optional[Detector] = None
        self.source: Optional[VideoSource] = None

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._jpeg: bytes = b""
        self._state: Dict = self._empty_state()
        self._emitted: Dict[str, float] = {}
        self._active_track: Optional[int] = None
        self.errors: List[str] = []
        self.model_status = "NOT_LOADED"
        self.running = False

    # ------------------------------------------------------------------
    def _empty_state(self) -> Dict:
        return {
            "running": False,
            "mode": getattr(self, "mode", "demo"),
            "simulated": True,
            "frame_id": 0,
            "timestamp": time.time(),
            "ambulances": [],
            "other_detections": 0,
            "decision": None,
            "signal": {"fsm": {"state": SignalState.NORMAL.value}, "lights": {
                "NORTH": "RED", "SOUTH": "RED", "EAST": "RED", "WEST": "RED"}},
            "green_corridor": {"intersections": [], "simulated": True},
            "health": {},
            "metrics": {},
        }

    # ------------------------------------------------------------------
    def start(self, source_override: Optional[str] = None,
              mode: Optional[str] = None) -> Dict:
        if self.running:
            return {"started": False, "reason": "ALREADY_RUNNING", "mode": self.mode}
        self.mode = (mode or self.cfg.mode).lower()
        self.errors = []
        if source_override:
            self.cfg.set("video.source", source_override)

        try:
            self.detector = build_detector(self.cfg, self.mode)
            self.model_status = self.detector.status
        except ModelNotFoundError as exc:
            self.model_status = "MODEL_ERROR"
            self.errors.append(str(exc))
            self._log_event("MODEL_ERROR", str(exc), level="ERROR")
            return {"started": False, "reason": "MODEL_NOT_FOUND", "detail": str(exc)}

        try:
            self.source = build_video_source(self.cfg)
            self.source.open()
        except VideoSourceError as exc:
            self.errors.append(str(exc))
            self._log_event("CAMERA_ERROR", str(exc), level="ERROR")
            return {"started": False, "reason": "CAMERA_ERROR", "detail": str(exc)}

        self.tracker.reset()
        self.validator.reset()
        self.trajectory.reset()
        self.corridor.reset()
        self.perf.start()
        self._emitted.clear()
        self._active_track = None
        self._stop.clear()
        self.running = True
        self._thread = threading.Thread(target=self._run, name="ais-pipeline", daemon=True)
        self._thread.start()
        self._log_event("PIPELINE_STARTED", f"mode={self.mode}")
        self.repo.sync_intersections(self.cfg.get("green_corridor.intersections") or [])
        return {"started": True, "mode": self.mode,
                "simulated": bool(self.detector and self.detector.simulated)}

    def stop(self) -> Dict:
        if not self.running:
            return {"stopped": False, "reason": "NOT_RUNNING"}
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self.source:
            self.source.release()
        self.running = False
        with self._lock:
            self._state["running"] = False
        self._log_event("PIPELINE_STOPPED", "")
        return {"stopped": True}

    def reset(self) -> Dict:
        self.stop()
        self.fsm.__init__(  # re-init with the same durations and listener
            prepare_duration=self.fsm.durations[SignalState.PREPARE],
            all_red_duration=self.fsm.durations[SignalState.ALL_RED],
            emergency_green_max=self.fsm.durations[SignalState.EMERGENCY_GREEN],
            clearance_duration=self.fsm.durations[SignalState.CLEARANCE],
            normal_phase_duration=self.fsm.durations[SignalState.NORMAL],
            on_event=self._on_fsm_event,
        )
        self.signals.fsm = self.fsm
        self.tracker.reset()
        self.validator.reset()
        self.trajectory.reset()
        self.corridor.reset()
        with self._lock:
            self._state = self._empty_state()
        self._log_event("SYSTEM_RESET", "")
        return {"reset": True}

    # ------------------------------------------------------------------
    def _run(self) -> None:
        target_fps = float(self.cfg.get("video.target_fps", 15) or 0)
        interval = 1.0 / target_fps if target_fps > 0 else 0.0
        while not self._stop.is_set():
            loop_start = time.perf_counter()
            try:
                self._process_once()
            except Exception as exc:  # pipeline must never die silently
                log.exception("pipeline iteration failed", extra={"event": "PIPELINE_ERROR"})
                self.errors.append(str(exc))
                self._log_event("PIPELINE_ERROR", str(exc), level="ERROR")
                time.sleep(0.25)
            if interval:
                sleep = interval - (time.perf_counter() - loop_start)
                if sleep > 0:
                    time.sleep(sleep)
        self.running = False

    # ------------------------------------------------------------------
    def _process_once(self) -> None:
        t_start = time.perf_counter()
        frame, meta = self.source.read()
        if frame is None or meta is None:
            self._log_event("CAMERA_ERROR", f"source status={self.source.status}",
                            level="ERROR")
            self.fsm.abort("CAMERA_ERROR")
            time.sleep(0.5)
            return

        t0 = time.perf_counter()
        detections = self.detector.detect(frame, meta)
        det_ms = (time.perf_counter() - t0) * 1000
        self.perf.record("detection_ms", det_ms)

        amb_dets = [d for d in detections if is_ambulance(d)]
        other_dets = [d for d in detections if not is_ambulance(d)]

        t0 = time.perf_counter()
        tracks = self.tracker.update(amb_dets, meta)
        track_ms = (time.perf_counter() - t0) * 1000
        self.perf.record("tracking_ms", track_ms)

        t0 = time.perf_counter()
        ambulances = []
        candidates = []
        for tr in tracks:
            cx, cy = tr.centroid
            roi_res = self.roi.classify(cx, cy, meta.width, meta.height)
            traj = self.trajectory.analyse(tr, meta.width, meta.height)
            prox = self.proximity.estimate(cx, cy, meta.width, meta.height, traj)
            val = self.validator.update(tr, roi_res, traj, meta.timestamp)
            prio = self.priority.score(
                detection_confidence=tr.confidence,
                temporal_frames=val.consecutive_frames,
                required_frames=self.validator.required_frames,
                approach_known=roi_res.approach != Approach.UNKNOWN.value,
                proximity_urgency=self.proximity.proximity_urgency(prox),
                eta_urgency=self.proximity.eta_urgency(prox),
                trajectory_confidence=traj.confidence,
            )
            decision = self.decider.decide(track=tr, roi_result=roi_res,
                                           trajectory=traj, proximity=prox,
                                           validation=val, priority=prio)
            entry = {
                "track_id": tr.track_id,
                "bbox": [round(v, 1) for v in tr.bbox],
                "confidence": round(tr.confidence, 3),
                "approach": roi_res.approach,
                "zone": roi_res.zone,
                "in_roi": roi_res.in_roi,
                "direction": ("INBOUND" if traj.motion_state == MotionState.APPROACHING.value
                              else "OUTBOUND" if traj.motion_state == MotionState.MOVING_AWAY.value
                              else traj.motion_state),
                "motion_state": traj.motion_state,
                "trajectory": traj.to_dict()["points"],
                "trajectory_info": traj.to_dict(),
                "proximity": prox.proximity,
                "relative_eta_s": prox.relative_eta_s,
                "proximity_note": prox.note,
                "validated": val.validated,
                "validation": val.to_dict(self.validator.required_frames),
                "priority": prio.to_dict(),
                "decision": decision.to_dict(),
                "confidence_history": [round(p.confidence, 3) for p in tr.history[-60:]],
                "simulated": self.detector.simulated,
            }
            ambulances.append(entry)
            self._per_track_events(tr, entry, meta)
            if decision.decision == "PRIORITY_REQUESTED":
                candidates.append(entry)
            if meta.frame_id % 3 == 0:
                self.repo.log_trajectory_point(
                    tr.track_id, meta.frame_id, cx, cy, tr.confidence, roi_res.zone,
                    roi_res.approach, prox.proximity, prox.relative_eta_s, meta.timestamp)
            self.repo.upsert_track(tr.track_id, roi_res.approach, tr.confidence,
                                   val.validated, self.detector.simulated, meta.timestamp)

        self._handle_priority(candidates, meta)
        self._handle_clearance(ambulances, meta)
        self.fsm.tick(meta.timestamp)
        decision_ms = (time.perf_counter() - t0) * 1000
        self.perf.record("decision_ms", decision_ms)

        signal_snapshot = self.signals.snapshot(meta.timestamp)
        corridor_status = self.corridor.update(self.fsm.state.value,
                                               self.fsm.priority_approach, meta.timestamp)
        self.repo.sync_intersections([
            {**i, "status": corridor_status.get(i["id"], "MONITOR")}
            for i in (self.cfg.get("green_corridor.intersections") or [])])

        # detections logged sparsely to keep the DB useful but small
        if meta.frame_id % 5 == 0:
            for d in amb_dets:
                self.repo.log_detection(d)

        annotated = annotate(frame, self.roi, ambulances,
                             [{"bbox": d.bbox} for d in other_dets],
                             signal_snapshot["lights"], self.fsm.state.value,
                             self.detector.simulated, meta.fps, meta.frame_id)
        jpeg = encode_jpeg(annotated)

        end_ms = (time.perf_counter() - t_start) * 1000
        self.perf.record("end_to_end_ms", end_ms)
        self.perf.frame_done()

        top = max(ambulances, key=lambda a: a["priority"]["score"], default=None)
        state = {
            "running": True,
            "mode": self.mode,
            "simulated": self.detector.simulated,
            "frame_id": meta.frame_id,
            "timestamp": meta.timestamp,
            "resolution": [meta.width, meta.height],
            "source_status": self.source.status,
            "ambulances": ambulances,
            "other_detections": len(other_dets),
            "decision": top["decision"] if top else None,
            "focus_track": top["track_id"] if top else None,
            "signal": signal_snapshot,
            "green_corridor": self.corridor.snapshot(),
            "health": self.health(),
            "metrics": self.perf.snapshot(),
            "roi": self.roi.to_dict(),
        }
        with self._lock:
            self._jpeg = jpeg
            self._state = state
        self.bus.publish("state", state)

    # ------------------------------------------------------------------
    def _per_track_events(self, tr, entry: Dict, meta) -> None:
        tid = tr.track_id
        if self._once(f"track_created:{tid}"):
            self._log_event("TRACK_CREATED", f"track {tid} created", track_id=tid,
                            payload={"confidence": entry["confidence"]},
                            timestamp=meta.timestamp)
            self._log_event("AMBULANCE_DETECTED", "ambulance detection associated",
                            track_id=tid, timestamp=meta.timestamp)
        if entry["approach"] != Approach.UNKNOWN.value and self._once(f"approach:{tid}:{entry['approach']}"):
            self._log_event("APPROACH_IDENTIFIED", f"approach {entry['approach']}",
                            track_id=tid, payload={"approach": entry["approach"]},
                            timestamp=meta.timestamp)
        if entry["validation"]["frames"] == 1 and self._once(f"valstart:{tid}"):
            self._log_event("VALIDATION_STARTED", "temporal validation started",
                            track_id=tid, timestamp=meta.timestamp)
        if entry["validated"] and self._once(f"validated:{tid}"):
            self._log_event("AMBULANCE_VALIDATED",
                            f"validated after {entry['validation']['frames']} frames",
                            track_id=tid, payload=entry["validation"],
                            timestamp=meta.timestamp)
            self._log_event("PRIORITY_SCORE_CALCULATED",
                            f"score {entry['priority']['score']}", track_id=tid,
                            payload=entry["priority"], timestamp=meta.timestamp)

    def _handle_priority(self, candidates: List[Dict], meta) -> None:
        if not candidates:
            return
        # deterministic priority queue: score desc, then lowest track id
        queue = sorted(candidates, key=lambda a: (-a["priority"]["score"], a["track_id"]))
        winner = queue[0]
        episode = self.fsm.episode

        for loser in queue[1:]:
            if self._once(f"conflict:{episode}:{loser['track_id']}"):
                self._log_event("PRIORITY_CONFLICT",
                                f"track {loser['track_id']} deferred to {winner['track_id']}",
                                level="WARNING", track_id=loser["track_id"],
                                payload={"winner": winner["track_id"],
                                         "winner_score": winner["priority"]["score"],
                                         "score": loser["priority"]["score"]},
                                timestamp=meta.timestamp)

        # the ambulance currently being served needs no repeated request
        if self.fsm.state is not SignalState.NORMAL and self.fsm.track_id == winner["track_id"]:
            return
        # one request per track per emergency episode keeps the log readable
        if not self._once(f"request:{episode}:{winner['track_id']}"):
            return

        result = self.fsm.request_priority(winner["approach"], winner["track_id"],
                                           winner["priority"]["score"])
        if result.accepted:
            self._active_track = winner["track_id"]
        self.repo.log_priority_event(
            track_id=winner["track_id"], approach=winner["approach"],
            confidence=winner["confidence"], proximity=winner["proximity"],
            relative_eta=winner["relative_eta_s"],
            priority_score=winner["priority"]["score"],
            decision=winner["decision"]["decision"],
            reason_codes=winner["decision"]["reason_codes"],
            accepted=result.accepted, simulated=self.detector.simulated,
            timestamp=meta.timestamp)
        if not result.accepted and result.reason == "REQUEST_REJECTED":
            self._log_event("REQUEST_REJECTED",
                            f"priority request for track {winner['track_id']} rejected "
                            f"({self.fsm.state.value} active)", level="WARNING",
                            track_id=winner["track_id"], timestamp=meta.timestamp)

    def _handle_clearance(self, ambulances: List[Dict], meta) -> None:
        if self.fsm.state is not SignalState.EMERGENCY_GREEN:
            return
        tid = self.fsm.track_id
        entry = next((a for a in ambulances if a["track_id"] == tid), None)
        if entry is None:
            if tid in getattr(self.tracker, "lost_track_ids", []):
                self._log_event("TRACK_LOST", f"track {tid} lost during emergency green",
                                level="WARNING", track_id=tid, timestamp=meta.timestamp)
            self.fsm.ambulance_cleared(tid)
            return
        passed = (entry["motion_state"] == MotionState.MOVING_AWAY.value
                  and entry["zone"] in (Zone.CONTROL_ZONE.value, Zone.NEAR_ZONE.value,
                                        Zone.CLEARANCE_ZONE.value, Zone.MEDIUM_ZONE.value))
        if passed:
            self.fsm.ambulance_cleared(tid)

    # ------------------------------------------------------------------
    def _on_fsm_event(self, event: str, payload: Dict) -> None:
        self.repo.log_signal_event(
            from_state=payload.get("from", ""), signal_state=event.replace("FSM_", ""),
            reason=payload.get("reason", event), approach=payload.get("approach"),
            track_id=self.fsm.track_id,
            accepted=event not in ("TRANSITION_REJECTED", "REQUEST_REJECTED"))
        self._log_event(event, payload.get("reason", ""), track_id=self.fsm.track_id,
                        payload=payload,
                        level="WARNING" if "REJECTED" in event else "INFO")
        if event == "FSM_NORMAL":
            self._log_event("NORMAL_OPERATION", "intersection back to normal",
                            track_id=None)

    def _once(self, key: str) -> bool:
        if key in self._emitted:
            return False
        self._emitted[key] = time.time()
        if len(self._emitted) > 4000:
            self._emitted.clear()
        return True

    def _log_event(self, event_type: str, message: str = "", level: str = "INFO",
                   track_id: Optional[int] = None, payload: Optional[Dict] = None,
                   timestamp: Optional[float] = None) -> None:
        self.repo.log_system_event(event_type, message=message, level=level,
                                   track_id=track_id, payload=payload,
                                   timestamp=timestamp)
        log.info(message or event_type, extra={"event": event_type, "track_id": track_id})
        self.bus.publish("event", {"event_type": event_type, "message": message,
                                   "level": level, "track_id": track_id,
                                   "timestamp": timestamp or time.time(),
                                   "metadata": payload or {}})

    # ------------------------------------------------------------------
    def health(self) -> Dict[str, str]:
        return {
            "camera": (self.source.status if self.source else "OFFLINE"),
            "model": (self.detector.status if self.detector else self.model_status),
            "tracker": self.tracker.status if self.running else "IDLE",
            "database": self.repo.status,
            "api": "ONLINE",
            "mode": self.mode.upper(),
            "simulated": ("YES" if self.detector.simulated else "NO") if self.detector else "PENDING",
        }

    def snapshot(self) -> Dict:
        with self._lock:
            state = dict(self._state)
        state["health"] = self.health()
        state["running"] = self.running
        state["errors"] = self.errors[-5:]
        return state

    def latest_jpeg(self) -> bytes:
        with self._lock:
            return self._jpeg
