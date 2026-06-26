"""Play HTTP surface (offline -- the action/state path needs no LLM).

Mounts the play router on a bare app (no Room/main init) and drives a full hand
over HTTP, plus the error paths. The live /coach call is exercised in the live
end-to-end run, not here; we only assert it is correctly gated (409) before the
hand completes.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.play_api import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_play_a_full_hand_over_http():
    c = _client()
    r = c.post("/api/play/new", json={"seed": 7})
    assert r.status_code == 200
    body = r.json()
    sid, st = body["session_id"], body["state"]
    assert not st["complete"] and st["legal"] is not None
    assert len(st["opponents"]) == 5

    guard = 0
    while not st["complete"] and guard < 200:
        guard += 1
        kind = "check" if st["legal"]["can_check"] else "call"
        r = c.post(f"/api/play/{sid}/action", json={"kind": kind})
        assert r.status_code == 200, r.text
        st = r.json()["state"]
    assert st["complete"]

    # state is fetchable and stays complete
    assert c.get(f"/api/play/{sid}").json()["state"]["complete"]


def test_unknown_session_is_404():
    c = _client()
    assert c.get("/api/play/nope").status_code == 404
    assert c.post("/api/play/nope/action", json={"kind": "check"}).status_code == 404


def test_invalid_action_is_422():
    c = _client()
    sid = c.post("/api/play/new", json={"seed": 1}).json()["session_id"]
    assert c.post(f"/api/play/{sid}/action", json={"kind": "wiggle"}).status_code == 422


def test_coach_before_complete_is_409():
    c = _client()
    sid = c.post("/api/play/new", json={"seed": 1}).json()["session_id"]
    assert c.post(f"/api/play/{sid}/coach").status_code == 409
