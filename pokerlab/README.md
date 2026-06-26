# pokerlab — AI Poker Training Lab

A **standalone** web game where a human plays heads-up No-Limit Hold'em against
configurable AI bots — "an AI poker lab where the agents become opponents you can
train against." It **depends on, but never edits,** the sibling `playsim` package
for the PokerKit-backed archetype bots and the `Observation`/`Decision` seam.

> Capstone/AI-demo track. Shares the FairPlay *engine + design language*, not its
> product thesis.

## Architecture

```
Human (web UI)  ─┐
Heuristic bot    ─┼─► one act(obs) seam ─► HandSession (steppable, over PokerKit)
RL-trained bot   ─┘                         │
                                            ▼
            GameSession (persistent stacks, button rotation, pauses for the human)
                                            │
                          FastAPI turn-by-turn API  ◄──►  Vite/React/Tailwind UI
```

- `pokerlab/engine/` — `HandSession` (a *steppable* version of `playsim.table.play_hand`
  that pauses for a human), `GameSession` (multi-hand driver), `agents.py` (the heuristic
  roster: Rock, Calling Station, Maniac, Grinder, Solver-Like), `roster.py` (merges those
  with any **trained RL checkpoints** discovered on disk — torch loaded lazily).
- `pokerlab/server/` — FastAPI: `/api/styles`, `/api/games`, `/api/games/{id}/action`,
  `/api/games/{id}/next`.
- `pokerlab/web/` — the game UI (matches the FairPlay theme tokens).
- `pokerlab/rl/` — Track A: a Gymnasium env over the PokerKit engine + CleanRL-style PPO
  → an `RLPolicyAgent` that slots into the *same* `act(obs)` seam as the heuristic bots.
  Also a PettingZoo **AEC** env (`pettingzoo_env.py`) + **self-play** trainer
  (`train_selfplay.py`) — both seats are agents; the policy learns vs frozen past selves.

## Run it

**Backend** (from the repo/worktree root, so `pokerlab` and `playsim` import):

```powershell
python -m venv .venv-pokerlab
.\.venv-pokerlab\Scripts\Activate.ps1
pip install -r pokerlab/requirements.txt
pip install -e playsim                       # the bots/seam (editable, not modified)
uvicorn pokerlab.server.app:app --reload --port 8000
```

**Frontend** (separate terminal):

```powershell
cd pokerlab/web
npm install
npm run dev                                  # http://localhost:5173  (proxies /api → :8000)
```

Open http://localhost:5173, pick an opponent, and play. The bot acts instantly; the
table pauses on your turn for fold / check-call / raise (slider + ½-pot / pot / all-in).

## Train a bot, then play it (Track A)

Install the RL deps (heavier; CPU torch is enough), train a policy with PPO, and it
shows up in the opponent picker tagged **Trained · PPO** — "play the bot you trained."

```powershell
pip install -r pokerlab/requirements-rl.txt          # numpy, gymnasium, torch
# (smaller torch: pip install torch --index-url https://download.pytorch.org/whl/cpu)

# from the worktree root, with playsim importable:
$env:PYTHONPATH = "$PWD;$PWD/playsim"

# quick smoke (seconds) — proves the pipeline end to end
python -m pokerlab.rl.train --opponent rock --total-timesteps 2048 --num-envs 4 `
    --num-steps 32 --opp-equity-samples 4 --out pokerlab/rl/checkpoints/smoke.pt
python -m pokerlab.rl.eval --checkpoint pokerlab/rl/checkpoints/smoke.pt --opponent rock --hands 300

# a real bot (minutes on CPU)
python -m pokerlab.rl.train --opponent solver --total-timesteps 400000 --num-envs 8 `
    --out pokerlab/rl/checkpoints/solver_buster.pt
```

Checkpoints land in `pokerlab/rl/checkpoints/*.pt`; **restart the server** and each one
appears as a selectable opponent (key `rl:<filename>`). Nothing else to wire.

### Self-play (a genuinely strong bot)

Instead of training against one fixed heuristic, train against **frozen snapshots of
your own past selves** over the PettingZoo **AEC** env. The opponent keeps improving as
the learner does, so the bot doesn't just exploit one style — it gets *good*:

```powershell
python -m pokerlab.rl.train_selfplay --total-timesteps 400000 --num-steps 1024 `
    --snapshot-every 20 --pool-size 5 --out pokerlab/rl/checkpoints/selfplay.pt
python -m pokerlab.rl.eval --checkpoint pokerlab/rl/checkpoints/selfplay.pt --opponent solver --hands 3000
```

Same checkpoint format, so `rl:selfplay` shows up in the picker like any other trained
bot. (A few-thousand-step smoke is weak by design — give it the full run for strength.)

## Optional: LLM "coach's take"

Layer a plain-English narration *over* the deterministic EV numbers. Fully gated — off
unless both the SDK and a key are present; the deterministic coach always works regardless.

```powershell
pip install anthropic
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:POKERLAB_NARRATOR_MODEL = "claude-haiku-4-5-20251001"   # optional (default)
# restart uvicorn — a "Coach's take" button appears under each hand review
```

The narrator is *fed* the computed equity/pot-odds/EV and asked to explain them; it never
invents analysis. Each press is one small billed API call.

## Tests (backend)

```powershell
# from the worktree root, with playsim importable
$env:PYTHONPATH = "$PWD;$PWD/playsim"
python pokerlab/tests/test_engine_smoke.py
python pokerlab/tests/test_server.py
```

## Status

- ✅ Steppable engine + human-aware game session (smoke test green)
- ✅ Turn-by-turn FastAPI server (smoke test green)
- ✅ Web game UI (Vite + React 19 + TS + Tailwind v4, FairPlay theme)
- ✅ Track A — RL bot: Gymnasium env over PokerKit + PPO trainer + eval (env smoke green)
- ✅ Trained bots wired into the roster as selectable opponents (test green)
- ✅ Post-hand coaching — deterministic EV/equity review per decision (tests green)
- ✅ Self-play — PettingZoo AEC env (api_test green) + PPO vs a frozen opponent pool
- ✅ Difficulty tiers (Beginner→Expert + Trained), hand-history replay & session stats
- ✅ Optional LLM "coach's take" narrator over the EV numbers (gated on an API key)
