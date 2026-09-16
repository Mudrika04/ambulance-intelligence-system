"""SQLAlchemy ORM entities."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, DateTime, Float, Integer, JSON, String,
                        Text, Index)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Detection(Base):
    __tablename__ = "detections"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=utcnow, index=True)
    frame_id = Column(Integer, index=True)
    track_id = Column(Integer, index=True, nullable=True)
    class_name = Column(String(48))
    confidence = Column(Float)
    bbox = Column(JSON)
    source = Column(String(32))
    simulated = Column(Boolean, default=False)


class Track(Base):
    __tablename__ = "tracks"
    id = Column(Integer, primary_key=True)
    track_id = Column(Integer, index=True)
    intersection_id = Column(String(16), default="INT-01")
    first_seen = Column(DateTime, default=utcnow)
    last_seen = Column(DateTime, default=utcnow)
    approach = Column(String(16))
    max_confidence = Column(Float, default=0.0)
    validated = Column(Boolean, default=False)
    frames = Column(Integer, default=0)
    simulated = Column(Boolean, default=False)


class TrajectoryPoint(Base):
    __tablename__ = "trajectory_points"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=utcnow, index=True)
    track_id = Column(Integer, index=True)
    frame_id = Column(Integer)
    cx = Column(Float)
    cy = Column(Float)
    confidence = Column(Float)
    zone = Column(String(24))
    approach = Column(String(16))
    proximity = Column(String(16))
    relative_eta = Column(Float, nullable=True)


class PriorityEvent(Base):
    __tablename__ = "priority_events"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=utcnow, index=True)
    track_id = Column(Integer, index=True)
    intersection_id = Column(String(16), default="INT-01")
    approach = Column(String(16))
    confidence = Column(Float)
    proximity = Column(String(16))
    relative_eta = Column(Float, nullable=True)
    priority_score = Column(Float)
    decision = Column(String(32))
    reason_codes = Column(JSON)
    accepted = Column(Boolean, default=False)
    simulated = Column(Boolean, default=False)


class SignalEvent(Base):
    __tablename__ = "signal_events"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=utcnow, index=True)
    intersection_id = Column(String(16), default="INT-01")
    track_id = Column(Integer, nullable=True)
    from_state = Column(String(24))
    signal_state = Column(String(24))
    approach = Column(String(16), nullable=True)
    reason = Column(String(64))
    accepted = Column(Boolean, default=True)


class SystemEvent(Base):
    __tablename__ = "system_events"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=utcnow, index=True)
    event_type = Column(String(48), index=True)
    level = Column(String(16), default="INFO")
    track_id = Column(Integer, nullable=True, index=True)
    intersection_id = Column(String(16), nullable=True)
    message = Column(Text, default="")
    payload = Column("metadata", JSON)


class Intersection(Base):
    __tablename__ = "intersections"
    id = Column(Integer, primary_key=True)
    intersection_id = Column(String(16), unique=True)
    name = Column(String(64))
    role = Column(String(24))
    status = Column(String(24), default="MONITOR")
    updated_at = Column(DateTime, default=utcnow)


class Experiment(Base):
    __tablename__ = "experiments"
    id = Column(Integer, primary_key=True)
    experiment_id = Column(String(48), unique=True, index=True)
    scenario = Column(String(64))
    mode = Column(String(32))
    configuration = Column(JSON)
    started_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime, nullable=True)
    results = Column(JSON)
    notes = Column(Text, default="")


class Metric(Base):
    __tablename__ = "metrics"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=utcnow, index=True)
    experiment_id = Column(String(48), nullable=True, index=True)
    name = Column(String(48), index=True)
    value = Column(Float)
    unit = Column(String(24), default="")
    context = Column(JSON)


Index("ix_system_events_type_time", SystemEvent.event_type, SystemEvent.timestamp)
