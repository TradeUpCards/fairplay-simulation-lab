"""GATE: prove PokerKit supports decision injection + manual dealing + determinism.

If this can't be made to pass, switch the engine to option B (treys + own betting
loop); everything above the Engine seam in the plan is unchanged.

Run:  python -m pytest sim/tests/test_pokerkit_spike.py -v
"""
from pokerkit import Automation, NoLimitTexasHoldem

AUTOMATIONS = (
    Automation.ANTE_POSTING,
    Automation.BET_COLLECTION,
    Automation.BLIND_OR_STRADDLE_POSTING,
    Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
    Automation.HAND_KILLING,
    Automation.CHIPS_PUSHING,
    Automation.CHIPS_PULLING,
)  # NOTE: HOLE_DEALING / BOARD_DEALING intentionally absent — we deal manually.

HOLES = ["AhAs", "KdKc", "7h2d"]
BOARD = ["2s", "3s", "4s", "5d", "6c"]   # no collision with the hole cards


def _play_fixed_hand():
    s = NoLimitTexasHoldem.create_state(
        AUTOMATIONS, True, 0, (1, 2), 2, (200, 200, 200), 3,
    )
    for h in HOLES:
        s.deal_hole(h)
    guard = 0
    while s.status and guard < 300:
        guard += 1
        if s.card_burning_status:            # burn pending before a board street
            s.burn_card("??")                # "??" = unknown card; not from our deck
        elif s.actor_index is not None:      # a betting decision — inject one
            s.check_or_call()
        elif s.can_deal_board():             # between streets — we supply the board
            have = len(s.board_cards)
            need = 3 if have == 0 else 1
            s.deal_board("".join(BOARD[have:have + need]))
        else:
            break
    return s


def test_decisions_inject_and_chips_conserve():
    s = _play_fixed_hand()
    assert not s.status                       # hand completed
    assert s.payoffs is not None
    assert sum(s.payoffs) == 0                # chips conserved


def test_fixed_deal_and_line_is_deterministic():
    a = _play_fixed_hand()
    b = _play_fixed_hand()
    assert tuple(a.payoffs) == tuple(b.payoffs)
