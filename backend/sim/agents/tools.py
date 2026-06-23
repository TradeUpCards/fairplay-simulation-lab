"""Decision tools — pure reads over a DecisionContext snapshot. No engine."""
from __future__ import annotations

import random

from treys import Card, Evaluator

from sim import deck

_EV = Evaluator()


def pot_odds(pot: int, to_call: int) -> float:
    if to_call <= 0:
        return 0.0
    return to_call / (pot + to_call)


def position(seat: int, button: int, num_players: int) -> str:
    # Seats after the button act later; blinds are the two seats after the button.
    rel = (seat - button) % num_players
    if rel in (1, 2):
        return "blind"
    if rel <= num_players // 3:
        return "early"
    if rel <= 2 * num_players // 3:
        return "middle"
    return "late"


# Chen-formula preflop hand strength (≈ -1 for 72o up to 20 for AA).
_CHEN_VAL = {"A": 10.0, "K": 8.0, "Q": 7.0, "J": 6.0, "T": 5.0, "9": 4.5,
             "8": 4.0, "7": 3.5, "6": 3.0, "5": 2.5, "4": 2.0, "3": 1.5, "2": 1.0}
_RANK_ORD = {r: i for i, r in enumerate("23456789TJQKA", start=2)}   # 2..14


def preflop_strength(hole: list[str]) -> float:
    """Chen-formula starting-hand score. Higher = stronger; used to gate preflop play."""
    (ra, sa), (rb, sb) = (hole[0][0], hole[0][1]), (hole[1][0], hole[1][1])
    if ra == rb:                                   # pair
        return max(5.0, _CHEN_VAL[ra] * 2)
    score = max(_CHEN_VAL[ra], _CHEN_VAL[rb])
    if sa == sb:                                   # suited
        score += 2
    diff = abs(_RANK_ORD[ra] - _RANK_ORD[rb])
    gap = diff - 1                                 # 0 = connectors
    score -= {0: 0, 1: 1, 2: 2, 3: 4}.get(gap, 5)
    if gap <= 1 and max(_RANK_ORD[ra], _RANK_ORD[rb]) < 12:   # 0/1-gap straight bonus, both < Q
        score += 1
    return score


def _t(cards: list[str]) -> list[int]:
    return [Card.new(c) for c in cards]


def hand_equity(hole: list[str], board: list[str], n_opponents: int,
                rng: random.Random, samples: int = 200) -> float:
    """Monte-Carlo win probability. Deterministic given rng. Lower treys score = better."""
    known = set(hole) | set(board)
    live = [c for c in deck.full_deck() if c not in known]
    hole_t = _t(hole)
    wins = ties = 0
    for _ in range(samples):
        d = live[:]
        rng.shuffle(d)
        i = 0
        opp_holes = []
        for _ in range(n_opponents):
            opp_holes.append(d[i:i + 2])
            i += 2
        need = 5 - len(board)
        full_board = board + d[i:i + need]
        board_t = _t(full_board)
        mine = _EV.evaluate(board_t, hole_t)
        best_opp = min(_EV.evaluate(board_t, _t(o)) for o in opp_holes)
        if mine < best_opp:
            wins += 1
        elif mine == best_opp:
            ties += 1
    return (wins + 0.5 * ties) / samples
