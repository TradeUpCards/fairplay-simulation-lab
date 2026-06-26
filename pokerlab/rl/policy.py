"""RLPolicyAgent — a trained PPO checkpoint behind the standard act(obs, rng) seam,
so the learned bot is interchangeable with the heuristic ArchetypeAgents in the
game and the env. Decides from the Observation alone (no engine internals)."""
from __future__ import annotations

import random

import torch

from playsim.agent import Decision, Observation

from .encode import N_ACTIONS, OBS_DIM, decode_action, encode_obs
from .model import ActorCritic


class RLPolicyAgent:
    agent_model = "ppo"
    agent_version = "v1"

    def __init__(self, player_id: int, checkpoint: str, device: str = "cpu",
                 deterministic: bool = False, base_latency_ms: int = 900):
        self.player_id = player_id
        self.device = device
        self.deterministic = deterministic
        self.base_latency_ms = base_latency_ms
        ckpt = torch.load(checkpoint, map_location=device)
        self.model = ActorCritic(ckpt.get("obs_dim", OBS_DIM),
                                 ckpt.get("n_actions", N_ACTIONS),
                                 ckpt.get("hidden", 128))
        self.model.load_state_dict(ckpt["model"])
        self.model.to(device).eval()

    @torch.no_grad()
    def act(self, obs: Observation, rng: random.Random) -> Decision:
        x = torch.as_tensor(encode_obs(obs), dtype=torch.float32, device=self.device).unsqueeze(0)
        logits = self.model.logits(x)
        if self.deterministic:
            a = int(logits.argmax(dim=-1).item())
        else:
            a = int(torch.distributions.Categorical(logits=logits).sample().item())
        d = decode_action(a, obs)
        d.latency_ms = self.base_latency_ms
        return d
