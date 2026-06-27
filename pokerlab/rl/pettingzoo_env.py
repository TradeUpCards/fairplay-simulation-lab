"""The poker engine exposed as a standard PettingZoo **AEC** multi-agent env.

This is the MARL-legible interface: two agents (``player_0``, ``player_1``) take
turns over the *same* steppable PokerKit ``HandSession`` the game uses, with the
*same* obs/action encoding as the single-agent trainer. One hand = one episode;
reward is 0 until the hand ends, then each agent gets ``net_chips / starting_stack``.

Self-play training (``train_selfplay.py``) drives this env. It also conforms to
``pettingzoo.test.api_test`` so other MARL algorithms could plug in unchanged.
"""
from __future__ import annotations

import random

import numpy as np
from gymnasium import spaces
from pettingzoo import AECEnv
from pettingzoo.utils import wrappers

from ..engine.game import HandSession
from .encode import N_ACTIONS, OBS_DIM, decode_action, encode_obs, legal_mask


def env(**kwargs):
    """Wrapped env (bounds + order enforcement) — use this for api_test / external algos."""
    e = raw_env(**kwargs)
    e = wrappers.AssertOutOfBoundsWrapper(e)
    e = wrappers.OrderEnforcingWrapper(e)
    return e


class raw_env(AECEnv):
    metadata = {"render_modes": [], "name": "poker_hu_v0", "is_parallelizable": False}

    def __init__(self, starting_stack: int = 200, sb: int = 1, bb: int = 2, seed=None):
        super().__init__()
        self.starting_stack = starting_stack
        self.sb, self.bb = sb, bb
        self.possible_agents = ["player_0", "player_1"]   # player_i == seat i
        self._obs_space = spaces.Dict({
            "observation": spaces.Box(0.0, 10.0, (OBS_DIM,), dtype=np.float32),
            "action_mask": spaces.Box(0, 1, (N_ACTIONS,), dtype=np.int8),
        })
        self._act_space = spaces.Discrete(N_ACTIONS)
        self._rng = random.Random(seed)
        self.hand: HandSession | None = None

    def observation_space(self, agent):
        return self._obs_space

    def action_space(self, agent):
        return self._act_space

    def _seat(self, agent: str) -> int:
        return self.possible_agents.index(agent)

    def _agent(self, seat: int) -> str:
        return self.possible_agents[seat]

    def _other(self, agent: str) -> str:
        return self.possible_agents[1 - self._seat(agent)]

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        self.agents = self.possible_agents[:]
        self.rewards = {a: 0.0 for a in self.agents}
        self._cumulative_rewards = {a: 0.0 for a in self.agents}
        self.terminations = {a: False for a in self.agents}
        self.truncations = {a: False for a in self.agents}
        self.infos = {a: {} for a in self.agents}
        self._skip_agent_selection = None
        self.hand = HandSession([0, 1], [self.starting_stack] * 2, self.sb, self.bb, self._rng)
        self.agent_selection = self._agent(self.hand.actor_seat())

    def observe(self, agent: str):
        seat = self._seat(agent)
        if self.hand is not None and not self.hand.done and self.hand.actor_seat() == seat:
            o = self.hand.observation()
            return {"observation": encode_obs(o), "action_mask": legal_mask(o).astype(np.int8)}
        # not this agent's turn — well-formed but empty
        return {"observation": np.zeros(OBS_DIM, np.float32),
                "action_mask": np.zeros(N_ACTIONS, np.int8)}

    def step(self, action):
        agent = self.agent_selection
        if self.terminations[agent] or self.truncations[agent]:
            self._was_dead_step(action)               # action must be None
            return

        self._cumulative_rewards[agent] = 0
        o = self.hand.observation()
        self.hand.apply(decode_action(int(action), o))
        for a in self.agents:
            self.rewards[a] = 0.0

        if self.hand.done:
            payoffs = self.hand.payoffs()             # {player_id/seat: net_chips}
            for a in self.agents:
                self.rewards[a] = payoffs.get(self._seat(a), 0) / self.starting_stack
                self.terminations[a] = True
            self.agent_selection = self._other(agent)  # let both agents dead-step
        else:
            self.agent_selection = self._agent(self.hand.actor_seat())

        self._accumulate_rewards()

    def render(self):
        return None

    def close(self):
        pass
