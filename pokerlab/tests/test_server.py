"""Server smoke test (FastAPI TestClient): create a game, play actions, next hand."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]          # worktree root (has pokerlab/ + playsim/)
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "playsim"))

from fastapi.testclient import TestClient  # noqa: E402
from pokerlab.server.app import app  # noqa: E402

client = TestClient(app)


def test_styles():
    r = client.get("/api/styles")
    assert r.status_code == 200
    keys = {s["key"] for s in r.json()["styles"]}
    assert {"rock", "station", "maniac", "grinder", "solver"} <= keys


def test_play_a_few_actions():
    r = client.post("/api/games", json={"style": "maniac", "seed": 3})
    assert r.status_code == 200
    gid = r.json()["game_id"]
    state = r.json()["state"]

    steps = 0
    while steps < 60:
        steps += 1
        if state["over"]:
            state = client.post(f"/api/games/{gid}/next").json()["state"]
            continue
        if state["your_turn"]:
            legal = state["legal"]
            kind = "check_call"          # always check/call — exercises the loop
            state = client.post(f"/api/games/{gid}/action",
                                json={"kind": kind}).json()["state"]
        else:
            # shouldn't happen (bots auto-advance), but re-read defensively
            state = client.get(f"/api/games/{gid}").json()["state"]
    assert state["hand_no"] >= 2


def test_raise_and_fold_paths():
    gid = client.post("/api/games", json={"style": "rock", "seed": 9}).json()["game_id"]
    state = client.get(f"/api/games/{gid}").json()["state"]
    # find a spot where we can raise, do a min-raise; otherwise just check/call once
    if state["your_turn"] and state["legal"]["can_raise"]:
        amt = state["legal"]["min_raise_to"]
        r = client.post(f"/api/games/{gid}/action", json={"kind": "raise", "amount": amt})
        assert r.status_code == 200
    # bad action kind rejected
    bad = client.post(f"/api/games/{gid}/action", json={"kind": "bogus"})
    assert bad.status_code == 400


if __name__ == "__main__":
    test_styles()
    test_play_a_few_actions()
    test_raise_and_fold_paths()
    print("OK — server smoke passed")
