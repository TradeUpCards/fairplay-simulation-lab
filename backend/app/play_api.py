"""HTTP surface for the single-human training table.

    POST /api/play/new            -> {session_id, state}    start a hand
    GET  /api/play/{sid}          -> {session_id, state}     current state
    POST /api/play/{sid}/action   -> {session_id, state}     submit a move
    POST /api/play/{sid}/coach    -> {session_id, coaching}  one live coach call (hand complete only)

Sessions live in an in-memory store -- a single-process POC, not durable. The
action endpoint is fast (engine + bots only); coaching is a separate call so the UI
can play the hand snappily and then fetch the (slower, live) coaching afterwards.
"""

from __future__ import annotations

import functools
import subprocess
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from play.session import PlaySession

router = APIRouter(prefix="/api/play", tags=["play"])


@functools.lru_cache(maxsize=1)
def _version() -> str:
    """Short git SHA (+ '-dirty') of the running code, for the debug overlay."""
    root = Path(__file__).resolve().parents[2]
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=root, text=True,
            stderr=subprocess.DEVNULL).strip()
        dirty = subprocess.call(
            ["git", "diff", "--quiet"], cwd=root,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0
        return sha + ("-dirty" if dirty else "")
    except Exception:  # noqa: BLE001
        return "unknown"

_SESSIONS: dict[str, PlaySession] = {}
_VALID_ACTIONS = {"fold", "check", "call", "raise"}


class NewBody(BaseModel):
    bots: Optional[list[str]] = None      # 1-5 archetypes (empty entries dropped); default mix
    hero_seat: int = 2                    # the human's fixed seat (players don't move)
    reveal: bool = True                   # False = "mystery": opponent styles hidden
    button_seat: Optional[int] = None     # rotates the dealer button between hands
    seed: int = 0
    stack_bb: int = 100


class ActionBody(BaseModel):
    kind: str                              # fold | check | call | raise
    amount: int = 0                        # total raise-to chips (for "raise")


def _envelope(sid: str, session: PlaySession) -> dict:
    return {"session_id": sid, "state": asdict(session.state())}


def _get(sid: str) -> PlaySession:
    session = _SESSIONS.get(sid)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")
    return session


@router.post("/new")
def new_hand(body: NewBody) -> dict:
    try:
        session = PlaySession(
            hero_seat=body.hero_seat, bots=body.bots, reveal=body.reveal,
            button_seat=body.button_seat, seed=body.seed, stack_bb=body.stack_bb,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    sid = uuid.uuid4().hex[:12]
    _SESSIONS[sid] = session
    return _envelope(sid, session)


@router.get("/{sid}")
def get_state(sid: str) -> dict:
    return _envelope(sid, _get(sid))


@router.post("/{sid}/action")
def submit_action(sid: str, body: ActionBody) -> dict:
    session = _get(sid)
    if body.kind not in _VALID_ACTIONS:
        raise HTTPException(status_code=422, detail=f"invalid action kind: {body.kind!r}")
    try:
        session.act(body.kind, body.amount)
    except RuntimeError as e:                      # e.g. acting on a completed hand
        raise HTTPException(status_code=409, detail=str(e))
    return _envelope(sid, session)


@router.post("/{sid}/coach")
def get_coaching(sid: str) -> dict:
    session = _get(sid)
    if not session.hand.complete:
        raise HTTPException(status_code=409, detail="hand is not complete yet")
    return {"session_id": sid, "coaching": session.coaching(), "version": _version()}
