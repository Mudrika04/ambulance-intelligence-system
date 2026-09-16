# Contributing

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install
```

## Before opening a pull request

```bash
cd backend && python -m pytest -q
cd frontend && npm test && npm run build
```

## Ground rules

1. **Never fabricate results.** No metric, screenshot or capability appears in the
   repository unless it came from an actual run. If something is not measured,
   the UI says AWAITING EXPERIMENT DATA.
2. **Label every simulated value.** Anything produced by the demo detector, the
   signal simulator, the green corridor or the experiment runner must carry
   `simulated: true` and be labelled in the interface.
3. **The AI layer only requests priority.** Decision code must never mutate
   signal state directly; it goes through `TrafficSignalFSM`.
4. **A new pipeline stage needs a test.** Add it to `backend/tests/`, and if it
   affects the mandatory scenarios, update `test_mandatory_scenarios.py`.
5. **No audio.** This project is computer-vision only by design.
6. **No biometric processing.** No face recognition, person identification or
   licence-plate recognition.
7. **Keep parameters configurable.** New thresholds go in `configs/config.yaml`
   with a comment noting they are prototype values.

## Style

Python: 4 spaces, type hints on public functions, module docstrings explaining
why rather than what. TypeScript: Prettier defaults in `.prettierrc`.
