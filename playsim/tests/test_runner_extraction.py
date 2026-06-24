"""U1 — regression guard for the per-hand accounting extraction.

``apply_hand_accounting`` was factored out of ``run_session`` so the room
orchestrator can reuse the exact same economics. These tests pin the helper's
behavior directly and confirm ``run_session``'s retention/leave path (whose
tilt-leave block moved out of the persist loop) stays deterministic.
"""

from __future__ import annotations

from playsim.knobs import knobs_for
from playsim.runner import Player, apply_hand_accounting, run_session
from playsim.table import ActionRecord, HandRecord


def _make_rec(payoffs, contest, showdown, *, pot_bb=50, bb=2):
    actions = [
        ActionRecord(pid, street, "bet", 10, 20, 100, True, True, False)
        for pid, street in contest
    ]
    return HandRecord(
        hand_id=0, button_seat=0, seat_player_ids=list(payoffs),
        starting_stacks={pid: 200 for pid in payoffs},
        hole={}, board=[], actions=actions, payoffs=dict(payoffs),
        pot_bb=pot_bb, big_blind=bb, showdown_player_ids=list(showdown),
    )


def test_skill_edge_transfer_is_zero_sum_and_accrues_counts():
    order = [1, 2, 3]
    knobs = {1: knobs_for("grinder"), 2: knobs_for("recreational"), 3: knobs_for("new")}
    rec = _make_rec({1: 30, 2: -20, 3: -10}, [(1, 1), (2, 1), (3, 1)], [1, 2, 3])
    before = sum(rec.payoffs.values())
    stacks = {p: 200 for p in order}
    net = {p: 0.0 for p in order}
    busts = {p: 0 for p in order}
    seat = {p: 0.0 for p in order}
    hands = {p: 0 for p in order}

    apply_hand_accounting(
        rec, order, stacks=stacks, net_session=net, busts=busts,
        seat_minutes=seat, hands_played=hands, knobs=knobs, bb=2, start=200,
        min_per_hand=0.75, rebuy_threshold_bb=8, skill_edge=0.5, persist_stacks=True,
    )

    # zero-sum transfer preserves the pot total to within per-player rounding
    assert abs(sum(rec.payoffs.values()) - before) <= len(order)
    # seat-time + hand counts accrue for everyone dealt in
    assert hands == {1: 1, 2: 1, 3: 1}
    assert all(abs(seat[p] - 0.75) < 1e-9 for p in order)
    # chip accounting reflects the (post-skill_edge) payoffs
    assert all(abs(net[p] - rec.payoffs[p] / 2) < 1e-9 for p in order)
    assert all(stacks[p] == 200 + rec.payoffs[p] for p in order)  # no bust at these sizes


def test_busted_stack_rebuys_exactly_once():
    order = [1, 2]
    knobs = {1: knobs_for("new"), 2: knobs_for("grinder")}
    rec = _make_rec({1: -195, 2: 195}, [], [])  # no contest -> skill_edge no-op
    stacks = {1: 200, 2: 200}
    net = {1: 0.0, 2: 0.0}
    busts = {1: 0, 2: 0}
    seat = {1: 0.0, 2: 0.0}
    hands = {1: 0, 2: 0}

    apply_hand_accounting(
        rec, order, stacks=stacks, net_session=net, busts=busts,
        seat_minutes=seat, hands_played=hands, knobs=knobs, bb=2, start=200,
        min_per_hand=0.75, rebuy_threshold_bb=8, skill_edge=0.0, persist_stacks=True,
    )

    assert busts[1] == 1 and stacks[1] == 200          # 5 chips < 16 threshold -> rebuy
    assert busts[2] == 0 and stacks[2] == 395
    assert abs(net[1] - (-195 / 2)) < 1e-9


def test_no_persist_updates_counts_only():
    order = [1, 2]
    knobs = {1: knobs_for("new"), 2: knobs_for("new")}
    rec = _make_rec({1: 50, 2: -50}, [], [])
    stacks = {1: 200, 2: 200}
    net = {1: 0.0, 2: 0.0}
    busts = {1: 0, 2: 0}
    seat = {1: 0.0, 2: 0.0}
    hands = {1: 0, 2: 0}

    apply_hand_accounting(
        rec, order, stacks=stacks, net_session=net, busts=busts,
        seat_minutes=seat, hands_played=hands, knobs=knobs, bb=2, start=200,
        min_per_hand=0.75, rebuy_threshold_bb=8, skill_edge=0.0, persist_stacks=False,
    )

    assert hands == {1: 1, 2: 1}
    assert all(abs(seat[p] - 0.75) < 1e-9 for p in order)
    assert stacks == {1: 200, 2: 200}   # untouched without persist
    assert net == {1: 0.0, 2: 0.0}
    assert busts == {1: 0, 2: 0}


def test_run_session_retention_path_deterministic_after_extraction():
    roster = [
        Player(1, "new"), Player(2, "recreational"),
        Player(3, "grinder"), Player(4, "aggressive_predatory"),
    ]
    a = run_session(roster, 60, seed=7, equity_samples=8, retention=True)
    b = run_session(roster, 60, seed=7, equity_samples=8, retention=True)

    assert a.seat_minutes == b.seat_minutes
    assert a.left_at_minute == b.left_at_minute
    assert a.busts == b.busts
    assert a.hands_played == b.hands_played
    assert a.retention is True
    assert a.paid_seat_minutes > 0
