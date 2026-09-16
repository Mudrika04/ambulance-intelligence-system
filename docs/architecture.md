# Architecture

## Layers

| Layer | Package | Responsibility |
| --- | --- | --- |
| Input | `app.vision.video_source` | Frames + metadata from file, webcam or RTSP |
| Perception | `app.vision.detector` | Detections (real YOLOv8 or labelled demo) |
| Association | `app.tracking` | Persistent track IDs and history |
| Interpretation | `app.decision` | ROI, trajectory, validation, proximity, priority, explanation |
| Control | `app.traffic` | Deterministic FSM, signal simulator, green corridor |
| Persistence | `app.database` | Repository over SQLAlchemy |
| Delivery | `app.api`, `app.services` | REST, WebSocket, MJPEG, orchestration |

## Orchestration

`app.services.pipeline.Pipeline` owns one worker thread. Each iteration reads a frame, runs detection, tracking and the decision stack, drives the FSM, updates the corridor, renders the annotated JPEG and publishes a snapshot on the event bus. The API layer never blocks on the pipeline: it reads the last snapshot under a lock.

## Why the layers are separate

The safety argument depends on it. The AI layer can only ever *request* priority; `TrafficSignalFSM` decides. That separation is what makes `NORMAL → EMERGENCY_GREEN` structurally impossible rather than merely unlikely.

## Interfaces

`VideoSource`, `Detector`, `Tracker`, `Repository` are abstract. `FileVideoSource`, `YOLODetector`, `ByteTrackTracker`, `SQLiteRepository` are the shipped implementations. A PostgreSQL repository or a real signal controller can be added without touching decision code.

## Threading and failure

- Pipeline failures are caught per iteration, logged as `PIPELINE_ERROR`, and the loop continues.
- Camera failure aborts any pre-green phase back to NORMAL.
- Database failure degrades to `LOGGING_ERROR`; the pipeline keeps running.
- The event bus publishes from the worker thread into asyncio queues using `call_soon_threadsafe`.
