"""Headless smoke test: drive a GameSession with a scripted 'human' and verify the
steppable loop runs hands end-to-end, conserves chips, and produces a sane view."""
import sys
from pathlib import Path

# allow running directly (pytest also picks it up)
sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent))  # pokerlab/..
from pokerlab.engine import GameSession, HUMAN_ID  # noqa: E402
from playsim.agent import Decision  # noqa: E402


def _scripted_human(view) -> Decision:
    """A trivial human: check when free, otherwise call (never folds/raises) —
    just enough to exercise the loop."""
    legal = view["legal"]
    if legal["can_check"]:
        return Decision("check_call")
    return Decision("check_call")  # call


def _play(style, hands=8, seed=7):
    g = GameSession(style, starting_stack=200, sb=1, bb=2, seed=seed)
    total = sum(g.stacks.values())
    for _ in range(hands):
        guard = 0
        while not g.state_view()["over"]:
            guard += 1
            assert guard < 500, "hand did not terminate"
            v = g.state_view()
            if v["your_turn"]:
                g.submit_human(_scripted_human(v))
            # else: bots auto-advanced already inside the session
        v = g.state_view()
        assert v["result"] is not None
        # chips conserved within a hand (no reload this run with 200bb start)
        assert sum(g.stacks.values()) in (total, 400), g.stacks
        g.next_hand()
    return g


def test_all_styles_play_through():
    for style in ("rock", "station", "maniac", "grinder", "solver"):
        g = _play(style)
        assert g.hand_no >= 8


def test_view_shape():
    g = GameSession("maniac", seed=1)
    v = g.state_view()
    assert set(v) >= {"hand_no", "board", "pot", "seats", "your_turn", "log", "over"}
    assert len(v["seats"]) == 2
    you = next(s for s in v["seats"] if s["is_human"])
    assert you["hole"] is not None and len(you["hole"]) == 2     # you always see your cards
    opp = next(s for s in v["seats"] if not s["is_human"])
    assert opp["hole"] is None                                   # opponent hidden pre-showdown


if __name__ == "__main__":
    test_all_styles_play_through()
    test_view_shape()
    print("OK — engine smoke passed")
