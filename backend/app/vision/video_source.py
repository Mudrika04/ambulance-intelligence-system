"""VideoSource abstraction: the pipeline never depends on the source type."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import cv2
import numpy as np

from ..core.logging_conf import get_logger
from ..core.types import FrameMeta, SourceKind

log = get_logger(__name__)


class VideoSourceError(RuntimeError):
    pass


class VideoSource(ABC):
    kind: SourceKind = SourceKind.FILE

    def __init__(self) -> None:
        self._frame_id = 0
        self._opened = False
        self._status = "OFFLINE"
        self._t0 = 0.0
        self._fps_measured = 0.0
        self._last_ts = 0.0

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def read(self) -> Tuple[Optional[np.ndarray], Optional[FrameMeta]]: ...

    def release(self) -> None:
        self._opened = False
        self._status = "OFFLINE"

    @property
    def status(self) -> str:
        return self._status

    @property
    def opened(self) -> bool:
        return self._opened

    def _measure(self) -> None:
        now = time.perf_counter()
        if self._last_ts:
            dt = now - self._last_ts
            if dt > 0:
                inst = 1.0 / dt
                self._fps_measured = inst if not self._fps_measured else (
                    0.9 * self._fps_measured + 0.1 * inst)
        self._last_ts = now


class _CaptureSource(VideoSource):
    """Shared cv2.VideoCapture behaviour."""

    def __init__(self, target, loop: bool = False):
        super().__init__()
        self._target = target
        self._loop = loop
        self._cap: Optional[cv2.VideoCapture] = None
        self.width = 0
        self.height = 0
        self.declared_fps = 0.0

    def open(self) -> None:
        self._cap = cv2.VideoCapture(self._target)
        if not self._cap or not self._cap.isOpened():
            self._status = "CAMERA_ERROR"
            raise VideoSourceError(f"Unable to open video source: {self._target!r}")
        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.declared_fps = float(self._cap.get(cv2.CAP_PROP_FPS)) or 0.0
        self._opened = True
        self._status = "ONLINE"
        log.info("video source opened", extra={"event": "VIDEO_OPENED"})

    def read(self):
        if not self._cap or not self._opened:
            self._status = "CAMERA_ERROR"
            return None, None
        ok, frame = self._cap.read()
        if not ok:
            if self._loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self._cap.read()
            if not ok:
                self._status = "EOF" if self.kind == SourceKind.FILE else "CAMERA_ERROR"
                return None, None
        self._frame_id += 1
        self._measure()
        meta = FrameMeta(
            frame_id=self._frame_id,
            timestamp=time.time(),
            width=frame.shape[1],
            height=frame.shape[0],
            fps=round(self._fps_measured, 2),
            source_status=self._status,
        )
        return frame, meta

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
        super().release()


class FileVideoSource(_CaptureSource):
    kind = SourceKind.FILE

    def __init__(self, path: str, loop: bool = True):
        super().__init__(str(path), loop=loop)

    @property
    def position_seconds(self) -> float:
        if self._cap and self.declared_fps:
            return self._cap.get(cv2.CAP_PROP_POS_FRAMES) / self.declared_fps
        return 0.0


class WebcamSource(_CaptureSource):
    kind = SourceKind.WEBCAM

    def __init__(self, index: int = 0):
        super().__init__(int(index), loop=False)


class RTSPSource(_CaptureSource):
    kind = SourceKind.RTSP

    def __init__(self, url: str):
        super().__init__(str(url), loop=False)


class SyntheticSource(VideoSource):
    """In-memory frame generator used when no video file exists (tests/CI)."""

    kind = SourceKind.FILE

    def __init__(self, width: int = 960, height: int = 540, fps: float = 15.0):
        super().__init__()
        self.width, self.height, self.fps = width, height, fps

    def open(self) -> None:
        self._opened = True
        self._status = "ONLINE"
        self._t0 = time.time()

    def read(self):
        if not self._opened:
            return None, None
        frame = np.full((self.height, self.width, 3), 40, dtype=np.uint8)
        self._frame_id += 1
        self._measure()
        return frame, FrameMeta(self._frame_id, time.time(), self.width,
                                self.height, round(self._fps_measured, 2), "ONLINE")


def build_video_source(cfg) -> VideoSource:
    kind = str(cfg.get("video.source_type", "file")).lower()
    loop = bool(cfg.get("video.loop", True))
    if kind == "webcam":
        return WebcamSource(int(cfg.get("video.source", 0)))
    if kind == "rtsp":
        return RTSPSource(str(cfg.get("video.source")))
    path = cfg.resolve("video.source")
    if not path.exists():
        log.warning("video file missing, falling back to synthetic frames",
                    extra={"event": "VIDEO_FALLBACK"})
        return SyntheticSource()
    return FileVideoSource(str(path), loop=loop)
