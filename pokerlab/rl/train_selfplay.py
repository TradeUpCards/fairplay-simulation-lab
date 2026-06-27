"""Self-play PPO over the PettingZoo AEC poker env.

One shared policy learns to beat **frozen snapshots of its own past selves** (an
opponent pool), alternating seats each hand so it learns both positions. Unlike
``train.py`` (learner vs one fixed heuristic), the opponent here keeps getting
stronger as the learner does — the standard, stable form of self-play (frozen
opponents avoid the instability of chasing a live mirror).

The checkpoint is saved in the same format as ``train.py``, so it auto-discovers
in the game roster as ``rl:<name>`` and is immediately playable.

    python -m pokerlab.rl.train_selfplay --total-timesteps 300000 \
        --snapshot-every 20 --out pokerlab/rl/checkpoints/selfplay.pt
"""
from __future__ import annotations

import argparse
import copy
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from .encode import N_ACTIONS, OBS_DIM
from .model import ActorCritic
from .pettingzoo_env import raw_env


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--total-timesteps", type=int, default=300_000)
    p.add_argument("--num-steps", type=int, default=1024, help="learner transitions per update")
    p.add_argument("--lr", type=float, default=2.5e-4)
    p.add_argument("--gamma", type=float, default=0.99)
    p.add_argument("--gae-lambda", type=float, default=0.95)
    p.add_argument("--update-epochs", type=int, default=4)
    p.add_argument("--num-minibatches", type=int, default=4)
    p.add_argument("--clip-coef", type=float, default=0.2)
    p.add_argument("--ent-coef", type=float, default=0.01)
    p.add_argument("--vf-coef", type=float, default=0.5)
    p.add_argument("--max-grad-norm", type=float, default=0.5)
    p.add_argument("--hidden", type=int, default=128)
    p.add_argument("--snapshot-every", type=int, default=20, help="updates between adding a snapshot")
    p.add_argument("--pool-size", type=int, default=5, help="most-recent snapshots kept as opponents")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", default="pokerlab/rl/checkpoints/selfplay.pt")
    return p.parse_args()


@torch.no_grad()
def _sample(net, obs_vec, device) -> int:
    x = torch.as_tensor(obs_vec, dtype=torch.float32, device=device).unsqueeze(0)
    return int(torch.distributions.Categorical(logits=net.logits(x)).sample().item())


def collect(env, agent, opp, pool, n_steps, py_rng, device):
    """Run whole hands until >= n_steps learner transitions are buffered. Reward is
    terminal-only, stamped (with done=1) on the learner's last decision each hand."""
    obs_l, act_l, logp_l, val_l, rew_l, done_l = [], [], [], [], [], []
    while len(obs_l) < n_steps:
        env.reset()
        learner = "player_0" if py_rng.random() < 0.5 else "player_1"
        opp.load_state_dict(py_rng.choice(pool))
        idxs, term_reward = [], 0.0
        while env.agents:
            cur = env.agent_selection
            obs, rew, term, trunc, info = env.last()
            if term or trunc:
                if cur == learner:
                    term_reward = rew
                env.step(None)
                continue
            v = obs["observation"]
            if cur == learner:
                x = torch.as_tensor(v, dtype=torch.float32, device=device).unsqueeze(0)
                with torch.no_grad():
                    a, logp, _, value = agent.get_action_and_value(x)
                obs_l.append(v); act_l.append(int(a.item())); logp_l.append(float(logp.item()))
                val_l.append(float(value.item())); rew_l.append(0.0); done_l.append(0.0)
                idxs.append(len(obs_l) - 1)
                env.step(int(a.item()))
            else:
                env.step(_sample(opp, v, device))
        if idxs:
            rew_l[idxs[-1]] = term_reward
            done_l[idxs[-1]] = 1.0
    return (np.asarray(obs_l, np.float32), np.asarray(act_l), np.asarray(logp_l, np.float32),
            np.asarray(val_l, np.float32), np.asarray(rew_l, np.float32), np.asarray(done_l, np.float32))


def train(args):
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    py_rng = random.Random(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    env = raw_env(seed=args.seed)
    agent = ActorCritic(OBS_DIM, N_ACTIONS, args.hidden).to(device)
    opp = ActorCritic(OBS_DIM, N_ACTIONS, args.hidden).to(device).eval()
    opt = torch.optim.Adam(agent.parameters(), lr=args.lr, eps=1e-5)

    pool = [copy.deepcopy(agent.state_dict())]      # start by beating your initial self
    num_updates = max(1, args.total_timesteps // args.num_steps)
    start, global_step, recent = time.time(), 0, []

    for update in range(1, num_updates + 1):
        obs, act, logp, val, rew, done = collect(
            env, agent, opp, pool, args.num_steps, py_rng, device)
        global_step += len(obs)
        recent.extend(rew[done > 0.5].tolist())

        b_obs = torch.as_tensor(obs, device=device)
        b_act = torch.as_tensor(act, dtype=torch.long, device=device)
        b_logp = torch.as_tensor(logp, device=device)
        b_val = torch.as_tensor(val, device=device)
        b_rew = torch.as_tensor(rew, device=device)
        b_done = torch.as_tensor(done, device=device)
        N = len(obs)

        # GAE over the flat buffer (episodes delimited by done=1)
        adv = torch.zeros(N, device=device)
        last = torch.zeros((), device=device)
        for t in reversed(range(N)):
            nonterm = 1.0 - b_done[t]
            nextval = b_val[t + 1] if t + 1 < N else torch.zeros((), device=device)
            delta = b_rew[t] + args.gamma * nextval * nonterm - b_val[t]
            last = delta + args.gamma * args.gae_lambda * nonterm * last
            adv[t] = last
        ret = adv + b_val

        idx = np.arange(N)
        mb = max(1, N // args.num_minibatches)
        for _ in range(args.update_epochs):
            np.random.shuffle(idx)
            for s in range(0, N, mb):
                m = idx[s:s + mb]
                if len(m) < 2:                       # a size-1 minibatch makes std() NaN
                    continue
                _, nlp, ent, nv = agent.get_action_and_value(b_obs[m], b_act[m])
                ratio = (nlp - b_logp[m]).exp()
                a = adv[m]
                a = (a - a.mean()) / (a.std() + 1e-8)
                pg = torch.max(-a * ratio,
                               -a * torch.clamp(ratio, 1 - args.clip_coef, 1 + args.clip_coef)).mean()
                vl = 0.5 * ((nv.flatten() - ret[m]) ** 2).mean()
                loss = pg - args.ent_coef * ent.mean() + args.vf_coef * vl
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(agent.parameters(), args.max_grad_norm)
                opt.step()

        if update % args.snapshot_every == 0:
            pool.append(copy.deepcopy(agent.state_dict()))
            if len(pool) > args.pool_size:
                pool.pop(0)

        if update % 10 == 0 or update == num_updates:
            avg = float(np.mean(recent[-500:])) if recent else 0.0
            sps = int(global_step / (time.time() - start))
            print(f"upd {update}/{num_updates} · step {global_step} · pool {len(pool)} · "
                  f"avg_term_reward {avg:+.3f} · {sps} steps/s", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model": agent.state_dict(), "obs_dim": OBS_DIM, "n_actions": N_ACTIONS,
                "hidden": args.hidden, "opponent": "self-play"}, out)
    print(f"saved checkpoint -> {out}", flush=True)


if __name__ == "__main__":
    train(parse_args())
