# Models

Place a trained YOLOv8 ambulance model here:

```
models/ambulance_yolov8.pt
```

The path is configurable in `configs/config.yaml` (`model.path`) or via the
`AIS_MODEL_PATH` environment variable.

Weights are not committed to the repository. If the file is missing, REAL MODEL
MODE refuses to start and returns a `MODEL NOT FOUND` message naming the exact
expected path; DEMO / SIMULATION MODE remains available.

The model must expose a class named `ambulance` (configurable through
`model.ambulance_classes`). A stock COCO YOLOv8 checkpoint has no ambulance
class and will produce no ambulance detections.
