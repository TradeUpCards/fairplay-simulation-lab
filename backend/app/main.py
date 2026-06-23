"""FairPlay live-scoring API — FastAPI app.

Wraps the scoring engine so the operator can move a player between tables and
watch the affected table scores recompute live, pushed to the frontend over SSE.

Endpoints
---------
  GET  /api/pit                      full operator snapshot (rosters + health, ranked)
  POST /api/players/{id}/stand       stand a player up   → rescore their table → broadcast
  POST /api/players/{id}/sit         sit a player down    → rescore that table  → broadcast
  GET  /api/stream                   SSE: a `score_update` per mutation
  GET  /api/healthz                  liveness probe (for Railway/Docker)

Run locally:  uvicorn backend.app.main:app --reload --port 8000   (from the repo root)
"""
from __future__ import annotations

import json
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .hub import Hub
from .room import Room, RoomError

app = FastAPI(title="FairPlay live-scoring API", version="0.1.0")

# CORS — the Vite dev server origins by default; override via env for deploy.
_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:5174,http://localhost:5175",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

room = Room()
hub = Hub()


class SitBody(BaseModel):
    table_id: str


def _broadcast_table(table_id: str) -> dict:
    """Publish (and return) one table's recomputed roster + health."""
    payload = room.table_update(table_id)
    hub.publish({"event": "score_update", "data": payload})
    return payload


@app.get("/api/pit")
def get_pit() -> dict:
    """Full operator snapshot — the drop-in for the static health + roster files."""
    return room.pit_snapshot()


@app.post("/api/players/{player_id}/stand")
def stand(player_id: str) -> dict:
    try:
        h = room.stand(player_id)
    except RoomError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _broadcast_table(h.table_id)


@app.post("/api/players/{player_id}/sit")
def sit(player_id: str, body: SitBody) -> dict:
    try:
        h = room.sit(player_id, body.table_id)
    except RoomError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _broadcast_table(h.table_id)


@app.get("/api/stream")
async def stream(request: Request) -> EventSourceResponse:
    """SSE channel — emits a `score_update` event on every seating mutation."""

    async def event_generator():
        q = hub.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                event = await q.get()
                yield {"event": event["event"], "data": json.dumps(event["data"])}
        finally:
            hub.unsubscribe(q)

    return EventSourceResponse(event_generator())


@app.get("/api/healthz")
def healthz() -> dict:
    return {"ok": True, "tables": len(room.tables)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=bool(os.environ.get("RELOAD")),
    )
