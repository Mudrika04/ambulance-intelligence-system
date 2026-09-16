"""Detector abstraction with a real YOLOv8 implementation and a demo fallback."""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

import numpy as np

from ..core.logging_conf import get_logger
from ..core.types import Detection, FrameMeta
from . import scenario

log = get_logger(__name__)

AMBULANCE_ALIASES = {"ambulance", "emergency_vehicle", "emergency-vehicle", "ems"}


class ModelNotFoundError(RuntimeError):
    """Raised when REAL MODEL MODE is requested but the weights are absent."""


class Detector(ABC):
    name: str = "detector"
    simulated: bool = False

    @abstractmethod
    def load(self) -> None: ...

    @abstractmethod
    def detect(self, frame: np.ndarray, meta: FrameMeta) -> List[Detection]: ...

    @property
    def status(self) -> str:
        return "READY"


class YOLODetector(Detector):
    """Real Ultralytics YOLOv8 inference. No hard-coded detections, ever."""

    name = "yolov8"
    simulated = False

    def __init__(self, model_path: str | Path, conf: float = 0.6,
                 iou: float = 0.45, device: str = "cpu",
                 ambulance_classes: Optional[List[str]] = None):
        self.model_path = Path(model_path)
        self.conf = conf
        self.iou = iou
        self.device = device
        self.ambulance_classes = {c.lower() for c in (ambulance_classes or ["ambulance"])}
        self._model = None
        self._status = "NOT_LOADED"

    @property
    def status(self) -> str:
        return self._status

    def load(self) -> None:
        if not self.model_path.exists():
            self._status = "MODEL_ERROR"
            raise ModelNotFoundError(
                "MODEL NOT FOUND\n"
                f"Expected a trained YOLOv8 ambulance model at: {self.model_path}\n"
                "Place your trained weights there (file name must match "
                "configs/config.yaml -> model.path), for example:\n"
                "    models/ambulance_yolov8.pt\n"
                "Then start the backend with mode=real (AIS_MODE=real).\n"
                "Until a model is supplied, use DEMO / SIMULATION MODE."
            )
        try:
            from ultralytics import YOLO  # imported lazily: heavy dependency
        except ImportError as exc:  # pragma: no cover - env dependent
            self._status = "MODEL_ERROR"
            raise ModelNotFoundError(
                "Ultralytics is not installed. Install it with:\n"
                "    pip install ultralytics\n"
                "REAL MODEL MODE requires ultralytics + a trained ambulance model."
            ) from exc
        self._model = YOLO(str(self.model_path))
        self._status = "READY"
        names = getattr(self._model, "names", {}) or {}
        found = {str(v).lower() for v in names.values()} & self.ambulance_classes
        if not found:
            log.warning(
                "loaded model exposes no ambulance class; ambulance detections will be empty",
                extra={"event": "MODEL_CLASS_WARNING"})
        log.info("YOLO model loaded", extra={"event": "MODEL_LOADED"})

    def detect(self, frame: np.ndarray, meta: FrameMeta) -> List[Detection]:
        if self._model is None:
            raise ModelNotFoundError("YOLODetector.load() must be called before detect()")
        results = self._model.predict(frame, conf=self.conf, iou=self.iou,
                                      device=self.device, verbose=False)
        out: List[Detection] = []
        for res in results:
            names = res.names
            boxes = getattr(res, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls.item())
                conf = float(box.conf.item())
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                out.append(Detection(
                    class_name=str(names.get(cls_id, cls_id)),
                    confidence=conf,
                    bbox=(x1, y1, x2, y2),
                    timestamp=meta.timestamp,
                    frame_id=meta.frame_id,
                    source="yolo",
                    simulated=False,
                ))
        return out


class DemoDetector(Detector):
    """DEMO / SIMULATION detector.

    Produces scripted detections (with jitter, dropouts and a periodic
    single-frame false positive) so the full pipeline can be demonstrated
    without a trained model. Every detection it returns is flagged
    simulated=True and is labelled DEMO / SIMULATION in the UI.
    """

    name = "demo-simulation"
    simulated = True

    def __init__(self, nominal_fps: float = 15.0, seed: int = 7):
        self.nominal_fps = nominal_fps or 15.0
        self._rng = random.Random(seed)

    def load(self) -> None:
        log.info("demo detector active (simulated detections)",
                 extra={"event": "DEMO_DETECTOR_LOADED"})

    @property
    def status(self) -> str:
        return "READY (DEMO)"

    def detect(self, frame: np.ndarray, meta: FrameMeta) -> List[Detection]:
        t = meta.frame_id / self.nominal_fps
        rng = random.Random(meta.frame_id * 9176 + 13)
        dets: List[Detection] = []
        for obj in scenario.objects_at(t):
            if obj.occluded and rng.random() < 0.85:
                continue  # simulated detection loss during occlusion
            x1, y1, x2, y2 = scenario.to_pixel_bbox(obj, meta.width, meta.height)
            jitter = lambda: rng.uniform(-2.5, 2.5)
            base = 0.83 if obj.cls == "ambulance" else 0.74
            conf = min(0.97, max(0.35, base + rng.uniform(-0.09, 0.11)))
            dets.append(Detection(
                class_name=obj.cls,
                confidence=conf,
                bbox=(x1 + jitter(), y1 + jitter(), x2 + jitter(), y2 + jitter()),
                timestamp=meta.timestamp,
                frame_id=meta.frame_id,
                source="demo-simulation",
                simulated=True,
            ))
        # periodic single-frame false positive: demonstrates that temporal
        # validation refuses to escalate a one-frame detection
        if meta.frame_id % 137 == 0:
            w, h = meta.width, meta.height
            cx, cy = rng.uniform(0.15, 0.85) * w, rng.uniform(0.15, 0.85) * h
            dets.append(Detection("ambulance", 0.63,
                                  (cx - 34, cy - 26, cx + 34, cy + 26),
                                  meta.timestamp, meta.frame_id,
                                  "demo-simulation", True))
        return dets


def build_detector(cfg, mode: Optional[str] = None) -> Detector:
    mode = (mode or cfg.mode).lower()
    if mode == "real":
        det = YOLODetector(
            cfg.resolve("model.path"),
            conf=float(cfg.get("model.confidence_threshold", 0.6)),
            iou=float(cfg.get("model.iou_threshold", 0.45)),
            device=str(cfg.get("model.device", "cpu")),
            ambulance_classes=cfg.get("model.ambulance_classes", ["ambulance"]),
        )
    else:
        det = DemoDetector(nominal_fps=float(cfg.get("video.target_fps", 15) or 15))
    det.load()
    return det


def is_ambulance(det: Detection) -> bool:
    return det.class_name.lower() in AMBULANCE_ALIASES
