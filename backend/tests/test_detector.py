"""Detector layer tests."""
from __future__ import annotations

import numpy as np
import pytest

from app.core.types import FrameMeta
from app.vision.detector import (DemoDetector, ModelNotFoundError, YOLODetector,
                                 build_detector, is_ambulance)


def _meta(frame_id=1, w=960, h=540):
    return FrameMeta(frame_id, 1000.0, w, h, 15.0)


def test_demo_detector_produces_labelled_simulated_detections():
    det = DemoDetector(nominal_fps=15)
    det.load()
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    found = []
    for fid in range(1, 200):
        found += det.detect(frame, _meta(fid))
    assert found, "demo detector produced no detections"
    assert all(d.simulated for d in found)
    assert all(d.source == "demo-simulation" for d in found)
    assert any(is_ambulance(d) for d in found)


def test_demo_detections_are_reproducible():
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    a = DemoDetector(15).detect(frame, _meta(60))
    b = DemoDetector(15).detect(frame, _meta(60))
    assert [d.bbox for d in a] == [d.bbox for d in b]


def test_yolo_detector_reports_missing_model_clearly(tmp_path):
    det = YOLODetector(tmp_path / "ambulance_yolov8.pt")
    with pytest.raises(ModelNotFoundError) as exc:
        det.load()
    assert "MODEL NOT FOUND" in str(exc.value)
    assert det.status == "MODEL_ERROR"


def test_detect_before_load_raises(tmp_path):
    det = YOLODetector(tmp_path / "missing.pt")
    with pytest.raises(ModelNotFoundError):
        det.detect(np.zeros((10, 10, 3), dtype=np.uint8), _meta())


def test_build_detector_demo_mode_is_simulated(cfg):
    det = build_detector(cfg, "demo")
    assert det.simulated is True
    assert "DEMO" in det.status
