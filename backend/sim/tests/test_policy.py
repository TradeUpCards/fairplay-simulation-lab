import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim import deck  # noqa: E402
from sim.engine.base import DecisionContext  # noqa: E402
from sim.agents import policy  # noqa: E402
from sim.agents.archetype import Agent, ARCHETYPES  # noqa: E402


def _ctx(to_call=10, pot=30, stack=200, street="flop"):
    return DecisionContext(seat=0, hole=["Ah", "Ks"], board=["Kd", "7c", "2h"],
                           to_call=to_call, pot=pot, stack=stack, big_blind=2,
                           position="late", n_opponents=1, street=street, num_players=6)


def test_strong_folds_when_behind_facing_bet():
    assert policy.strong_policy(_ctx(), equity=0.10).kind == "fold"


def test_strong_raises_when_far_ahead():
    assert policy.strong_policy(_ctx(), equity=0.90).kind == "raise_to"


def test_beginner_calls_below_breakeven():
    # odds = 10/40 = 0.25; the beginner calls with equity 0.20 (below break-even) — a leak.
    assert policy.beginner_policy(_ctx(to_call=10, pot=30), equity=0.20).kind == "check_call"


def test_beginner_folds_clear_air_to_a_big_bet():
    # odds = 60/90 ≈ 0.67; with trash equity even the station folds (not infinite calling).
    assert policy.beginner_policy(_ctx(to_call=60, pot=30), equity=0.10).kind == "fold"


def test_preflop_open_is_small():
    # A preflop raise opens to ~3bb, not a pot-fraction escalation.
    a = policy._raise_to(_ctx(to_call=2, pot=3, street="preflop"), 0.6)
    assert a.kind == "raise_to" and a.amount == 6        # 3 * big_blind


def test_bluff_raise_is_tagged():
    # bluff_freq=2.0 forces the (probabilistic) bluff branch so the test is deterministic.
    fish = ARCHETYPES["aggressive_predatory"]._replace(skill=0.0, bluff_freq=2.0)
    out = policy.apply_style(policy.Action("fold"), _ctx(), equity=0.10, arch=fish,
                             rng=random.Random(0))
    assert out.kind == "raise_to" and out.tag == "bluff"


def _preflop_ctx(hole, to_call=2, position="early"):
    return DecisionContext(seat=0, hole=hole, board=[], to_call=to_call, pot=3, stack=200,
                           big_blind=2, position=position, n_opponents=2,
                           street="preflop", num_players=6)


def test_preflop_gate_folds_trash():
    # Even a loose recreational agent folds 72o from early position.
    a = Agent(ARCHETYPES["recreational"]).decide(_preflop_ctx(["7d", "2c"]), random.Random(0))
    assert a.kind == "fold"


def test_preflop_gate_plays_premium():
    # AA clears every range gate — it never folds preflop.
    a = Agent(ARCHETYPES["grinder"]).decide(_preflop_ctx(["Ah", "As"]), random.Random(0))
    assert a.kind != "fold"


def test_beginner_commits_more_often_than_strong():
    # Over many random flop spots facing a pot-sized bet, the loose beginner commits
    # (calls/raises) more often than the disciplined strong line. Style noise off.
    strong = Agent(ARCHETYPES["grinder"]._replace(skill=1.0, aggression=0.0, bluff_freq=0.0))
    weak = Agent(ARCHETYPES["grinder"]._replace(skill=0.0, aggression=0.0, bluff_freq=0.0))
    full = deck.full_deck()
    s_commit = w_commit = 0
    for i in range(40):
        d = full[:]
        random.Random(i).shuffle(d)
        ctx = DecisionContext(seat=0, hole=d[0:2], board=d[2:5], to_call=30, pot=30,
                              stack=200, big_blind=2, position="late", n_opponents=1,
                              street="flop", num_players=6)
        if strong.decide(ctx, random.Random(1000 + i)).kind != "fold":
            s_commit += 1
        if weak.decide(ctx, random.Random(1000 + i)).kind != "fold":
            w_commit += 1
    assert w_commit > s_commit
