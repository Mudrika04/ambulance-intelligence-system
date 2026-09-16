# Ambulance Intelligence System

An explainable computer-vision platform for real-time ambulance detection, tracking, predictive priority scoring and safety-aware traffic signal control.

**Project 27_CSAI_4B_04** · Department of Artificial Intelligence · Pranveer Singh Institute of Technology, Kanpur · 2026–27

---

## 1. Overview

The system watches a road camera, decides whether an ambulance is genuinely approaching an intersection, explains that decision in plain terms, and asks a deterministic safety layer to grant a green signal. Every stage between the camera and the signal head is separated, logged and testable:

```
camera/video → detection → tracking → ROI & approach → temporal validation →
trajectory → proximity & relative ETA → priority score → explainable decision →
signal FSM → green corridor → event log → analytics
```

The project is deliberately **not** "YOLO detects ambulance". A single-frame detection can never move the signal. Priority is granted only after a track has persisted, stayed inside a configured approach, and kept moving toward the intersection.

## 2. Problem statement

Fixed-time signals do not know an ambulance is coming. An ambulance meeting a red phase waits for the cycle, and drivers cannot always clear a path. Purely detection-driven priority is worse than useless if a single noisy frame can flip a junction to green, because a false activation stops cross traffic for no reason and erodes trust in the system.

## 3. Motivation

Kanpur's arterial junctions run fixed-time plans. A camera already exists at many of them. The question the project asks is not "can a model see an ambulance" but "what evidence should be required before a machine is allowed to change a signal, and how do we show an operator why it did".

## 4. Key features

| Feature | Status |
| --- | --- |
| MP4 / webcam / RTSP video abstraction | IMPLEMENTED · TESTED (MP4 tested; webcam and RTSP implemented, untested without hardware) |
| Real YOLOv8 detector (Ultralytics) | IMPLEMENTED · TESTED (loaded and run on CPU; needs your trained weights for ambulances) |
| Demo detector with labelled simulated detections | IMPLEMENTED · TESTED |
| ByteTrack-style tracker with persistent IDs | IMPLEMENTED · TESTED |
| Configurable ROIs, approaches and proximity zones | IMPLEMENTED · TESTED |
| Temporal validation (configurable frame count) | IMPLEMENTED · TESTED |
| Trajectory analysis, camera-based proximity and relative ETA | IMPLEMENTED · TESTED |
| Weighted, explainable priority engine | IMPLEMENTED · TESTED |
| Decision engine with reason codes | IMPLEMENTED · TESTED |
| Deterministic signal FSM with rejected transitions | IMPLEMENTED · TESTED |
| Signal simulator | IMPLEMENTED · SIMULATION |
| Three-intersection green corridor | IMPLEMENTED · SIMULATION |
| SQLite event logging, replay and analytics | IMPLEMENTED · TESTED |
| REST API, OpenAPI docs, WebSocket, MJPEG stream | IMPLEMENTED · TESTED |
| Control-console dashboard (React + TypeScript) | IMPLEMENTED · TESTED (component tests; no browser screenshots captured yet) |
| Fixed-time vs AI-adaptive experiment runner | IMPLEMENTED · SIMULATION |
| Ablation study (A/B/C/D) | IMPLEMENTED · TESTED |
| Detection evaluation (P/R/F1/AP) | IMPLEMENTED · awaiting a trained model and a labelled dataset for meaningful numbers |

## 5. Architecture

```
ambulance-intelligence-system/
├── backend/app/
│   ├── api/          FastAPI routes, dependency singletons, WebSocket
│   ├── core/         config, structured logging, domain types
│   ├── database/     engine bootstrap + repository
│   ├── models/       SQLAlchemy entities
│   ├── schemas/      Pydantic request/response models
│   ├── services/     pipeline orchestrator, event bus, metrics, experiments
│   ├── vision/       video sources, detectors, overlay, demo scenario
│   ├── tracking/     ByteTrack tracker
│   ├── decision/     ROI, trajectory, validation, proximity, priority, engine
│   └── traffic/      FSM, signal simulator, green corridor
├── frontend/src/     React + TypeScript console
├── configs/          config.yaml
├── scripts/          sample video, ablation, detection evaluation
├── docs/             design documentation
└── data/             SQLite database, sample clip, experiment output
```

Every replaceable part sits behind an interface: `VideoSource`, `Detector`, `Tracker`, `Repository`, `TrafficSignalFSM`. Swapping SQLite for PostgreSQL, or the simulator for a real controller, does not touch the decision code.

## 6. Workflow

1. A frame arrives with frame number, timestamp, measured FPS and source status.
2. The detector returns detections; ambulance-class detections go to the tracker.
3. The tracker assigns a persistent track ID and keeps centroid, confidence and bbox history.
4. The ROI manager resolves approach (NORTH/SOUTH/EAST/WEST) and zone (FAR → CLEARANCE).
5. The trajectory analyser classifies motion as APPROACHING, STATIONARY, MOVING_AWAY or UNCERTAIN.
6. The temporal validator counts consecutive frames satisfying every criterion.
7. Proximity and relative ETA are estimated in image space and labelled as camera-based.
8. The priority engine produces a weighted score with per-component contributions.
9. The decision engine emits a decision plus reason codes.
10. Only a validated track above threshold may request priority; the FSM decides whether to grant it.
11. The green corridor updates downstream intersections; everything is logged and streamed to the console.

