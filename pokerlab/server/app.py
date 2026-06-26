"""FastAPI turn-by-turn server for the poker training game.

One GameSession per game id (in-memory). The UI: create a game, read state, post
the human's action (or 'next hand'), re-read state. The session auto-plays the
bot's turns, so every response is either the human's turn or a finished hand.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from playsim.agent import Decision

from ..engine import GameSession, known, roster

# Load pokerlab/.env (e.g. ANTHROPIC_API_KEY for the optional narrator) if present.
# Graceful: works without python-dotenv installed, and without a .env file.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

app = FastAPI(title="pokerlab — AI Poker Training Lab")

# Vite dev server origins (the standalone game UI).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

_GAMES: dict[str, GameSession] = {}


class NewGame(BaseModel):
    style: str = "maniac"
    seed: int | None = None
    starting_stack: int = 200


class Action(BaseModel):
    kind: str                  # "fold" | "check_call" | "raise"
    amount: int = 0            # total raise-to (for "raise")


def _get(gid: str) -> GameSession:
    g = _GAMES.get(gid)
    if g is None:
        raise HTTPException(404, "game not found")
    return g


@app.get("/api/styles")
def styles():
    return {"styles": roster()}


@app.post("/api/games")
def new_game(body: NewGame):
    if not known(body.style):
        raise HTTPException(400, f"unknown style {body.style!r}")
    gid = uuid.uuid4().hex[:12]
    _GAMES[gid] = GameSession(body.style, starting_stack=body.starting_stack, seed=body.seed)
    return {"game_id": gid, "state": _GAMES[gid].state_view()}


@app.get("/api/games/{gid}")
def get_state(gid: str):
    return {"game_id": gid, "state": _get(gid).state_view()}


@app.post("/api/games/{gid}/action")
def act(gid: str, body: Action):
    g = _get(gid)
    if body.kind not in ("fold", "check_call", "raise"):
        raise HTTPException(400, "kind must be fold | check_call | raise")
    try:
        g.submit_human(Decision(body.kind, amount=body.amount))
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from None
    return {"game_id": gid, "state": g.state_view()}


@app.post("/api/games/{gid}/next")
def next_hand(gid: str):
    g = _get(gid)
    try:
        g.next_hand()
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from None
    return {"game_id": gid, "state": g.state_view()}


@app.get("/api/games/{gid}/coaching")
def coaching(gid: str):
    g = _get(gid)
    try:
        return {"game_id": gid, "coaching": g.coaching()}
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from None


@app.get("/api/games/{gid}/history")
def history(gid: str):
    g = _get(gid)
    return {"game_id": gid, **g.history_view()}


@app.get("/api/narrator")
def narrator_status():
    """Cheap check (no model call) so the UI knows whether to offer 'Coach's take'."""
    from ..coach.narrator import available
    return {"available": available()}


@app.get("/api/games/{gid}/narration")
def narration(gid: str):
    g = _get(gid)
    from ..coach.narrator import available
    if not available():
        return {"game_id": gid, "available": False, "narration": None}
    try:
        return {"game_id": gid, "available": True, "narration": g.narration()}
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from None


# In production (Docker), the built UI is served from the same origin as the API.
# Mounted LAST so it never shadows the /api routes above; skipped in dev (no dist).
_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="web")
