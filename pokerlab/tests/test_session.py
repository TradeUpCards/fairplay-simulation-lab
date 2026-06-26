"""GameSession flow: the human must always land on a hand they can act in. Walk
hands (bot open-folds the SB, human is BB and never acts) are skipped, never shown
as a dead 'you won, you did nothing' screen — the bug that made the game feel broken."""
from __future__ import annotations

import pytest

from pokerlab.engine import GameSession
from playsim.agent import Decision

HEURISTIC = ["rock", "station", "maniac", "grinder", "solver"]


@pytest.mark.parametrize("style", HEURISTIC)
def test_fresh_game_is_immediately_playable(style):
    g = GameSession(style, seed=7)
    sv = g.state_view()
    assert not sv["over"], f"{style}: fresh game dumped on an over screen"
    assert sv["your_turn"], f"{style}: fresh game is not the human's turn"
    assert sv["legal"] is not None
    btn = [s["seat"] for s in sv["seats"] if s["is_button"]]
    assert len(btn) == 1, "exactly one seat holds the button"


def test_session_stats_and_history_track_real_hands():
    g = GameSession("station", seed=5)
    for _ in range(12):
        while not g.state_view()["over"]:
            if g.state_view()["your_turn"]:
                g.submit_human(Decision("check_call"))
        g.next_hand()

    stats = g.state_view()["stats"]
    assert stats["hands_played"] >= 10
    assert stats["won"] + stats["lost"] + stats["tie"] == stats["hands_played"]

    hv = g.history_view()
    assert len(hv["hands"]) == stats["hands_played"]
    for h in hv["hands"]:                                    # each entry replays its coaching
        assert h["outcome"] in ("won", "lost", "tie")
        assert "summary" in h["coaching"]
    nos = [h["hand_no"] for h in hv["hands"]]
    assert nos == sorted(nos, reverse=True)                  # newest first


def test_human_reaches_a_decision_on_every_hand():
    # rock open-folds the small blind ~40% of the time -> exercises the walk-skip loop
    g = GameSession("rock", seed=3)
    for _ in range(25):
        assert g.state_view()["your_turn"], "human dumped on a no-action hand"
        guard = 0
        while not g.state_view()["over"]:
            guard += 1
            assert guard < 300
            if g.state_view()["your_turn"]:
                g.submit_human(Decision("check_call"))
        g.next_hand()
        walks = g.state_view().get("walks")
        if walks:                                   # when walks were skipped, report is well-formed
            assert walks["count"] >= 1
            assert isinstance(walks["net_bb"], (int, float))
