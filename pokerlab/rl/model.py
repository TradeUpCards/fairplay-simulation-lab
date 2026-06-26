"""Actor-Critic network shared by the PPO trainer and the inference policy, so a
checkpoint trained by train.py loads identically in RLPolicyAgent."""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from torch.distributions import Categorical


def _init(layer: nn.Linear, std: float = np.sqrt(2), bias: float = 0.0) -> nn.Linear:
    nn.init.orthogonal_(layer.weight, std)
    nn.init.constant_(layer.bias, bias)
    return layer


class ActorCritic(nn.Module):
    def __init__(self, obs_dim: int, n_actions: int, hidden: int = 128):
        super().__init__()
        self.trunk = nn.Sequential(
            _init(nn.Linear(obs_dim, hidden)), nn.Tanh(),
            _init(nn.Linear(hidden, hidden)), nn.Tanh(),
        )
        self.actor = _init(nn.Linear(hidden, n_actions), std=0.01)
        self.critic = _init(nn.Linear(hidden, 1), std=1.0)

    def get_value(self, x: torch.Tensor) -> torch.Tensor:
        return self.critic(self.trunk(x))

    def get_action_and_value(self, x: torch.Tensor, action: torch.Tensor | None = None):
        h = self.trunk(x)
        dist = Categorical(logits=self.actor(h))
        if action is None:
            action = dist.sample()
        return action, dist.log_prob(action), dist.entropy(), self.critic(h)

    def logits(self, x: torch.Tensor) -> torch.Tensor:
        return self.actor(self.trunk(x))
