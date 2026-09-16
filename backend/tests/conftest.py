"""Shared fixtures.

The integration fixtures drive the REAL Pipeline object with a scripted
detector, so the tests exercise production code paths rather than a parallel
implementation.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import load_config                      # noqa: E402
from app.core.types import Detection, FrameMeta              # noqa: E402
from app.database.db import init_db                          # noqa: E402
from app.vision.detector import Detector                     # noqa: E402
from app.vision.video_source import SyntheticSource          # noqa: E402

WIDTH, HEIGHT = 960, 540


class ScriptedDetector(Detector):
    """Returns pre-computed detections for each frame index."""

    name = "scripted"
    simulated = True

    def __init__(self, script: List[List[Detection]]):
        self.script = script
        self.index = 0

    def load(self) -> None:
        pass

    @property
    def status(self) -> str:
        return "READY (SCRIPTED)"

    def detect(self, frame: np.ndarray, meta: FrameMeta) -> List[Detection]:
        dets = self.script[self.index] if self.index < len(self.script) else []
        self.index += 1
        out = []
        for d in dets:
            out.append(Detection(d.class_name, d.confidence, d.bbox, meta.timestamp,
                                 meta.frame_id, "scripted", True))
        return out


def box(cx: float, cy: float, w: float = 70, h: float = 50):
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def ambulance(cx: float, cy: float, conf: float = 0.85) -> Detection:
    return Detection("ambulance", conf, box(cx, cy), time.time(), 0, "scripted", True)


def approach_script(frames: int, start_y: float = 30.0, end_y: float = 300.0,
                    conf: float = 0.85, cx: float = 470.0) -> List[List[Detection]]:
    """Ambulance travelling down the NORTH approach toward the intersection."""
    step = (end_y - start_y) / max(1, frames - 1)
    return [[ambulance(cx, start_y + i * step, conf)] for i in range(frames)]


def departing_script(frames: int) -> List[List[Detection]]:
    """Ambulance moving away from the intersection along the EAST approach."""
    return [[ambulance(620 + i * 12, 300)] for i in range(frames)]


@pytest.fixture(scope="session", autouse=True)
def _database(tmp_path_factory):
    db_dir = tmp_path_factory.mktemp("ais-db")
    init_db(f"sqlite:///{db_dir}/test.db")
    yield


@pytest.fixture
def cfg():
    c = load_config()
    c.set("video.target_fps", 0)
    c.set("signal.prepare_duration", 0.05)
    c.set("signal.all_red_duration", 0.05)
    c.set("signal.emergency_green_max", 5)
    c.set("signal.clearance_duration", 0.05)
    c.set("database.url", "sqlite:///data/test_runtime.db")
    return c


@pytest.fixture
def pipeline_factory(cfg):
    from app.services.pipeline import Pipeline

    created = []

    def _make(script: List[List[Detection]], **overrides) -> "Pipeline":
        for key, value in overrides.items():
            cfg.set(key, value)
        p = Pipeline(cfg)
        p.detector = ScriptedDetector(script)
        p.source = SyntheticSource(WIDTH, HEIGHT)
        p.source.open()
        p.mode = "demo"
        p.perf.start()
        created.append(p)
        return p

    yield _make
    for p in created:
        if p.running:
            p.stop()


def run_frames(pipeline, count: int, sleep: float = 0.0) -> List[Dict]:
    """Step the real pipeline synchronously and collect per-frame snapshots."""
    states = []
    for _ in range(count):
        pipeline._process_once()
        states.append(pipeline.snapshot())
        if sleep:
            time.sleep(sleep)
    return states
