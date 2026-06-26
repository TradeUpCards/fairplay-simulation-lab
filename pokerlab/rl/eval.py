"""Evaluate a trained checkpoint: play N hands vs an opponent and report bb/100 and
win-rate, against a random-action baseline so the learning is legible.

    python -m pokerlab.rl.eval --checkpoint pokerlab/rl/checkpoints/regular.pt \
        --opponent regular --hands 3000
"""
from __future__ import annotations

import argparse

import numpy as np
import torch

from .encode import N_ACTIONS
from .env import HeadsUpPokerEnv
from .model import ActorCritic


def _load(checkpoint: str, device: str):
    ckpt = torch.load(checkpoint, map_location=device)
    m = ActorCritic(ckpt["obs_dim"], ckpt["n_actions"], ckpt["hidden"]).to(device)
    m.load_state_dict(ckpt["model"])
    m.eval()
    return m


def _eval(pick, opponent: str, hands: int, seed: int) -> dict:
    env = HeadsUpPokerEnv(opponent=opponent, seed=seed, opp_equity_samples=20)
    obs, info = env.reset(seed=seed)
    nets: list[float] = []
    guard = 0
    while len(nets) < hands and guard < hands * 200:
        guard += 1
        a = pick(obs, info)
        obs, r, done, trunc, info = env.step(a)
        if done:
            nets.append(info["net_chips"])
            obs, info = env.reset()
    arr = np.asarray(nets, dtype=np.float64)
    bb = env.bb
    bb_per_hand = arr / bb
    n = len(arr)
    ci = 1.96 * bb_per_hand.std(ddof=1) / np.sqrt(n) * 100 if n > 1 else 0.0
    return {
        "hands": n,
        "bb_per_100": float(bb_per_hand.mean() * 100),
        "ci95": float(ci),
        "win_rate": float((arr > 0).mean()),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--opponent", default="regular")
    p.add_argument("--hands", type=int, default=3000)
    p.add_argument("--seed", type=int, default=12345)
    args = p.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = _load(args.checkpoint, device)
    rng = np.random.default_rng(args.seed)

    def trained(obs, _info):
        x = torch.as_tensor(obs, dtype=torch.float32, device=device).unsqueeze(0)
        with torch.no_grad():
            return int(model.logits(x).argmax(dim=-1).item())

    def random_pick(_obs, info):
        mask = info.get("action_mask")
        choices = np.flatnonzero(mask > 0) if mask is not None else np.arange(N_ACTIONS)
        return int(rng.choice(choices)) if choices.size else 1

    t = _eval(trained, args.opponent, args.hands, args.seed)
    b = _eval(random_pick, args.opponent, args.hands, args.seed)
    print(f"vs {args.opponent}  ({t['hands']} hands)")
    print(f"  trained : {t['bb_per_100']:+.1f} bb/100  (±{t['ci95']:.1f})  win {t['win_rate']:.1%}")
    print(f"  random  : {b['bb_per_100']:+.1f} bb/100  (±{b['ci95']:.1f})  win {b['win_rate']:.1%}")
    edge = t["bb_per_100"] - b["bb_per_100"]
    print(f"  learned edge over random: {edge:+.1f} bb/100")


if __name__ == "__main__":
    main()
