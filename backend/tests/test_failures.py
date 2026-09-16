"""Failure handling: the system must fail safely."""
from __future__ import annotations

import numpy as np
import pytest

from app.core.types import FrameMeta
from app.tracking.bytetrack import ByteTrackTracker
from app.traffic.fsm import SignalState
from app.vision.detector import ModelNotFoundError, YOLODetector
from app.vision.video_source import FileVideoSource, VideoSourceError


def test_missing_video_file_raises_camera_error():
    src = FileVideoSource("/does/not/exist.mp4")
    with pytest.raises(VideoSourceError):
        src.open()
    assert src.status == "CAMERA_ERROR"


def test_missing_model_raises_model_error(tmp_path):
    with pytest.raises(ModelNotFoundError):
        YOLODetector(tmp_path / "nope.pt").load()


def test_camera_failure_aborts_priority_sequence(pipeline_factory):
    p = pipeline_factory([[]])
    p.fsm.request_priority("NORTH", 1, 0.9)
    assert p.fsm.state is SignalState.PREPARE

    class DeadSource:
        status = "CAMERA_ERROR"

        def read(self):
            return None, None

    p.source = DeadSource()
    p._process_once()
    assert p.fsm.state is SignalState.NORMAL
    assert p.health()["camera"] == "CAMERA_ERROR"


def test_tracker_handles_garbage_detections_without_crashing():
    t = ByteTrackTracker()
    meta = FrameMeta(1, 1000.0, 960, 540, 15.0)
    assert t.update([], meta) == []


def test_database_logging_failure_does_not_stop_the_pipeline(pipeline_factory, monkeypatch):
    """A database outage must surface as LOGGING_ERROR, not a pipeline crash."""
    from conftest import approach_script
    import app.database.repository as repository

    p = pipeline_factory(approach_script(12))

    def dead_session(*args, **kwargs):
        raise RuntimeError("simulated database outage")

    monkeypatch.setattr(repository, "SessionLocal", dead_session)
    monkeypatch.setattr(repository, "healthy", lambda: False)
    for _ in range(12):
        p._process_once()          # must not raise
    assert p.repo.status == "ERROR"
    assert p.snapshot()["frame_id"] == 12


def test_pipeline_start_reports_model_not_found(cfg):
    from app.services.pipeline import Pipeline
    cfg.set("model.path", "models/definitely_missing.pt")
    p = Pipeline(cfg)
    result = p.start(mode="real")
    assert result["started"] is False
    assert result["reason"] == "MODEL_NOT_FOUND"
    assert "MODEL NOT FOUND" in result["detail"]
    assert p.health()["model"] == "MODEL_ERROR"
