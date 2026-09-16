"""Pydantic request/response schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    components: Dict[str, str]
    mode: str
    version: str
    timestamp: float


class StartVideoRequest(BaseModel):
    source: Optional[str] = Field(None, description="Path, camera index or RTSP URL")
    source_type: Optional[str] = Field(None, pattern="^(file|webcam|rtsp)$")
    mode: Optional[str] = Field(None, pattern="^(demo|real)$")


class SimpleResult(BaseModel):
    ok: bool
    detail: Dict[str, Any] = {}


class ConfigUpdate(BaseModel):
    updates: Dict[str, Any] = Field(
        ..., description="Dotted config paths, e.g. {'priority.threshold': 0.8}")


class ExperimentRequest(BaseModel):
    scenario: str = "default"
    arrivals: int = Field(20, ge=1, le=500)
    seed: int = 42


class EventItem(BaseModel):
    id: Optional[int] = None
    timestamp: str
    event_type: str
    level: str = "INFO"
    track_id: Optional[int] = None
    message: str = ""
    metadata: Dict[str, Any] = {}


class ReplayResponse(BaseModel):
    track_id: int
    track: Optional[Dict[str, Any]] = None
    timeline: List[Dict[str, Any]] = []
    priority_events: List[Dict[str, Any]] = []
    signal_events: List[Dict[str, Any]] = []
    trajectory: List[Dict[str, Any]] = []
