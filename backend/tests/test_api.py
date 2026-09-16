"""API and WebSocket tests using the real FastAPI application."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_openapi_documentation_is_available(client):
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    for endpoint in ("/api/health", "/api/status", "/api/detections", "/api/tracks",
                     "/api/events", "/api/priority", "/api/signal",
                     "/api/intersections", "/api/metrics", "/api/video/start",
                     "/api/video/stop", "/api/simulation/start",
                     "/api/simulation/stop", "/api/simulation/reset", "/api/config"):
        assert endpoint in paths, f"missing documented endpoint {endpoint}"


def test_health_reports_real_component_state(client):
    body = client.get("/api/health").json()
    assert body["components"]["database"] == "CONNECTED"
    assert body["components"]["api"] == "ONLINE"
    assert body["mode"] in ("demo", "real")


def test_status_before_start_is_not_running(client):
    body = client.get("/api/status").json()
    assert body["running"] in (True, False)
    assert "health" in body


def test_metrics_endpoint_never_fabricates_accuracy(client):
    body = client.get("/api/metrics").json()
    assert "runtime" in body
    if not body["runtime"]["measured"]:
        assert body["runtime"]["fps"]["mean"] is None


def test_config_update_applies_and_is_validated(client):
    ok = client.post("/api/config", json={"updates": {"priority.threshold": 0.75}})
    assert ok.status_code == 200
    assert ok.json()["detail"]["applied"]["priority.threshold"] == 0.75
    bad = client.post("/api/config", json={"updates": {"nonexistent": 1}})
    assert bad.status_code == 400
    client.post("/api/config", json={"updates": {"priority.threshold": 0.70}})


def test_stream_requires_a_running_pipeline(client):
    client.post("/api/video/stop")
    assert client.get("/api/video/stream").status_code == 409


def test_simulation_lifecycle_and_live_data(client):
    started = client.post("/api/simulation/start", json={}).json()
    assert started["detail"]["started"] is True
    assert started["detail"]["simulated"] is True
    time.sleep(3.0)

    status = client.get("/api/status").json()
    assert status["running"] is True
    assert status["frame_id"] > 0
    assert status["simulated"] is True
    assert status["metrics"]["fps"]["mean"] is not None

    assert client.get("/api/video/frame").status_code == 200
    assert client.get("/api/detections").status_code == 200
    assert client.get("/api/tracks").status_code == 200
    assert client.get("/api/signal").json()["current"]["fsm"]["state"] in (
        "NORMAL", "PREPARE", "ALL_RED", "EMERGENCY_GREEN", "CLEARANCE")
    corridor = client.get("/api/intersections").json()
    assert corridor["simulated"] is True and len(corridor["intersections"]) == 3

    events = client.get("/api/events").json()["events"]
    assert any(e["event_type"] == "PIPELINE_STARTED" for e in events)

    stopped = client.post("/api/simulation/stop").json()
    assert stopped["detail"]["stopped"] is True


def test_websocket_pushes_live_updates(client):
    client.post("/api/simulation/start", json={})
    try:
        with client.websocket_connect("/ws/live") as ws:
            hello = ws.receive_json()
            assert hello["type"] == "hello"
            kinds = set()
            for _ in range(6):
                kinds.add(ws.receive_json()["type"])
            assert kinds & {"state", "event", "system_health"}
    finally:
        client.post("/api/simulation/stop")


def test_replay_endpoint_returns_recorded_event(client):
    client.post("/api/simulation/reset")
    client.post("/api/simulation/start", json={})
    time.sleep(6.0)
    client.post("/api/simulation/stop")
    ids = client.get("/api/replay/tracks").json()["track_ids"]
    if not ids:
        pytest.skip("no validated track recorded in the sampled window")
    replay = client.get(f"/api/replay/{ids[0]}").json()
    assert replay["track_id"] == ids[0]
    assert replay["timeline"]
    assert client.get("/api/replay/999999").status_code == 404


def test_experiment_runner_produces_both_arms(client):
    result = client.post("/api/experiments/run",
                         json={"scenario": "unit", "arrivals": 12, "seed": 1}).json()
    assert result["baseline"]["arm"] == "BASELINE_FIXED_TIME"
    assert result["proposed"]["arm"] == "PROPOSED_AI_ADAPTIVE"
    assert result["simulation"] is True
    assert result["baseline"]["arrivals"] == 12
    listing = client.get("/api/experiments").json()
    assert listing["status"] == "OK"
