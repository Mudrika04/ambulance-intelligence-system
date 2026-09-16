from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ...core.config import get_config
from ...schemas.api import ExperimentRequest, SimpleResult, StartVideoRequest
from ..deps import get_experiments, get_pipeline, get_repo

router = APIRouter(tags=["control"])


def _start(payload: StartVideoRequest | None, forced_mode: str | None = None):
    cfg = get_config()
    if payload and payload.source_type:
        cfg.set("video.source_type", payload.source_type)
    p = get_pipeline()
    result = p.start(source_override=(payload.source if payload else None),
                     mode=forced_mode or (payload.mode if payload else None))
    if not result.get("started") and result.get("reason") in ("MODEL_NOT_FOUND", "CAMERA_ERROR"):
        raise HTTPException(status_code=409, detail=result)
    return result


@router.post("/video/start", response_model=SimpleResult)
def video_start(payload: StartVideoRequest | None = None):
    return SimpleResult(ok=True, detail=_start(payload))


@router.post("/video/stop", response_model=SimpleResult)
def video_stop():
    return SimpleResult(ok=True, detail=get_pipeline().stop())


@router.post("/simulation/start", response_model=SimpleResult)
def simulation_start(payload: StartVideoRequest | None = None):
    return SimpleResult(ok=True, detail=_start(payload, forced_mode="demo"))


@router.post("/simulation/stop", response_model=SimpleResult)
def simulation_stop():
    return SimpleResult(ok=True, detail=get_pipeline().stop())


@router.post("/simulation/reset", response_model=SimpleResult)
def simulation_reset():
    return SimpleResult(ok=True, detail=get_pipeline().reset())


@router.post("/experiments/run")
def run_experiment(payload: ExperimentRequest):
    return get_experiments().run(payload.scenario, payload.arrivals, payload.seed)


@router.get("/experiments")
def list_experiments():
    rows = get_repo().experiments(25)
    if not rows:
        return {"experiments": [], "status": "AWAITING_EXPERIMENT_DATA"}
    return {"experiments": rows, "status": "OK"}


@router.get("/ablation")
def ablation():
    """Ablation results produced by scripts/run_ablation.py."""
    import json
    from ...core.config import ROOT
    path = ROOT / "data/experiments/ablation.json"
    if not path.exists():
        return {"status": "AWAITING_EXPERIMENT_DATA",
                "hint": "python scripts/run_ablation.py"}
    return json.loads(path.read_text())


@router.get("/evaluation")
def evaluation():
    """Detection evaluation produced by scripts/evaluate_detection.py."""
    import json
    from ...core.config import ROOT
    path = ROOT / "data/experiments/detection_eval.json"
    if not path.exists():
        return {"status": "AWAITING_EXPERIMENT_DATA",
                "hint": "python scripts/evaluate_detection.py"}
    return json.loads(path.read_text())


@router.get("/video/stream")
def video_stream():
    """MJPEG stream of the annotated pipeline output."""
    import time

    p = get_pipeline()

    def gen():
        boundary = b"--frame\r\n"
        idle = 0
        while p.running and idle < 200:
            jpeg = p.latest_jpeg()
            if jpeg:
                idle = 0
                yield boundary + b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            else:
                idle += 1
            time.sleep(0.06)

    if not p.running:
        raise HTTPException(status_code=409, detail="Pipeline is not running")
    return StreamingResponse(gen(),
                             media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/video/frame")
def video_frame():
    from fastapi.responses import Response
    jpeg = get_pipeline().latest_jpeg()
    if not jpeg:
        raise HTTPException(status_code=404, detail="No frame available yet")
    return Response(content=jpeg, media_type="image/jpeg")
