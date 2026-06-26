"""PettingZoo AEC env + self-play PPO. The AEC env is conformance-tested with
PettingZoo's own api_test; the trainer runs a tiny self-play loop and the resulting
checkpoint must load behind the standard act() seam. All guarded so the game spine
stays testable without the RL/MARL deps."""
from __future__ import annotations

import argparse
import random

import numpy as np
import pytest


def test_aec_api_conformance():
    pytest.importorskip("pettingzoo")
    from pettingzoo.test import api_test

    from pokerlab.rl.pettingzoo_env import env
    api_test(env(seed=0), num_cycles=100)


def test_aec_is_zero_sum():
    pytest.importorskip("pettingzoo")
    from pokerlab.rl.pettingzoo_env import env

    e = env(seed=1)
    rng = np.random.default_rng(0)
    for _ in range(30):
        e.reset()
        rewards = {}
        while e.agents:
            agent = e.agent_selection
            obs, rew, term, trunc, info = e.last()
            if term or trunc:
                rewards[agent] = rew
                e.step(None)
            else:
                legal = np.flatnonzero(obs["action_mask"])
                e.step(int(rng.choice(legal)) if legal.size else 0)
        assert abs(sum(rewards.values())) < 1e-9


def test_selfplay_trains_and_checkpoint_plays(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("pettingzoo")
    from pokerlab.engine.game import HandSession
    from pokerlab.rl.policy import RLPolicyAgent
    from pokerlab.rl.train_selfplay import train

    out = tmp_path / "selfplay.pt"
    args = argparse.Namespace(
        total_timesteps=512, num_steps=128, lr=2.5e-4, gamma=0.99, gae_lambda=0.95,
        update_epochs=2, num_minibatches=4, clip_coef=0.2, ent_coef=0.01, vf_coef=0.5,
        max_grad_norm=0.5, hidden=64, snapshot_every=2, pool_size=3, seed=1, out=str(out))
    train(args)
    assert out.exists()

    # the self-play checkpoint loads behind the act(obs) seam and makes a legal move
    h = HandSession([0, 1], [200, 200], 1, 2, random.Random(0))
    agent = RLPolicyAgent(0, str(out))
    d = agent.act(h.observation(), random.Random(0))
    assert d.kind in ("fold", "check_call", "raise")
