# Deployment

## Local

```bash
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
cd frontend && npm install && npm run dev
```

The Vite dev server proxies `/api` and `/ws` to port 8000, so no CORS configuration is needed in development. For a production build, `npm run build` emits `frontend/dist`; serve it behind any static server and set `VITE_API_BASE` to the backend origin.

## Docker

```bash
docker compose up --build
# backend  http://localhost:8000
# frontend http://localhost:5173
```

`data/`, `models/` and `configs/` are mounted so the database, weights and configuration survive rebuilds.

## Configuration in production

Never commit `.env`. Camera credentials belong in `AIS_RTSP_URL`. `.gitignore` already excludes `.env`, `*.pt` weights, the SQLite database and generated experiment output.

## Migrating off SQLite

Set `AIS_DATABASE_URL` to a PostgreSQL or MySQL URL. `init_db` creates the schema on any SQLAlchemy-supported backend; only the SQLite-specific `check_same_thread` and WAL pragma are conditional.

## Operational notes

- The pipeline runs in one worker thread; one backend process serves one camera.
- The MJPEG endpoint returns 409 when the pipeline is stopped.
- Structured JSON logs go to stdout and are container-friendly.
