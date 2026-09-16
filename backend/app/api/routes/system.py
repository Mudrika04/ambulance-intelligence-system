from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from ...core.config import get_config
from ...schemas.api import ConfigUpdate, HealthResponse, SimpleResult
from ..deps import get_pipeline, get_repo

router = APIRouter(tags=["system"])
VERSION = "0.1.0"


@router.get("/health", response_model=HealthResponse)
def health():
    p = get_pipeline()
    comp = p.health()
    overall = "OK" if comp.get("database") == "CONNECTED" else "DEGRADED"
    return HealthResponse(status=overall, components=comp, mode=p.mode,
                          version=VERSION, timestamp=time.time())


@router.get("/status")
def status():
    return get_pipeline().snapshot()


@router.get("/metrics")
def metrics():
    p = get_pipeline()
    runtime = p.perf.snapshot()
    stored = get_repo().metrics(limit=100)
    return {
        "runtime": runtime,
        "measured": runtime.get("measured", False),
        "note": ("Runtime values are measured from the running pipeline. "
                 "Detection accuracy metrics require a labelled dataset and a "
                 "trained model."),
        "stored_metrics": stored,
        "accuracy": {"status": "AWAITING_EXPERIMENT_DATA"} if not stored else None,
    }


@router.post("/config", response_model=SimpleResult)
def update_config(payload: ConfigUpdate):
    cfg = get_config()
    applied = {}
    for key, value in payload.updates.items():
        if cfg.get(key) is None and "." not in key:
            raise HTTPException(status_code=400, detail=f"Unknown config key: {key}")
        cfg.set(key, value)
        applied[key] = value
    p = get_pipeline()
    # hot-apply the parameters that are safe to change while running
    if "priority.threshold" in applied:
        p.priority.threshold = float(applied["priority.threshold"])
    if "validation.required_frames" in applied:
        p.validator.required_frames = int(applied["validation.required_frames"])
    if "model.confidence_threshold" in applied:
        p.validator.min_confidence = float(applied["model.confidence_threshold"])
    get_repo().log_system_event("CONFIG_UPDATED", message=str(applied))
    return SimpleResult(ok=True, detail={"applied": applied,
                                         "note": "Prototype defaults, not validated optima."})


@router.get("/config")
def read_config():
    return get_config().as_dict()
