"""Encode the engine's Observation into a fixed vector, and decode a discrete RL
action back into a Decision. This is the only place the RL world meets the engine,
so training and play share one representation.

Observation vector (OBS_DIM):
  [0:52]   hole multi-hot   (your two cards)
  [52:104] board multi-hot  (community cards so far)
  [104:]   12 scalar features (pot odds, commitment, stacks, street, sizing, …)

Actions (N_ACTIONS = 5, discrete):
  0 fold · 1 check/call · 2 raise ~½ pot · 3 raise ~pot · 4 all-in
Illegal choices are remapped to the nearest legal action so the policy can never
make an illegal move (the engine also enforces legality as a backstop).
"""
from __future__ import annotations

import numpy as np

from playsim.agent import Decision, Observation
from playsim.equity import FULL_DECK

CARD_INDEX = {c: i for i, c in enumerate(FULL_DECK)}
assert len(CARD_INDEX) == 52, "expected a 52-card deck from playsim.equity"

N_SCALARS = 12
OBS_DIM = 52 + 52 + N_SCALARS
N_ACTIONS = 5
_STARTING_STACK_REF = 200  # normalization reference (bb units assumed sb/bb = 1/2)


def encode_obs(o: Observation) -> np.ndarray:
    v = np.zeros(OBS_DIM, dtype=np.float32)
    v[CARD_INDEX[o.hole[0]]] = 1.0
    v[CARD_INDEX[o.hole[1]]] = 1.0
    for c in o.board:
        v[52 + CARD_INDEX[c]] = 1.0

    pot = max(o.pot, 1)
    stack = max(o.my_stack, 1)
    bb = max(o.big_blind, 1)
    s = [
        o.to_call / (pot + o.to_call),                 # pot odds
        pot / (pot + stack),                           # pot commitment
        min(stack / (_STARTING_STACK_REF * bb), 2.0),  # stack depth (bb-normalized)
        min(o.to_call / (20 * bb), 1.0),               # bet faced (capped)
        (o.street or 0) / 3.0,                          # street
        min(o.n_active / 2.0, 1.0),                     # opponents live
        1.0 if o.weak_opponent else 0.0,               # a weak opponent is in
        min(o.min_raise_to / (stack + o.to_call + 1), 1.0),
        min(o.max_raise_to / (stack + o.to_call + 1), 1.0),
        1.0 if o.to_call == 0 else 0.0,                # can check
        1.0 if o.to_call > 0 else 0.0,                 # facing a bet
        min(pot / (50 * bb), 1.0),                      # absolute pot size (capped)
    ]
    v[104:] = np.asarray(s, dtype=np.float32)
    return v


def can_raise(o: Observation) -> bool:
    """Raise-ability derived from the Observation alone (so the RL policy decides the
    same way in training and in the game seam, which only passes an Observation).
    PokerKit reports 0 min/max completion when no raise is legal."""
    return o.min_raise_to > 0 and o.max_raise_to >= o.min_raise_to


def legal_mask(o: Observation) -> np.ndarray:
    """1 = the action is meaningfully available (for masked policies / remap)."""
    m = np.zeros(N_ACTIONS, dtype=np.float32)
    m[0] = 1.0 if o.to_call > 0 else 0.0       # fold only when facing a bet
    m[1] = 1.0                                  # check/call always available
    if can_raise(o):
        m[2] = m[3] = m[4] = 1.0
    return m


def decode_action(action: int, o: Observation) -> Decision:
    """Map a discrete action to a legal Decision (remapping illegal choices)."""
    if action == 0:
        if o.to_call > 0:
            return Decision("fold")
        return Decision("check_call")          # never fold for free
    if action == 1:
        return Decision("check_call")
    # raise family
    if not can_raise(o):
        return Decision("check_call")
    pot = o.pot
    if action == 2:
        target = o.to_call + 0.5 * (pot + o.to_call)
    elif action == 3:
        target = o.to_call + 1.0 * (pot + o.to_call)
    else:  # all-in
        target = o.max_raise_to
    amt = int(round(max(o.min_raise_to, min(o.max_raise_to, target))))
    return Decision("raise", amount=amt)
