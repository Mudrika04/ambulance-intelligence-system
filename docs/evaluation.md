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

`python scripts/evaluate_detection.py` computes precision, recall, F1, AP@0.5 and an approximate AP@0.5:0.95 against a ground-truth file.

Run in demo mode the ground truth is the same script the demo detector samples, so the figures (P 0.982, R 0.958, F1 0.970, AP@0.5 0.954 over 450 frames) verify only that the evaluation code and the scenario agree. **They are not a model accuracy claim.** Meaningful accuracy requires a trained model and an independently labelled dataset; until then the dashboard shows AWAITING EXPERIMENT DATA.

## Fixed-time vs AI-adaptive

`POST /api/experiments/run` runs both controllers over the same scripted arrival set and stores the result. It is a discrete-event simulation built from the configured signal timings — not a field measurement — and every payload says so. Waiting time under fixed-time control depends on where in the cycle the ambulance arrives; under the adaptive arm it depends on validation delay plus PREPARE plus ALL_RED.

## Not yet measured

Real-world detection accuracy, robustness to weather and night conditions, behaviour on genuine traffic footage, and whether the default threshold, weights and validation frame count are appropriate for any real site.
