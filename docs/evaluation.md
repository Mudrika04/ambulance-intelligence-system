# Evaluation

## What can be measured today

Runtime metrics are measured on the running pipeline and reported as measured values, never as claims:

| Metric | Demo mode | Real mode (COCO YOLOv8n, CPU) |
| --- | --- | --- |
| Processing rate | 14.97 fps (throttled to 15) | 17.5 fps unthrottled |
| Detection latency | 0.04 ms | 52.2 ms |
| Tracking latency | 0.04 ms | < 0.1 ms |
| Decision latency | 1.25 ms | ~1 ms |
| End-to-end latency | 6.9–7.1 ms | 57.0 ms |

Hardware: 1 vCPU, 3 GB RAM, 960×540 frames. Numbers will differ on your machine; the dashboard always shows values measured locally.

## Ablation

`python scripts/run_ablation.py` — results in `docs/temporal-validation.md` and at `GET /api/ablation`.

## Detection accuracy

The ambulance detector was trained on a 558-image single-class dataset
("Ambulance" by Pouria Maleki, Roboflow Universe, CC BY 4.0) using YOLOv8n
for 60 epochs on a Colab T4 GPU (84 validation images, 103 ambulance
instances).

| Metric | Value |
| --- | --- |
| mAP@0.5 | 0.948 |
| mAP@0.5:0.95 | 0.774 |
| Precision | 0.911 |
| Recall | 0.891 |
| F1 (derived) | 0.900 |

Training and validation loss curves converged without divergence across 60
epochs, indicating the model did not overfit the training set. A
confusion-matrix breakdown at the default 0.25 confidence threshold showed 94
of 103 ambulances correctly detected, 9 missed, and 10 background regions
falsely flagged as ambulances.

That residual false-positive rate is exactly what the pipeline's temporal
validation stage (`docs/temporal-validation.md`) is designed to absorb: a
single-frame detection, however confident, can never by itself trigger a
priority request.

Run `python scripts/evaluate_detection.py --mode real` to reproduce an
evaluation against your own labelled ground truth inside this pipeline
directly, rather than via Colab's validation split.
## Fixed-time vs AI-adaptive

`POST /api/experiments/run` runs both controllers over the same scripted arrival set and stores the result. It is a discrete-event simulation built from the configured signal timings — not a field measurement — and every payload says so. Waiting time under fixed-time control depends on where in the cycle the ambulance arrives; under the adaptive arm it depends on validation delay plus PREPARE plus ALL_RED.

## Not yet measured

Real-world detection accuracy, robustness to weather and night conditions, behaviour on genuine traffic footage, and whether the default threshold, weights and validation frame count are appropriate for any real site.
