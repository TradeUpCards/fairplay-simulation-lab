"""HeadsUpPokerEnv — a Gymnasium env over the PokerKit HandSession.

One learner seat vs a fixed heuristic opponent (a playsim ArchetypeAgent). An
episode is one hand; reward is the learner's chip delta (normalized). Position
alternates each episode so the policy sees both button and big blind. The opponent
plays inside the env, so standard single-agent PPO (CleanRL) trains directly.
Self-play (a PettingZoo AEC wrapper, both seats learning) is the later stretch —
the engine (PokerKit via HandSession) is already shared with play.
"""
from __future__ import annotations

import random

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from playsim.agent import ArchetypeAgent
from playsim.knobs import Knobs, knobs_for

from ..engine.game import HandSession
from .encode import N_ACTIONS, OBS_DIM, decode_action, encode_obs, legal_mask

LEARNER_ID = 0
OPP_ID = 1
_CHECK_ONLY_MASK = np.array([0, 1, 0, 0, 0], dtype=np.float32)


def _resolve_knobs(opponent: str | Knobs) -> Knobs:
    """Accept a Knobs, a pokerlab game style (rock/station/maniac/…), or a playsim
    archetype name."""
    if isinstance(opponent, Knobs):
        return opponent
    from ..engine.agents import BOT_STYLES  # lazy to avoid an import cycle
    if opponent in BOT_STYLES:
        return BOT_STYLES[opponent].knobs
    return knobs_for(opponent)


class HeadsUpPokerEnv(gym.Env):
    metadata: dict = {"render_modes": []}

    def __init__(self, opponent: str | Knobs = "regular", starting_stack: int = 200,
                 sb: int = 1, bb: int = 2, seed: int = 0, opp_equity_samples: int = 20):
        super().__init__()
        self.observation_space = spaces.Box(-1.0, 2.0, shape=(OBS_DIM,), dtype=np.float32)
        self.action_space = spaces.Discrete(N_ACTIONS)
        self.starting_stack = starting_stack
        self.sb, self.bb = sb, bb
        self._opp = ArchetypeAgent(OPP_ID, _resolve_knobs(opponent),
                                   equity_samples=opp_equity_samples)
        self._rng = random.Random(seed)
        self._ep = 0
        self._hand: HandSession | None = None
        self._seat_ids: list[int] = []

    # -- gym API ----------------------------------------------------------
    def reset(self, *, seed: int | None = None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        # Deal until the learner actually faces a decision. If the opponent ends the
        # hand before the learner acts (e.g. folds the small blind preflop), there's
        # nothing to learn that episode — redeal. Position alternates, so the learner
        # is first-to-act every other hand, which guarantees this terminates.
        while True:
            self._ep += 1
            self._seat_ids = [LEARNER_ID, OPP_ID] if self._ep % 2 == 0 else [OPP_ID, LEARNER_ID]
            stacks = [self.starting_stack, self.starting_stack]
            self._hand = HandSession(self._seat_ids, stacks, self.sb, self.bb, self._rng)
            self._play_opponent()
            if not self._hand.done:
                return self._obs(), self._info()

    def step(self, action):
        self._hand.apply(decode_action(int(action), self._hand.observation()))
        self._play_opponent()
        if self._hand.done:
            net = self._hand.payoffs()[LEARNER_ID]
            reward = net / self.starting_stack
            return (np.zeros(OBS_DIM, dtype=np.float32), float(reward), True, False,
                    {"action_mask": _CHECK_ONLY_MASK, "net_chips": net})
        return self._obs(), 0.0, False, False, self._info()

    # -- internals --------------------------------------------------------
    def _play_opponent(self):
        while not self._hand.done:
            pid = self._seat_ids[self._hand.actor_seat()]
            if pid == LEARNER_ID:
                return
            self._hand.apply(self._opp.act(self._hand.observation(), self._rng))

    def _obs(self) -> np.ndarray:
        if self._hand.done:
            return np.zeros(OBS_DIM, dtype=np.float32)
        return encode_obs(self._hand.observation())

    def _info(self) -> dict:
        if self._hand.done:
            return {"action_mask": _CHECK_ONLY_MASK}
        return {"action_mask": legal_mask(self._hand.observation())}