## 7. Technology stack

Python 3.12, FastAPI, Uvicorn, Pydantic, SQLAlchemy, SQLite, OpenCV, NumPy, Ultralytics YOLOv8 (optional), pytest · React 18, TypeScript, Vite, Tailwind CSS, Recharts, Vitest, Testing Library · Docker Compose.

## 8. Installation

```bash
git clone <repo-url> ambulance-intelligence-system
cd ambulance-intelligence-system

# backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

# optional: REAL MODEL MODE (large download, pulls torch)
pip install -r backend/requirements-real-model.txt

# frontend
cd frontend && npm install && cd ..

# environment
cp .env.example .env
```

## 9. Configuration

All tunable parameters live in `configs/config.yaml`; `.env` overrides `AIS_MODE`, `AIS_MODEL_PATH`, `AIS_VIDEO_SOURCE`, `AIS_DATABASE_URL`. Parameters can also be changed at runtime with `POST /api/config`.

**The defaults are prototype values chosen for demonstration. None of them — five validation frames, a 0.70 priority threshold, the six priority weights — has been experimentally established as optimal. Validating them is future work.**

## 10. Dataset setup

No traffic dataset ships with this repository. Generate the synthetic demo clip:

```bash
python scripts/generate_sample_video.py
```

This writes `data/sample/demo_intersection.mp4` (schematic, clearly watermarked "SYNTHETIC DEMO CLIP — NOT REAL FOOTAGE") and a matching ground-truth JSON. To use your own footage, point `video.source` at it. For training, collect and label ambulance images yourself, or use a dataset whose licence permits your use.

## 11. Model setup

Put trained weights at `models/ambulance_yolov8.pt` (see `models/README.md`). A stock COCO checkpoint has no ambulance class and will detect nothing. If the file is missing, the backend returns a `MODEL NOT FOUND` message naming the expected path instead of silently substituting fake detections.

## 12. Demo mode

```bash
uvicorn app.main:app --app-dir backend --port 8000     # terminal 1
cd frontend && npm run dev                              # terminal 2
# open http://localhost:5173 and press "Start demo pipeline"
```

Demo mode generates scripted detections so the whole pipeline can be shown without a trained model, a GPU or a camera. Every simulated value is flagged `simulated: true` in the API and labelled DEMO / SIMULATION on screen and on the video overlay.

## 13. Real model mode

```bash
AIS_MODE=real uvicorn app.main:app --app-dir backend --port 8000
# or press "Start with trained model" in the console
```

Real mode performs genuine Ultralytics inference. There are no hard-coded coordinates and no fabricated confidences anywhere in that path.

## 14. API documentation

Interactive docs: `http://localhost:8000/docs`. See `docs/api.md` for the full list.

## 15. Database

SQLite by default (`data/ais.db`), created automatically at startup. Tables: `detections`, `tracks`, `trajectory_points`, `priority_events`, `signal_events`, `system_events`, `intersections`, `experiments`, `metrics`. Schema details in `docs/api.md` and `backend/app/models/entities.py`.

## 16. Testing

```bash
cd backend && python -m pytest -q      # 74 tests
cd frontend && npm test                # 7 component tests
```

The ten mandatory scenarios in `backend/tests/test_mandatory_scenarios.py` drive the real `Pipeline` object, not a stand-in.

## 17. Evaluation

```bash
python scripts/run_ablation.py          # stage-by-stage contribution
python scripts/evaluate_detection.py    # precision / recall / F1 / AP
curl -X POST localhost:8000/api/experiments/run -d '{"arrivals":20}' -H 'Content-Type: application/json'
```

Detection accuracy figures are only meaningful with a trained model and an independently labelled dataset. Until those exist, the console shows **AWAITING EXPERIMENT DATA** rather than a number.

## 18. Screenshots

`screenshots/` is empty on purpose. Capture images from your own running instance following `screenshots/README.md`. No screenshot in this repository has been fabricated.

## 19. Limitations

- Proximity and relative ETA are image-space estimates. Without camera calibration they are not metres and not equivalent to GPS positioning.
- The signal controller, green corridor and experiment comparison are simulations with no connection to real infrastructure.
- No trained ambulance model is included, so end-to-end accuracy is unmeasured.
- The demo clip is synthetic; robustness under real rain, night, glare and dense traffic is untested.
- BoT-SORT is not implemented; requesting it falls back to ByteTrack with a warning.
- The tracker uses greedy IoU association rather than a Kalman filter with Hungarian matching.

## 20. Future scope

Train and evaluate a real ambulance detector; calibrate the camera for metric distance; replace greedy association with a Kalman/Hungarian tracker; validate the threshold and weights experimentally; connect to a real controller over a standards-based interface; extend the corridor beyond three simulated intersections.

## 21. Team contribution

Fill in before submission:

| Member | Roll number | Contribution |
| --- | --- | --- |
|  |  | Detection and tracking |
|  |  | Decision and priority engine |
|  |  | Traffic control and corridor |
|  |  | Dashboard and API |

## Privacy

The system processes only what emergency-vehicle detection requires. There is no face recognition, no person identification and no licence-plate recognition anywhere in the codebase.
