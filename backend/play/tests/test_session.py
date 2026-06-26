"""Play-session state machine + coach-summary assembly (offline -- no LLM call).

Verifies the orchestration that sits between the engine hook and the coach: a hand
plays to completion through the human seat, every human decision is recorded with a
real equity number, the decisive opponent resolves to a real archetype + leak, and
the assembled summary is exactly the shape the (already-proven) coach consumes. The
live coach call itself is tested in coach/tests; here we stop at the summary.
"""

from play.session import PlaySession
from play.session import _STREETS


def _play_passive(session: PlaySession):
    """A scripted human that checks when it can and calls otherwise -- never folds,
    so the hand reaches several decisions across streets."""
    st = session.state()
    guard = 0
    while not st.complete and guard < 200:
        guard += 1
        st = session.act("check" if st.legal.can_check else "call")
    return st


def test_hand_plays_to_completion_and_assembles_summary():
    session = PlaySession(seed=7, hand_id=42)
    st = _play_passive(session)

    assert st.complete
    assert session.summary is not None            # the human acted at least once
    summary = session.summary

    # decisive opponent resolved to a real archetype with a named leak
    opp = summary["decisive_opponent"]
    assert opp["style_label"] and len(opp["leak"]) > 15
    assert opp["tendencies"]["bluff_pct"] >= 0

    # every decision carries a real equity number and a legal street
    assert summary["decisions"]
    for d in summary["decisions"]:
        assert 0.0 <= d["hero_equity_pct"] <= 100.0
        assert d["street"] in _STREETS
        assert d["hero_action"]

    # hero hole cards are two real cards
    assert len(summary["hero"]["hole"]) == 2


def test_bots_are_deterministic_for_a_seed():
    """Same seed + same human line => identical hand record (bots are the only other
    actors and they are seeded)."""
    a = PlaySession(seed=99, hand_id=1)
    _play_passive(a)
    b = PlaySession(seed=99, hand_id=1)
    _play_passive(b)
    assert a.hand.record == b.hand.record
    # and the derived equity is reproducible too
    assert a.summary["decisions"][0]["hero_equity_pct"] == b.summary["decisions"][0]["hero_equity_pct"]


def test_state_surfaces_seats_blinds_stacks_and_log():
    s = PlaySession(seed=7, hand_id=1)
    st = s.state()
    assert len(st.seats) == 6
    assert {'BTN', 'SB', 'BB'} <= {sv.role for sv in st.seats}   # blinds/button
    assert all(sv.stack_bb > 0 for sv in st.seats)               # stacks visible
    assert any(sv.is_hero for sv in st.seats)
    _play_passive(s)
    assert s.state().log                                         # action log populated


def test_variable_player_count_and_mystery():
    heads_up = PlaySession(bots=['recreational'], seed=1)
    assert heads_up.max_seats == 2 and len(heads_up.state().seats) == 2

    mystery = PlaySession(bots=['grinder', 'recreational'], reveal=False, seed=2)
    bots = [sv for sv in mystery.state().seats if not sv.is_hero]
    assert all(sv.label == 'Unknown' and sv.archetype is None for sv in bots)


def test_state_exposes_legal_actions_before_completion():
    session = PlaySession(seed=3, hand_id=1)
    st = session.state()
    if not st.complete:                     # hero has a turn
        lg = st.legal
        assert isinstance(lg.can_check, bool)
        # exactly one of check/call is offered depending on whether there's a bet
        assert lg.can_check != lg.can_call or (not lg.can_check and not lg.can_call)
