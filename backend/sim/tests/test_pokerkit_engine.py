import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim import deck  # noqa: E402
from sim.engine.base import Action  # noqa: E402
from sim.engine.pokerkit_engine import PokerKitEngine  # noqa: E402


def _fold_to_bets(ctx):
    return Action("fold") if ctx.to_call > 0 else Action("check_call")


def _drive(line_fn, seed_deck):
    eng = PokerKitEngine()
    eng.start_hand(deck=seed_deck, button=0, blinds=(1, 2),
                   starting_stacks=[200, 200, 200])
    guard = 0
    while not eng.is_done() and guard < 500:
        guard += 1
        if eng.actor() is None:
            break
        eng.apply(line_fn(eng.context()))
    return eng


def test_hand_completes_and_conserves_chips():
    res = _drive(_fold_to_bets, deck.full_deck()).result()
    assert sum(res.payoffs) == 0 and len(res.payoffs) == 3


def test_context_exposes_valid_cards():
    eng = PokerKitEngine()
    eng.start_hand(deck=deck.full_deck(), button=0, blinds=(1, 2),
                   starting_stacks=[200, 200, 200])
    assert eng.actor() is not None
    ctx = eng.context()
    assert len(ctx.hole) == 2
    assert all(len(c) == 2 and c[0] in deck.RANKS and c[1] in deck.SUITS for c in ctx.hole)
    assert ctx.num_players == 3 and ctx.n_opponents == 2


def test_raise_line_conserves_chips():
    state = {"raised": False}

    def line(ctx):
        if not state["raised"]:
            state["raised"] = True
            return Action("raise_to", 6)        # raise over the big blind
        return _fold_to_bets(ctx)

    res = _drive(line, deck.full_deck()).result()
    assert sum(res.payoffs) == 0


def test_same_deck_same_payoffs():
    a = _drive(_fold_to_bets, deck.full_deck()).result()
    b = _drive(_fold_to_bets, deck.full_deck()).result()
    assert a.payoffs == b.payoffs
