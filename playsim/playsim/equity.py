"""Hand-strength estimation: preflop percentile + postflop Monte-Carlo equity.

The decision engine needs two numbers:

* ``preflop_percentile(hole)`` — where a starting hand ranks among all 1326
  combos (0 = worst, 1 = best). Used directly as the looseness/aggression
  threshold so vpip/pfr calibrate analytically.
* ``equity_mc(hole, board, n_opponents, rng, samples)`` — Monte-Carlo win
  probability vs random opponent ranges, using PokerKit's evaluator.

All randomness flows through a caller-supplied ``random.Random`` so the whole
simulation stays seeded and reproducible.
"""

from __future__ import annotations

import random
from functools import lru_cache

from pokerkit import StandardHighHand

RANKS = "23456789TJQKA"
SUITS = "cdhs"
RANK_VAL = {r: i for i, r in enumerate(RANKS, start=2)}  # 2..14
FULL_DECK = [r + s for r in RANKS for s in SUITS]

# Chen point value for the high card (A=10, K=8, Q=7, J=6, else rank/2)
_CHEN_HIGH = {14: 10.0, 13: 8.0, 12: 7.0, 11: 6.0}


def _chen_score(c1: str, c2: str) -> float:
    """Bill Chen starting-hand score (higher = stronger)."""
    r1, s1 = RANK_VAL[c1[0]], c1[1]
    r2, s2 = RANK_VAL[c2[0]], c2[1]
    hi, lo = (r1, r2) if r1 >= r2 else (r2, r1)
    base = _CHEN_HIGH.get(hi, hi / 2.0)
    if r1 == r2:  # pair
        return max(base * 2.0, 5.0)
    score = base
    if s1 == s2:  # suited
        score += 2.0
    gap = hi - lo - 1
    score -= {0: 0.0, 1: 1.0, 2: 2.0, 3: 4.0}.get(gap, 5.0)
    if gap <= 1 and hi < 12:  # straight bonus for low connectors
        score += 1.0
    return score


@lru_cache(maxsize=1)
def _sorted_combo_scores() -> tuple[float, ...]:
    scores = []
    n = len(FULL_DECK)
    for i in range(n):
        for j in range(i + 1, n):
            scores.append(_chen_score(FULL_DECK[i], FULL_DECK[j]))
    scores.sort()
    return tuple(scores)


def preflop_percentile(hole: tuple[str, str]) -> float:
    """Fraction of all starting combos this hand beats or ties (0..1)."""
    score = _chen_score(hole[0], hole[1])
    combos = _sorted_combo_scores()
    # fraction with score <= ours (rank among all combos)
    lo, hi = 0, len(combos)
    while lo < hi:
        mid = (lo + hi) // 2
        if combos[mid] <= score:
            lo = mid + 1
        else:
            hi = mid
    return lo / len(combos)


def equity_mc(
    hole: tuple[str, str],
    board: list[str],
    n_opponents: int,
    rng: random.Random,
    samples: int = 30,
) -> float:
    """Monte-Carlo win probability vs ``n_opponents`` random hands.

    Deterministic given ``rng``. Ties split. Cheap by design (small ``samples``)
    — we need realistic tendencies, not solver-grade precision.
    """
    if n_opponents <= 0:
        return 1.0
    known = set(hole) | set(board)
    deck = [c for c in FULL_DECK if c not in known]
    need_board = 5 - len(board)
    wins = 0.0
    hole_str = "".join(hole)
    for _ in range(samples):
        draw = rng.sample(deck, n_opponents * 2 + need_board)
        opp_hands = [draw[k * 2 : k * 2 + 2] for k in range(n_opponents)]
        run_board = board + draw[n_opponents * 2 :]
        board_str = "".join(run_board)
        my = StandardHighHand.from_game(hole_str, board_str)
        best_opp = max(
            StandardHighHand.from_game("".join(h), board_str) for h in opp_hands
        )
        if my > best_opp:
            wins += 1.0
        elif my == best_opp:
            wins += 0.5
    return wins / samples
