"""The replay guarantee: same (table, seed, hands) → byte-identical result."""

from playsim.rosters import get_roster
from playsim.runner import run_session


def test_same_seed_is_identical():
    roster = get_roster("case_c")
    a = run_session(roster, 120, seed=7, equity_samples=16)
    b = run_session(roster, 120, seed=7, equity_samples=16)
    assert a.features == b.features
    assert [h.payoffs for h in a.hands] == [h.payoffs for h in b.hands]
    assert [h.board for h in a.hands] == [h.board for h in b.hands]


def test_different_seed_differs():
    roster = get_roster("case_c")
    a = run_session(roster, 120, seed=7, equity_samples=16)
    c = run_session(roster, 120, seed=8, equity_samples=16)
    assert [h.board for h in a.hands] != [h.board for h in c.hands]
