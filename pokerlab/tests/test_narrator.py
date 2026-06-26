"""The optional LLM narrator must degrade gracefully: with no API key it reports
unavailable and the deterministic coach stands alone — no import errors, no crash."""
from __future__ import annotations

from pokerlab.coach import narrator
from pokerlab.engine import GameSession
from playsim.agent import Decision

_FAKE_COACHING = {
    "hole": ["As", "Kd"], "board": ["2c", "7h", "Jd"], "opp_hole": ["Qs", "Qh"],
    "net_bb": -3.0, "decisions": [],
    "summary": {"ev_lost_bb": 1.0, "headline": "test"},
}


def test_narrator_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert narrator.available() is False
    assert narrator.narrate(_FAKE_COACHING, "The Rock") is None


def test_session_narration_is_none_when_off(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    g = GameSession("station", seed=5)
    while not g.state_view()["over"]:
        if g.state_view()["your_turn"]:
            g.submit_human(Decision("check_call"))
    assert g.narration() is None          # gracefully off, deterministic coach unaffected
    assert g.coaching()["summary"] is not None
