.PHONY: install demo backend frontend test lint sample ablation eval

install:
	pip install -r backend/requirements.txt
	cd frontend && npm install

sample:
	python scripts/generate_sample_video.py

backend:
	uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && python -m pytest -q
	cd frontend && npm test

ablation:
	python scripts/run_ablation.py

eval:
	python scripts/evaluate_detection.py
