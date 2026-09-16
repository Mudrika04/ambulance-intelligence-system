"""Repository layer - the only place that talks to the ORM."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from sqlalchemy import desc, select

from ..core.logging_conf import get_logger
from ..models import entities as E
from .db import SessionLocal, healthy

log = get_logger(__name__)


def _ts(value: Optional[float]) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(value, tz=timezone.utc)


class Repository(ABC):
    @abstractmethod
    def log_system_event(self, event_type: str, **kw) -> None: ...

    @abstractmethod
    def recent_events(self, limit: int = 100) -> List[dict]: ...


class SQLiteRepository(Repository):
    """SQLAlchemy-backed repository. Logging failures never crash the pipeline."""

    def __init__(self):
        self.last_error: Optional[str] = None

    # --- internals ---------------------------------------------------
    def _write(self, obj_or_list):
        try:
            with SessionLocal() as s:
                if isinstance(obj_or_list, (list, tuple)):
                    s.add_all(obj_or_list)
                else:
                    s.add(obj_or_list)
                s.commit()
            self.last_error = None
            return True
        except Exception as exc:  # LOGGING_ERROR - never fatal
            self.last_error = str(exc)
            log.error("database write failed", extra={"event": "LOGGING_ERROR"})
            return False

    @property
    def status(self) -> str:
        if not healthy():
            return "ERROR"
        return "ERROR" if self.last_error else "CONNECTED"

    # --- writes ------------------------------------------------------
    def log_detection(self, det, track_id: Optional[int] = None) -> None:
        self._write(E.Detection(timestamp=_ts(det.timestamp), frame_id=det.frame_id,
                                track_id=track_id, class_name=det.class_name,
                                confidence=det.confidence, bbox=list(det.bbox),
                                source=det.source, simulated=det.simulated))

    def upsert_track(self, track_id: int, approach: str, confidence: float,
                     validated: bool, simulated: bool, timestamp: float,
                     intersection_id: str = "INT-01") -> None:
        try:
            with SessionLocal() as s:
                row = s.scalar(select(E.Track).where(E.Track.track_id == track_id)
                               .order_by(desc(E.Track.id)).limit(1))
                if row is None:
                    row = E.Track(track_id=track_id, first_seen=_ts(timestamp),
                                  intersection_id=intersection_id, simulated=simulated)
                    s.add(row)
                row.last_seen = _ts(timestamp)
                if approach and approach != "UNKNOWN":
                    row.approach = approach
                row.max_confidence = max(row.max_confidence or 0.0, confidence)
                row.validated = bool(row.validated or validated)
                row.frames = (row.frames or 0) + 1
                s.commit()
            self.last_error = None
        except Exception as exc:
            self.last_error = str(exc)
            log.error("track upsert failed", extra={"event": "LOGGING_ERROR"})

    def log_trajectory_point(self, track_id: int, frame_id: int, cx: float, cy: float,
                             confidence: float, zone: str, approach: str,
                             proximity: str, relative_eta: Optional[float],
                             timestamp: float) -> None:
        self._write(E.TrajectoryPoint(timestamp=_ts(timestamp), track_id=track_id,
                                      frame_id=frame_id, cx=cx, cy=cy,
                                      confidence=confidence, zone=zone,
                                      approach=approach, proximity=proximity,
                                      relative_eta=relative_eta))

    def log_priority_event(self, *, track_id: int, approach: str, confidence: float,
                           proximity: str, relative_eta, priority_score: float,
                           decision: str, reason_codes: Iterable[str], accepted: bool,
                           simulated: bool, timestamp: float,
                           intersection_id: str = "INT-01") -> None:
        self._write(E.PriorityEvent(timestamp=_ts(timestamp), track_id=track_id,
                                    intersection_id=intersection_id, approach=approach,
                                    confidence=confidence, proximity=proximity,
                                    relative_eta=relative_eta,
                                    priority_score=priority_score, decision=decision,
                                    reason_codes=list(reason_codes), accepted=accepted,
                                    simulated=simulated))

    def log_signal_event(self, *, from_state: str, signal_state: str, reason: str,
                         approach: Optional[str], track_id: Optional[int],
                         accepted: bool = True, timestamp: Optional[float] = None,
                         intersection_id: str = "INT-01") -> None:
        self._write(E.SignalEvent(timestamp=_ts(timestamp), from_state=from_state,
                                  signal_state=signal_state, reason=reason,
                                  approach=approach, track_id=track_id,
                                  accepted=accepted, intersection_id=intersection_id))

    def log_system_event(self, event_type: str, message: str = "", level: str = "INFO",
                         track_id: Optional[int] = None,
                         intersection_id: Optional[str] = None,
                         payload: Optional[dict] = None,
                         timestamp: Optional[float] = None) -> None:
        self._write(E.SystemEvent(timestamp=_ts(timestamp), event_type=event_type,
                                  message=message, level=level, track_id=track_id,
                                  intersection_id=intersection_id, payload=payload or {}))

    def sync_intersections(self, intersections: List[dict]) -> None:
        try:
            with SessionLocal() as s:
                for item in intersections:
                    row = s.scalar(select(E.Intersection)
                                   .where(E.Intersection.intersection_id == item["id"]))
                    if row is None:
                        row = E.Intersection(intersection_id=item["id"])
                        s.add(row)
                    row.name = item.get("name", item["id"])
                    row.role = item.get("role", "downstream")
                    row.status = item.get("status", "MONITOR")
                    row.updated_at = datetime.now(timezone.utc)
                s.commit()
        except Exception as exc:
            self.last_error = str(exc)

    def save_experiment(self, *, experiment_id: str, scenario: str, mode: str,
                        configuration: dict, results: dict, notes: str = "") -> None:
        self._write(E.Experiment(experiment_id=experiment_id, scenario=scenario,
                                 mode=mode, configuration=configuration,
                                 results=results, notes=notes,
                                 finished_at=datetime.now(timezone.utc)))

    def save_metric(self, name: str, value: float, unit: str = "",
                    experiment_id: Optional[str] = None,
                    context: Optional[dict] = None) -> None:
        self._write(E.Metric(name=name, value=value, unit=unit,
                             experiment_id=experiment_id, context=context or {}))

    # --- reads -------------------------------------------------------
    def recent_events(self, limit: int = 100, event_type: Optional[str] = None,
                      track_id: Optional[int] = None) -> List[dict]:
        with SessionLocal() as s:
            q = select(E.SystemEvent).order_by(desc(E.SystemEvent.timestamp)).limit(limit)
            if event_type:
                q = select(E.SystemEvent).where(E.SystemEvent.event_type == event_type)\
                    .order_by(desc(E.SystemEvent.timestamp)).limit(limit)
            if track_id is not None:
                q = select(E.SystemEvent).where(E.SystemEvent.track_id == track_id)\
                    .order_by(E.SystemEvent.timestamp).limit(limit)
            rows = list(s.scalars(q))
        return [{"id": r.id, "timestamp": r.timestamp.isoformat(),
                 "event_type": r.event_type, "level": r.level, "track_id": r.track_id,
                 "intersection_id": r.intersection_id, "message": r.message,
                 "metadata": r.payload} for r in rows]

    def recent_detections(self, limit: int = 100) -> List[dict]:
        with SessionLocal() as s:
            rows = list(s.scalars(select(E.Detection)
                                  .order_by(desc(E.Detection.id)).limit(limit)))
        return [{"id": r.id, "timestamp": r.timestamp.isoformat(), "frame_id": r.frame_id,
                 "track_id": r.track_id, "class_name": r.class_name,
                 "confidence": r.confidence, "bbox": r.bbox, "source": r.source,
                 "simulated": r.simulated} for r in rows]

    def tracks(self, limit: int = 100) -> List[dict]:
        with SessionLocal() as s:
            rows = list(s.scalars(select(E.Track).order_by(desc(E.Track.id)).limit(limit)))
        return [{"track_id": r.track_id, "approach": r.approach,
                 "first_seen": r.first_seen.isoformat(), "last_seen": r.last_seen.isoformat(),
                 "max_confidence": r.max_confidence, "validated": r.validated,
                 "frames": r.frames, "simulated": r.simulated} for r in rows]

    def priority_events(self, limit: int = 50) -> List[dict]:
        with SessionLocal() as s:
            rows = list(s.scalars(select(E.PriorityEvent)
                                  .order_by(desc(E.PriorityEvent.id)).limit(limit)))
        return [{"id": r.id, "timestamp": r.timestamp.isoformat(), "track_id": r.track_id,
                 "approach": r.approach, "confidence": r.confidence,
                 "proximity": r.proximity, "relative_eta": r.relative_eta,
                 "priority_score": r.priority_score, "decision": r.decision,
                 "reason_codes": r.reason_codes, "accepted": r.accepted,
                 "simulated": r.simulated} for r in rows]

    def signal_events(self, limit: int = 50) -> List[dict]:
        with SessionLocal() as s:
            rows = list(s.scalars(select(E.SignalEvent)
                                  .order_by(desc(E.SignalEvent.id)).limit(limit)))
        return [{"id": r.id, "timestamp": r.timestamp.isoformat(),
                 "from_state": r.from_state, "signal_state": r.signal_state,
                 "approach": r.approach, "track_id": r.track_id,
                 "reason": r.reason, "accepted": r.accepted} for r in rows]

    def trajectory(self, track_id: int) -> List[dict]:
        with SessionLocal() as s:
            rows = list(s.scalars(select(E.TrajectoryPoint)
                                  .where(E.TrajectoryPoint.track_id == track_id)
                                  .order_by(E.TrajectoryPoint.id)))
        return [{"timestamp": r.timestamp.isoformat(), "frame_id": r.frame_id,
                 "cx": r.cx, "cy": r.cy, "confidence": r.confidence, "zone": r.zone,
                 "approach": r.approach, "proximity": r.proximity,
                 "relative_eta": r.relative_eta} for r in rows]

    def replay(self, track_id: int) -> dict:
        with SessionLocal() as s:
            sys_events = list(s.scalars(select(E.SystemEvent)
                                        .where(E.SystemEvent.track_id == track_id)
                                        .order_by(E.SystemEvent.timestamp)))
            prio = list(s.scalars(select(E.PriorityEvent)
                                  .where(E.PriorityEvent.track_id == track_id)
                                  .order_by(E.PriorityEvent.timestamp)))
            sig = list(s.scalars(select(E.SignalEvent)
                                 .where(E.SignalEvent.track_id == track_id)
                                 .order_by(E.SignalEvent.timestamp)))
            track = s.scalar(select(E.Track).where(E.Track.track_id == track_id)
                             .order_by(desc(E.Track.id)).limit(1))
        return {
            "track_id": track_id,
            "track": None if track is None else {
                "approach": track.approach, "validated": track.validated,
                "frames": track.frames, "max_confidence": track.max_confidence,
                "first_seen": track.first_seen.isoformat(),
                "last_seen": track.last_seen.isoformat(),
                "simulated": track.simulated},
            "timeline": [{"timestamp": r.timestamp.isoformat(),
                          "event_type": r.event_type, "message": r.message,
                          "metadata": r.payload} for r in sys_events],
            "priority_events": [{"timestamp": r.timestamp.isoformat(),
                                 "decision": r.decision,
                                 "priority_score": r.priority_score,
                                 "reason_codes": r.reason_codes,
                                 "approach": r.approach,
                                 "proximity": r.proximity,
                                 "relative_eta": r.relative_eta} for r in prio],
            "signal_events": [{"timestamp": r.timestamp.isoformat(),
                               "from_state": r.from_state,
                               "signal_state": r.signal_state,
                               "reason": r.reason, "accepted": r.accepted} for r in sig],
            "trajectory": self.trajectory(track_id),
        }

    def experiments(self, limit: int = 25) -> List[dict]:
        with SessionLocal() as s:
            rows = list(s.scalars(select(E.Experiment)
                                  .order_by(desc(E.Experiment.id)).limit(limit)))
        return [{"experiment_id": r.experiment_id, "scenario": r.scenario, "mode": r.mode,
                 "configuration": r.configuration, "results": r.results,
                 "started_at": r.started_at.isoformat(),
                 "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                 "notes": r.notes} for r in rows]

    def metrics(self, limit: int = 200) -> List[dict]:
        with SessionLocal() as s:
            rows = list(s.scalars(select(E.Metric).order_by(desc(E.Metric.id)).limit(limit)))
        return [{"timestamp": r.timestamp.isoformat(), "name": r.name, "value": r.value,
                 "unit": r.unit, "experiment_id": r.experiment_id,
                 "context": r.context} for r in rows]

    def validated_track_ids(self, limit: int = 25) -> List[int]:
        with SessionLocal() as s:
            rows = list(s.scalars(select(E.Track.track_id)
                                  .where(E.Track.validated.is_(True))
                                  .order_by(desc(E.Track.id)).limit(limit)))
        return [int(r) for r in rows]
