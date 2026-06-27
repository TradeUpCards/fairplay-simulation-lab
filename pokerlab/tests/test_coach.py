"""Post-hand EV/equity coach: pure-threshold logic, forced mistake scenarios via a
duck-typed hand, and a determinism/structure check over a real session."""
from __future__ import annotations

from pokerlab.coach import coach_hand
from pokerlab.coach.coach import _verdict
from pokerlab.engine import GameSession
from pokerlab.engine.game import ActionEvent
from playsim.agent import Decision


def test_verdict_thresholds():
    assert _verdict(None) == "info"
    assert _verdict(0.0) == "ok"
    assert _verdict(0.49) == "ok"
    assert _verdict(0.5) == "good"
    assert _verdict(-0.5) == "mistake"
    assert _verdict(3.1) == "good"
    assert _verdict(-9.0) == "mistake"


class _FakeHand:
    """Minimal finished-hand stand-in (the coach only reads these attributes)."""
    def __init__(self, hole, opp_hole, board, events, payoff):
        self.n = 2
        self.seat_player_ids = [0, 1]
        self.hole = [list(hole), list(opp_hole)]
        self.board = list(board)
        self.events = events
        self._payoff = payoff

    def payoffs(self):
        return self._payoff


def test_loose_call_facing_overbet_is_a_mistake():
    # call 100 into a pot of 2 with a weak hand (~river air) -> deeply -EV
    board, hole, opp = ["3s", "9h", "Jd", "4c", "6s"], ("2c", "7d"), ("Ah", "Ks")
    ev = ActionEvent(0, 0, 3, "call", 100, 2, 100)
    hand = _FakeHand(hole, opp, board, [ev], {0: -100, 1: 100})
    out = coach_hand(hand, 0, 1, 2, seed=1, samples=80)
    d = out["decisions"][0]
    assert d["verdict"] == "mistake"
    assert d["ev_bb"] < 0
    assert out["summary"]["ev_lost_bb"] > 0
    assert out["summary"]["biggest_leak"] is not None
    assert "call" in d["note"].lower()


def test_folding_great_odds_with_real_equity_is_a_tight_fold_mistake():
    # fold pair-of-jacks facing 2 into a pot of 100 -> folding real equity is -EV
    board, hole, opp = ["Jd", "9h", "4c", "6s", "Ks"], ("Jh", "2c"), ("3d", "5d")
    ev = ActionEvent(0, 0, 3, "fold", 0, 100, 2)
    hand = _FakeHand(hole, opp, board, [ev], {0: 0, 1: 0})
    out = coach_hand(hand, 0, 1, 2, seed=1, samples=80)
    d = out["decisions"][0]
    assert d["equity"] > 0.4                       # a made pair has plenty of equity
    assert d["verdict"] == "mistake"
    assert d["ev_bb"] < 0
    assert "fold" in d["note"].lower()
    assert d["pot_odds"] is not None and d["pot_odds"] < 0.05


def test_session_coaching_is_deterministic_and_well_formed():
    def play_and_coach(seed):
        g = GameSession("station", seed=seed)
        outs = []
        for _ in range(8):
            guard = 0
            while not g.state_view()["over"]:
                guard += 1
                assert guard < 300
                if g.state_view()["your_turn"]:
                    g.submit_human(Decision("check_call"))
            outs.append(g.coaching())
            g.next_hand()
        return outs

    a = play_and_coach(5)
    b = play_and_coach(5)
    assert a == b                                   # fully deterministic given the seed
    assert any(o["decisions"] for o in a)           # some hands had gradeable decisions
    for o in a:
        for d in o["decisions"]:
            assert d["verdict"] in {"good", "ok", "mistake", "info"}
            assert 0.0 <= d["equity"] <= 1.0
            assert 0.0 <= d["actual_equity"] <= 1.0
