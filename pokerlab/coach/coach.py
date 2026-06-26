"""Post-hand coaching — deterministic EV/equity analysis of the human's decisions.

For each *voluntary* decision the human made, we recompute the situation as it was
at that moment (hole cards + the board visible on that street) and judge it on the
information available *then*, not on the opponent's cards (that would be results-
oriented). Two numbers drive every verdict:

* **equity** — Monte-Carlo win probability of the human's hand vs a random hand
  (reusing ``playsim.equity.equity_mc``). This is the information-set equity.
* **pot odds** — when facing a bet, the equity needed to break even on a call.

From those we get a showdown-basis EV for call/fold spots and a signed leak in big
blinds: ``ev_bb`` = EV(action taken) − EV(best alternative); negative = chips left
on the table. Bets/raises/checks get an honest *classification* (value / bluff /
thin) rather than a hard EV claim, since their EV depends on the opponent's
response. A clearly-labelled hindsight line ("they actually had …") is included for
learning but never feeds the verdict.
"""
from __future__ import annotations

import random

from pokerkit import StandardHighHand

from playsim.equity import FULL_DECK, equity_mc

STREET_NAME = {0: "preflop", 1: "flop", 2: "turn", 3: "river"}
_VISIBLE = {0: 0, 1: 3, 2: 4, 3: 5}     # board cards visible when acting on each street
_MARGIN_BB = 0.5                         # smaller than this = a "close" spot, not a mistake


def _equity_vs_hand(hole, opp_hole, board, rng: random.Random, samples: int) -> float:
    """Exact/Monte-Carlo win prob of ``hole`` vs a *known* ``opp_hole`` (hindsight)."""
    known = set(hole) | set(opp_hole) | set(board)
    deck = [c for c in FULL_DECK if c not in known]
    need = 5 - len(board)
    hole_s, opp_s = "".join(hole), "".join(opp_hole)

    def score(run_board):
        bs = "".join(run_board)
        me = StandardHighHand.from_game(hole_s, bs)
        opp = StandardHighHand.from_game(opp_s, bs)
        return 1.0 if me > opp else (0.5 if me == opp else 0.0)

    if need == 0:
        return score(board)
    wins = 0.0
    for _ in range(samples):
        wins += score(board + rng.sample(deck, need))
    return wins / samples


def _verdict(ev_bb: float | None) -> str:
    if ev_bb is None:
        return "info"
    if ev_bb >= _MARGIN_BB:
        return "good"
    if ev_bb <= -_MARGIN_BB:
        return "mistake"
    return "ok"


def _note(action, eq, pot_odds, ev_bb, ev_call_bb) -> str:
    eqp = f"{eq:.0%}"
    if action == "fold":
        od = f"{pot_odds:.0%}"
        if ev_bb is not None and ev_bb <= -_MARGIN_BB:
            return (f"Tight fold — {eqp} equity was enough at {od} pot odds; "
                    f"calling was worth ~{ev_call_bb:+.1f}bb.")
        return f"Good fold — only {eqp} equity, you needed {od} to call."
    if action == "call":
        od = f"{pot_odds:.0%}"
        if ev_bb >= _MARGIN_BB:
            return f"+EV call — {eqp} equity beat the {od} price (~{ev_bb:+.1f}bb)."
        if ev_bb <= -_MARGIN_BB:
            return f"Loose call — needed {od}, had {eqp}; folding saves ~{-ev_bb:.1f}bb."
        return f"Marginal call — {eqp} vs {od} needed, about break-even."
    if action == "check":
        if eq >= 0.68:
            return f"Checked {eqp} equity — strong enough to bet for value."
        return f"Checked with {eqp} equity."
    if action in ("bet", "raise"):
        verb = "Value" if eq >= 0.55 else ("Bluff" if eq <= 0.35 else "Thin")
        tail = (" — needs fold equity to profit." if verb == "Bluff" else "")
        return f"{verb} {action} — {eqp} equity.{tail}"
    return f"{eqp} equity."


def coach_hand(hand, human_id: int, sb: int, bb: int, *, seed=0, samples: int = 200) -> dict:
    """Analyze one finished HandSession from ``human_id``'s perspective."""
    rng = random.Random(seed)
    human_seat = hand.seat_player_ids.index(human_id)
    opp_seat = next(s for s in range(hand.n) if s != human_seat)
    hole = tuple(hand.hole[human_seat])
    opp_hole = tuple(hand.hole[opp_seat])
    full_board = list(hand.board)

    decisions: list[dict] = []
    for ev in hand.events:
        if ev.seat != human_seat:
            continue
        board_at = full_board[: _VISIBLE[ev.street]]
        eq = equity_mc(hole, board_at, 1, rng, samples)
        to_call = getattr(ev, "to_call", 0)
        facing = to_call > 0

        pot_odds = (to_call / (ev.pot_before + to_call)) if facing else None
        ev_call_bb = ev_bb = None
        if facing:
            # showdown-basis EV of calling, in big blinds
            ev_call_chips = eq * ev.pot_before - (1 - eq) * to_call
            ev_call_bb = ev_call_chips / bb
            if ev.action == "fold":
                ev_bb = -ev_call_bb              # taken=fold(0) − alt=call
            elif ev.action == "call":
                ev_bb = ev_call_bb               # taken=call − alt=fold(0)

        decisions.append({
            "street": ev.street,
            "street_name": STREET_NAME.get(ev.street, str(ev.street)),
            "action": ev.action,
            "amount": ev.amount,
            "to_call": to_call,
            "pot_before": ev.pot_before,
            "equity": round(eq, 4),
            "pot_odds": round(pot_odds, 4) if pot_odds is not None else None,
            "ev_bb": round(ev_bb, 2) if ev_bb is not None else None,
            "verdict": _verdict(ev_bb),
            "note": _note(ev.action, eq, pot_odds, ev_bb, ev_call_bb),
            "actual_equity": round(_equity_vs_hand(hole, opp_hole, board_at, rng, samples), 4),
        })

    payoffs = hand.payoffs()
    net_bb = payoffs.get(human_id, 0) / bb
    leaks = [d for d in decisions if d["ev_bb"] is not None and d["ev_bb"] <= -_MARGIN_BB]
    ev_lost_bb = round(sum(-d["ev_bb"] for d in leaks), 2)
    biggest = min(leaks, key=lambda d: d["ev_bb"]) if leaks else None

    if not decisions:
        headline = "No decisions to coach — you had no voluntary action this hand."
    elif biggest is None:
        headline = f"Clean hand — no clear EV mistakes. Net {net_bb:+.1f}bb."
    else:
        headline = (f"Left ~{ev_lost_bb:.1f}bb on the table. Biggest leak: "
                    f"{biggest['street_name']} {biggest['action']} "
                    f"({biggest['ev_bb']:+.1f}bb).")

    return {
        "hole": list(hole),
        "opp_hole": list(opp_hole),
        "board": full_board,
        "net_bb": round(net_bb, 2),
        "decisions": decisions,
        "summary": {
            "net_bb": round(net_bb, 2),
            "ev_lost_bb": ev_lost_bb,
            "headline": headline,
            "biggest_leak": biggest,
        },
    }
