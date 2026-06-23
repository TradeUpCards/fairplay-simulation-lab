# FairPlay live-scoring API

A thin **FastAPI** layer over the scoring engine (`scoring/*.py`). It holds the
room in memory, lets an operator move players between tables, recomputes the
affected table's health via the **unchanged** Python engine, and streams the new
scores to the frontend over **SSE**. The engine is not ported or reimplemented —
this only wraps it.

A fresh process reproduces the frozen `data/derived/health_scores.json`
byte-for-byte (verified), so the live API and the static demo agree on hour 0.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/api/pit` | Full operator snapshot — every table's roster + health, ranked healthiest-first |
| `POST` | `/api/players/{id}/stand` | Stand a player up from their table → rescore → broadcast |
| `POST` | `/api/players/{id}/sit` | Seat a player (`{"table_id": "T-8"}`) → rescore → broadcast |
| `GET`  | `/api/stream` | SSE; emits a `score_update` event per mutation |
| `GET`  | `/api/healthz` | Liveness probe |

`score_update` event payload: `{ "table_id", "table": <roster entry>, "health": <HealthScore> }`.

## Run locally (from the repo root)

```bash
uv venv --python 3.12 .venv          # Python 3.14 lacks wheels for the stack; 3.12 is safe
VIRTUAL_ENV=.venv uv pip install -r api/requirements.txt
PORT=8000 .venv/bin/python -m api.app          # or: .venv/bin/uvicorn api.app:app --reload
```

The frontend points at `http://localhost:8000` by default; override with
`VITE_API_BASE` in the frontend env. If the API is down the frontend falls back
to the frozen JSON, so the demo still runs.

## Config (env)

| Var | Default | Notes |
|---|---|---|
| `PORT` | `8000` | Bound on `0.0.0.0` |
| `CORS_ORIGINS` | `http://localhost:5173,:5174,:5175` | Comma-separated; set to the deployed frontend origin |
| `RELOAD` | unset | Any value → uvicorn auto-reload (dev only) |

## Dockerize / deploy (Railway) — notes for the next pass

- **One worker only.** State (the room) and the SSE hub are in-process; multiple
  workers would each hold a divergent room and split the SSE subscribers. Run a
  single uvicorn worker, or move the room + hub to Redis before scaling out.
- Working dir must be the **repo root** so `scoring/` imports and `data/*.json`
  resolve (`api/room.py` derives paths from `parents[1]`).
- Suggested start command: `uvicorn api.app:app --host 0.0.0.0 --port $PORT`.
- Set `CORS_ORIGINS` to the deployed frontend URL.
- SSE needs the proxy to **not buffer** `text/event-stream` and to allow long-lived
  connections (Railway is fine by default; mentioned for any nginx in front).
- State resets on restart — intentional for the demo; persistence is a later call.
