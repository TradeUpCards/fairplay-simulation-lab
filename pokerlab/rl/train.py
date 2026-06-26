"""PPO trainer for the heads-up poker bot (CleanRL-style, PyTorch).

Trains a policy in HeadsUpPokerEnv (one learner vs a fixed heuristic opponent) and
saves a checkpoint that RLPolicyAgent / the game load directly. Parallel envs are
managed manually (reset-on-done) since each episode is a single hand.

    python -m pokerlab.rl.train --opponent regular --total-timesteps 300000 \
        --num-envs 8 --out pokerlab/rl/checkpoints/regular.pt
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from .encode import N_ACTIONS, OBS_DIM
from .env import HeadsUpPokerEnv
from .model import ActorCritic


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--opponent", default="regular", help="bot style or playsim archetype")
    p.add_argument("--total-timesteps", type=int, default=300_000)
    p.add_argument("--num-envs", type=int, default=8)
    p.add_argument("--num-steps", type=int, default=128)
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
    p.add_argument("--opp-equity-samples", type=int, default=12)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", default="pokerlab/rl/checkpoints/bot.pt")
    return p.parse_args()


def train(args):
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    envs = [HeadsUpPokerEnv(opponent=args.opponent, seed=args.seed + i,
                            opp_equity_samples=args.opp_equity_samples)
            for i in range(args.num_envs)]
    n = args.num_envs
    cur_obs = np.stack([e.reset(seed=args.seed + i)[0] for i, e in enumerate(envs)])

    agent = ActorCritic(OBS_DIM, N_ACTIONS, args.hidden).to(device)
    opt = torch.optim.Adam(agent.parameters(), lr=args.lr, eps=1e-5)

    S = args.num_steps
    obs_buf = torch.zeros((S, n, OBS_DIM), device=device)
    act_buf = torch.zeros((S, n), dtype=torch.long, device=device)
    logp_buf = torch.zeros((S, n), device=device)
    rew_buf = torch.zeros((S, n), device=device)
    done_buf = torch.zeros((S, n), device=device)
    val_buf = torch.zeros((S, n), device=device)

    batch_size = n * S
    mb_size = batch_size // args.num_minibatches
    num_updates = args.total_timesteps // batch_size
    ep_returns: list[float] = []
    global_step = 0
    start = time.time()

    for update in range(1, num_updates + 1):
        for step in range(S):
            global_step += n
            obs_t = torch.as_tensor(cur_obs, dtype=torch.float32, device=device)
            with torch.no_grad():
                action, logp, _, value = agent.get_action_and_value(obs_t)
            obs_buf[step] = obs_t
            act_buf[step] = action
            logp_buf[step] = logp
            val_buf[step] = value.flatten()

            next_obs = np.empty_like(cur_obs)
            rewards = np.zeros(n, dtype=np.float32)
            dones = np.zeros(n, dtype=np.float32)
            acts = action.cpu().numpy()
            for i, e in enumerate(envs):
                o, r, term, trunc, info = e.step(int(acts[i]))
                rewards[i] = r
                if term or trunc:
                    dones[i] = 1.0
                    ep_returns.append(r)
                    o, _ = e.reset()
                next_obs[i] = o
            rew_buf[step] = torch.as_tensor(rewards, device=device)
            done_buf[step] = torch.as_tensor(dones, device=device)
            cur_obs = next_obs

        # GAE
        with torch.no_grad():
            next_value = agent.get_value(
                torch.as_tensor(cur_obs, dtype=torch.float32, device=device)).flatten()
            adv = torch.zeros((S, n), device=device)
            last = torch.zeros(n, device=device)
            for t in reversed(range(S)):
                nonterminal = 1.0 - done_buf[t]
                nextval = next_value if t == S - 1 else val_buf[t + 1]
                delta = rew_buf[t] + args.gamma * nextval * nonterminal - val_buf[t]
                last = delta + args.gamma * args.gae_lambda * nonterminal * last
                adv[t] = last
            returns = adv + val_buf

        b_obs = obs_buf.reshape(-1, OBS_DIM)
        b_act = act_buf.reshape(-1)
        b_logp = logp_buf.reshape(-1)
        b_adv = adv.reshape(-1)
        b_ret = returns.reshape(-1)
        b_val = val_buf.reshape(-1)

        idx = np.arange(batch_size)
        for _ in range(args.update_epochs):
            np.random.shuffle(idx)
            for s in range(0, batch_size, mb_size):
                mb = idx[s:s + mb_size]
                _, newlogp, entropy, newval = agent.get_action_and_value(b_obs[mb], b_act[mb])
                ratio = (newlogp - b_logp[mb]).exp()
                a = b_adv[mb]
                a = (a - a.mean()) / (a.std() + 1e-8)
                pg1 = -a * ratio
                pg2 = -a * torch.clamp(ratio, 1 - args.clip_coef, 1 + args.clip_coef)
                pg_loss = torch.max(pg1, pg2).mean()
                v_loss = 0.5 * ((newval.flatten() - b_ret[mb]) ** 2).mean()
                ent = entropy.mean()
                loss = pg_loss - args.ent_coef * ent + args.vf_coef * v_loss
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(agent.parameters(), args.max_grad_norm)
                opt.step()

        if update % 10 == 0 or update == num_updates:
            recent = ep_returns[-500:]
            avg = float(np.mean(recent)) if recent else 0.0
            sps = int(global_step / (time.time() - start))
            print(f"upd {update}/{num_updates} · step {global_step} · "
                  f"avg_return(bb-frac) {avg:+.3f} · {sps} steps/s", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model": agent.state_dict(), "obs_dim": OBS_DIM, "n_actions": N_ACTIONS,
                "hidden": args.hidden, "opponent": args.opponent}, out)
    print(f"saved checkpoint -> {out}", flush=True)


if __name__ == "__main__":
    train(parse_args())
