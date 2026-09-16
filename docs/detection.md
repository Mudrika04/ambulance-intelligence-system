# Detection

## Interface

```python
class Detector(ABC):
    def load(self) -> None: ...
    def detect(self, frame, meta) -> list[Detection]: ...
```

`Detection` carries `class_name`, `confidence`, `bbox`, `timestamp`, `frame_id`, `source` and `simulated`.

## YOLODetector

Real Ultralytics inference. Ultralytics is imported lazily so the rest of the system runs without torch installed. Configuration: `model.path`, `model.confidence_threshold`, `model.iou_threshold`, `model.device`, `model.ambulance_classes`.

If the weights are absent, `load()` raises `ModelNotFoundError` with a message that names the expected path. If they load but expose no ambulance class, a `MODEL_CLASS_WARNING` is logged — a stock COCO checkpoint will produce no ambulance detections.

Measured on this development machine (CPU, 960×540): model load 1.1 s, first inference 13.8 s including warm-up, subsequent inferences 52–80 ms per frame.

## DemoDetector

Samples the scripted scenario in `app.vision.scenario` with confidence jitter, a simulated occlusion dropout and a single-frame false positive every 137 frames. Everything it returns is `simulated=True` and `source="demo-simulation"`. The periodic false positive exists to demonstrate that temporal validation refuses to escalate a one-frame detection.

## Scope

Vision only. There is no microphone, siren detection, audio classification or audio-visual fusion anywhere in the system, by design.
