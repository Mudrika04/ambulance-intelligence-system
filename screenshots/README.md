# Screenshots

This directory is intentionally empty in the repository. No screenshot here has
been generated, mocked or fabricated.

Capture them from your own running instance:

1. `uvicorn app.main:app --app-dir backend --port 8000`
2. `cd frontend && npm run dev`, open http://localhost:5173
3. Press "Start demo pipeline" and wait for the inbound ambulance (about 3 s into
   each 30 s scenario loop)
4. Capture, using these filenames:

| File | What to capture |
| --- | --- |
| `01_dashboard.png` | Operations tab with the pipeline running |
| `02_live_detection.png` | Live view with bounding box, track ID and ROI overlay |
| `03_tracking.png` | Ambulance intelligence panel showing track ID, approach, direction |
| `04_priority_decision.png` | "Why this decision" panel with reason codes |
| `05_signal_control.png` | Phase ribbon in EMERGENCY_GREEN with signal heads |
| `06_green_corridor.png` | Corridor panel during handover |
| `07_event_replay.png` | Analysis tab, event replay timeline |
| `08_analytics.png` | Fixed-time vs AI-adaptive comparison and ablation table |
