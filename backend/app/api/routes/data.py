from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ...schemas.api import ReplayResponse
from ..deps import get_pipeline, get_repo

router = APIRouter(tags=["data"])


@router.get("/detections")
def detections(limit: int = Query(50, ge=1, le=500)):
    return {"live": get_pipeline().snapshot().get("ambulances", []),
            "stored": get_repo().recent_detections(limit)}


@router.get("/tracks")
def tracks(limit: int = Query(50, ge=1, le=500)):
    return {"live": [{k: a[k] for k in ("track_id", "approach", "direction",
                                        "confidence", "proximity", "relative_eta_s",
                                        "validated")}
                     for a in get_pipeline().snapshot().get("ambulances", [])],
            "stored": get_repo().tracks(limit)}


@router.get("/events")
def events(limit: int = Query(100, ge=1, le=1000), track_id: int | None = None,
           event_type: str | None = None):
    return {"events": get_repo().recent_events(limit, event_type, track_id)}


@router.get("/priority")
def priority(limit: int = Query(50, ge=1, le=500)):
    snap = get_pipeline().snapshot()
    return {"current_decision": snap.get("decision"),
            "ambulances": [{"track_id": a["track_id"], "priority": a["priority"],
                            "decision": a["decision"]}
                           for a in snap.get("ambulances", [])],
            "history": get_repo().priority_events(limit)}


@router.get("/signal")
def signal():
    snap = get_pipeline().snapshot()
    return {"current": snap.get("signal"), "history": get_repo().signal_events(50)}


@router.get("/intersections")
def intersections():
    return get_pipeline().snapshot().get("green_corridor", {})


@router.get("/replay/tracks")
def replay_tracks():
    return {"track_ids": get_repo().validated_track_ids(25)}


@router.get("/replay/{track_id}", response_model=ReplayResponse)
def replay(track_id: int):
    data = get_repo().replay(track_id)
    if not data["timeline"] and data["track"] is None:
        raise HTTPException(status_code=404, detail=f"No recorded event for track {track_id}")
    return data


@router.get("/trajectory/{track_id}")
def trajectory(track_id: int):
    points = get_repo().trajectory(track_id)
    if not points:
        raise HTTPException(status_code=404, detail="No trajectory recorded")
    return {"track_id": track_id, "points": points}
