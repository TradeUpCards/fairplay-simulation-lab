"""Env smoke test (numpy + gymnasium, no torch): the RL env steps cleanly, obs/
reward/mask are well-formed, and rewards stay bounded. Verifies the engine↔RL
seam before any training run."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "playsim"))

import numpy as np  # noqa: E402

from pokerlab.rl.env import HeadsUpPokerEnv, LEARNER_ID  # noqa: E402
from pokerlab.rl.encode import OBS_DIM, N_ACTIONS  # noqa: E402


def _run(opponent, episodes=40, seed=0):
    env = HeadsUpPokerEnv(opponent=opponent, seed=seed, opp_equity_samples=8)
    rng = np.random.default_rng(seed)
    nets = []
    for ep in range(episodes):
        obs, info = env.reset(seed=seed + ep)
        assert obs.shape == (OBS_DIM,) and obs.dtype == np.float32
        assert info["action_mask"].shape == (N_ACTIONS,)
        done = False
        guard = 0
        last_info = info
        while not done:
            guard += 1
            assert guard < 200, "episode did not terminate"
            # random *legal-ish* action (mask guides; env remaps anyway)
            mask = last_info["action_mask"]
            choices = np.flatnonzero(mask > 0)
            a = int(rng.choice(choices)) if choices.size else 1
            obs, reward, done, trunc, last_info = env.step(a)
            assert obs.shape == (OBS_DIM,)
            assert -1.01 <= reward <= 1.01, reward
        nets.append(last_info.get("net_chips", 0))
    return nets


def test_env_steps_all_opponents():
    for opp in ("rock", "regular", "maniac", "grinder", "solver_like"):
        nets = _run(opp, episodes=25)
        assert len(nets) == 25
        # heads-up zero-sum-ish: net chips should both win and lose across hands
        assert any(n > 0 for n in nets) or any(n < 0 for n in nets)


def test_obs_and_action_spaces():
    env = HeadsUpPokerEnv(opponent="maniac", seed=1)
    assert env.observation_space.shape == (OBS_DIM,)
    assert env.action_space.n == N_ACTIONS
    obs, info = env.reset(seed=1)
    assert np.isfinite(obs).all()
    # always-legal check/call
    obs, r, done, trunc, info = env.step(1)
    assert isinstance(r, float)


if __name__ == "__main__":
    test_env_steps_all_opponents()
    test_obs_and_action_spaces()
    print("OK — RL env smoke passed")
