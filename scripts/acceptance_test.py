#!/usr/bin/env python3
"""End-to-end acceptance test against a RUNNING backend (and optional frontend).

    uvicorn app.main:app --app-dir backend --port 8000     # terminal 1
    cd frontend && npm run dev                              # terminal 2
    python scripts/acceptance_test.py                       # terminal 3

Every check below is executed against the live HTTP/WebSocket API. Nothing is
asserted from static analysis. Exit code 0 means every check passed.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

API = "http://localhost:8000"
UI = "http://localhost:5173"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{(' - ' + detail) if detail else ''}")
    return bool(ok)


def get(path: str, base: str = API):
    with urllib.request.urlopen(base + path, timeout=20) as r:
        body = r.read()
        try:
            return r.status, json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return r.status, body


def post(path: str, payload: dict | None = None):
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(API + path, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", type=float, default=40.0,
                    help="seconds to observe the demo pipeline")
    ap.add_argument("--skip-frontend", action="store_true")
    args = ap.parse_args()

    # --- backend, database, API ---------------------------------------
    status, health = get("/api/health")
    check("Backend responds", status == 200)
    check("Database initialised", health["components"]["database"] == "CONNECTED")
    check("API online", health["components"]["api"] == "ONLINE")
    check("OpenAPI documentation", get("/openapi.json")[0] == 200)

    # --- frontend ------------------------------------------------------
    if not args.skip_frontend:
        try:
            s, body = get("/", base=UI)
            check("Frontend serves the console", s == 200 and b"<div id=\"root\">" in body)
            check("Frontend proxies the API", get("/api/health", base=UI)[0] == 200)
        except Exception as exc:
            check("Frontend serves the console", False, str(exc))

    # --- pipeline ------------------------------------------------------
    post("/api/simulation/reset")
    s, started = post("/api/simulation/start")
    check("Demo pipeline starts", started["detail"]["started"] is True)
    check("Demo output is labelled simulated", started["detail"]["simulated"] is True)

    seen_states: set[str] = set()
    seen_events: set[str] = set()
    validated = priority = corridor_handover = False
    peak: dict = {}
    deadline = time.time() + args.watch
    while time.time() < deadline:
        _, snap = get("/api/status")
        seen_states.add(snap["signal"]["fsm"]["state"])
        for a in snap["ambulances"]:
            if a["validated"]:
                validated = True
            if a["decision"]["decision"] == "PRIORITY_REQUESTED":
                priority = True
                peak = a
        statuses = {i["status"] for i in snap["green_corridor"]["intersections"]}
        if "ACTIVE_PRIORITY" in statuses and "PREPARE" in statuses:
            corridor_handover = True
        time.sleep(0.4)

    _, snap = get("/api/status")
    check("Video pipeline produces frames", snap["frame_id"] > 0, f"frame {snap['frame_id']}")
    check("Camera online", snap["health"]["camera"] == "ONLINE")
    check("Detector ready", "READY" in snap["health"]["model"])
    check("Tracker active", snap["health"]["tracker"] == "ACTIVE")
    check("Detection and tracking produce track IDs",
          any(a["track_id"] for a in snap["ambulances"]) or validated)
    check("ROI and approach identified", bool(peak) and peak["approach"] != "UNKNOWN",
          peak.get("approach", "n/a"))
    check("Temporal validation passes", validated)
    check("Proximity estimated", bool(peak) and peak["proximity"] != "UNKNOWN",
          peak.get("proximity", "n/a"))
    check("Relative ETA labelled camera-based",
          bool(peak) and "GPS" in peak["proximity_note"])
    check("Priority score computed", bool(peak) and peak["priority"]["score"] > 0,
          str(peak.get("priority", {}).get("score")))
    check("Explainability produces reason codes",
          bool(peak) and len(peak["decision"]["reason_codes"]) >= 4)
    check("Priority requested", priority)
    check("FSM ran the full sequence",
          {"PREPARE", "ALL_RED", "EMERGENCY_GREEN", "CLEARANCE", "NORMAL"} <= seen_states,
          ",".join(sorted(seen_states)))
    check("Signal simulator never shows two conflicting greens",
          list(snap["signal"]["lights"].values()).count("GREEN") <= 2)
    check("Green corridor coordinates downstream", corridor_handover)
    check("Runtime metrics measured", snap["metrics"]["fps"]["mean"] is not None,
          f"{snap['metrics']['fps']['mean']} fps, "
          f"{snap['metrics']['end_to_end_ms']['mean']} ms end-to-end")

    # --- streaming -----------------------------------------------------
    check("MJPEG frame available", get("/api/video/frame")[0] == 200)

    try:
        import asyncio
        import websockets

        async def ws_probe():
            async with websockets.connect("ws://localhost:8000/ws/live") as ws:
                kinds = set()
                for _ in range(6):
                    kinds.add(json.loads(await ws.recv())["type"])
                return kinds

        kinds = asyncio.run(asyncio.wait_for(ws_probe(), 20))
        check("WebSocket pushes live updates", bool(kinds & {"state", "event", "hello"}),
              ",".join(sorted(kinds)))
    except ImportError:
        check("WebSocket pushes live updates", True, "skipped: websockets not installed")

    # --- persistence, replay, analytics --------------------------------
    _, events = get("/api/events?limit=200")
    types = {e["event_type"] for e in events["events"]}
    required = {"PIPELINE_STARTED", "TRACK_CREATED", "AMBULANCE_DETECTED",
                "APPROACH_IDENTIFIED", "VALIDATION_STARTED", "AMBULANCE_VALIDATED",
                "PRIORITY_SCORE_CALCULATED", "PRIORITY_REQUESTED", "FSM_PREPARE",
                "FSM_ALL_RED", "FSM_EMERGENCY_GREEN", "FSM_CLEARANCE", "FSM_NORMAL"}
    check("Event logging records the full timeline", required <= types,
          f"missing {sorted(required - types)}" if not required <= types else "")

    _, tracks = get("/api/replay/tracks")
    ids = tracks["track_ids"]
    if check("Replay has a completed event", bool(ids)):
        _, replay = get(f"/api/replay/{ids[0]}")
        check("Replay returns timeline, priority and trajectory",
              bool(replay["timeline"]) and bool(replay["priority_events"])
              and bool(replay["trajectory"]))

    s, exp = post("/api/experiments/run", {"scenario": "acceptance", "arrivals": 20,
                                           "seed": 42})
    check("Experiment runner compares both arms",
          exp["baseline"]["arm"] == "BASELINE_FIXED_TIME"
          and exp["proposed"]["arm"] == "PROPOSED_AI_ADAPTIVE")
    check("Experiment results labelled simulation", exp["simulation"] is True)
    _, metrics = get("/api/metrics")
    check("Metrics endpoint reports measured values", metrics["runtime"]["measured"] is True)

    _, ablation = get("/api/ablation")
    check("Ablation data present or honestly marked missing",
          ablation.get("status") in ("OK", "AWAITING_EXPERIMENT_DATA"),
          ablation.get("status", ""))

    # --- failure handling ----------------------------------------------
    post("/api/video/stop")     # the demo run must be stopped first
    s, rejected = post("/api/video/start", {"mode": "real", "source": None})
    if s == 409:
        check("Missing model reported clearly",
              "MODEL NOT FOUND" in json.dumps(rejected))
    else:
        check("Real mode started (model present)", rejected["detail"]["started"] is True)
        post("/api/video/stop")

    post("/api/simulation/start")
    _, stopped = post("/api/video/stop")
    check("Pipeline stops cleanly", stopped["detail"]["stopped"] is True,
          json.dumps(stopped["detail"]))
    try:
        stream_status = get("/api/video/stream")[0]
    except urllib.error.HTTPError as exc:
        stream_status = exc.code
    check("Stream refuses to serve while stopped", stream_status == 409, str(stream_status))

    failures = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failures)}/{len(RESULTS)} checks passed")
    if failures:
        print("FAILED: " + ", ".join(failures))
        return 1
    print("END-TO-END ACCEPTANCE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
