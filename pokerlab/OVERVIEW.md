# pokerlab — Project Overview

> **AI Poker Lab** — a web game where a human plays heads-up No-Limit Hold'em against
> configurable AI opponents (including a bot you train yourself with reinforcement
> learning) and gets coached on every decision. *"The agents become opponents you can
> train against."*

This is the shareable overview: what we're building, how it fits together, the phases we
went through, and step-by-step instructions to run it. For the live task checklist see
[PLAN.md](PLAN.md); for terse run commands see [README.md](README.md).

---

## 1. What we're building

A standalone learning lab around poker, on three pillars:

1. **Play** — a human plays heads-up NLHE in the browser against a roster of bots, from
   exploitable table characters to a neural net trained by self-play.
2. **Train** — anyone can train a bot with PPO (against a fixed style, or via self-play
   against past versions of itself) and that checkpoint becomes a selectable opponent.
3. **Learn** — after every hand, a deterministic engine grades each decision on
   pot-odds-vs-equity (with an optional LLM "coach's take" in plain English), and a
   session review tracks your progress.

**The unifying idea.** A human, a hand-tuned heuristic bot, and a trained neural net all
sit behind **one interface** — `act(observation) -> decision`. Because of that, the exact
same PokerKit engine powers *both* training and play: a bot trained in the RL environment
drops straight into the live game with no glue, no adapter, no behavioural mismatch.

**Scope & boundaries (important for the team):**

- `pokerlab/` is a **standalone** top-level project. It **depends on, but never edits,**
  the sibling `playsim` package (we reuse its bots, its `Observation`/`Decision` seam, and
  its equity math).
- It deliberately matches the FairPlay design language (same Vite + React + Tailwind stack
  and theme tokens) so it looks native to the family.
- It's the **capstone / AI-demo track** — it shares FairPlay's engine and look, not its
  product thesis.
- Work lives on branch **`feat/ai-poker-lab`**. Nothing is committed or merged without an
  explicit ask.

---

## 2. How it works (architecture)

```
Human (web UI)  ─┐
Heuristic bot    ─┼─► act(obs) seam ─► HandSession (steppable, over PokerKit)
RL / self-play   ─┘                     │
                                        ▼
        GameSession (persistent stacks, button rotation, pauses for the human,
                     skips "walk" hands, records history + session stats)
                                        │
        FastAPI turn API  ◄────────────►  Vite/React/Tailwind UI
                │                          (table, action bar, difficulty-tiered
                ├─ deterministic EV/equity coach ─► Hand-review panel
                └─ optional LLM narrator (gated)  ─► "Coach's take"
```

| Area | What's in it |
|------|--------------|
| `engine/` | `HandSession` (a *steppable* hand that pauses for a human), `GameSession` (multi-hand driver: stacks, button, walk-skipping, history/stats), `agents.py` (heuristic roster), `roster.py` (merges heuristics + discovered RL checkpoints; torch loaded lazily) |
| `rl/` | `encode` (obs↔action seam), `env` (Gymnasium env), `model` (Actor-Critic), `train` (PPO vs a fixed style), `eval`, `policy` (`RLPolicyAgent`), `pettingzoo_env` (AEC multi-agent env), `train_selfplay` (self-play PPO) |
| `coach/` | `coach.py` (deterministic EV/equity grading) + `narrator.py` (optional, gated LLM narration) |
| `server/` | FastAPI turn-by-turn API |
| `web/` | the game UI |

---

## 3. The phases (how we got here)

- **Phase 1 — Game spine.** Steppable engine, human-aware game session, heuristic bot
  roster (Rock, Calling Station, Maniac, Grinder, Solver-Like), turn-by-turn API, and the
  web game UI on the FairPlay theme.
- **Phase 2 — Track A: the RL bot.** Obs/action encoding, a Gymnasium env over the engine,
  Actor-Critic + PPO trainer + eval, and an `RLPolicyAgent` that plugs into the same seam.
  Trained checkpoints are auto-discovered and become selectable opponents.
- **Phase 3 — Coaching.** Deterministic per-decision EV/equity review (pot-odds vs
  Monte-Carlo equity), graded on the information available at decision time (the
  opponent's actual cards are shown as clearly-labelled hindsight, never used to judge).
- **Phase 4 — Polish / stretch.**
  - **Self-play** over a real PettingZoo **AEC** env: one policy learns both seats against
    a frozen pool of its past selves.
  - **Difficulty tiers** — opponents grouped Beginner→Expert (heuristics) / Trained (RL).
  - **Hand-history replay + session stats** — review any past hand; live scoreboard.
  - **Optional LLM narrator** — a grounded "coach's take" over the EV numbers (gated).

A notable fix along the way: in heads-up you're the big blind half the time, and tight
bots open-fold the small blind, ending the hand before you act. The game now **skips these
"walk" hands** so you always land on a hand you can actually play.

---

## 4. Getting started (instructions)

**Prerequisites:** Python 3.12, Node 18+, git. Commands below run from the **repo root**
(the folder that contains both `pokerlab/` and `playsim/`), on branch `feat/ai-poker-lab`.

### 4a. Backend (the game)

```bash
python -m venv .venv-pokerlab
# activate it:
#   Windows PowerShell:  .\.venv-pokerlab\Scripts\Activate.ps1
#   macOS/Linux:         source .venv-pokerlab/bin/activate
pip install -r pokerlab/requirements.txt
pip install -e playsim                      # the shared bots/seam (editable, not modified)
uvicorn pokerlab.server.app:app --reload --port 8000
```

> Running from source (not installed)? Make sure `pokerlab` and `playsim` are importable.
> If needed, set `PYTHONPATH` to the repo root **and** `<repo-root>/playsim`:
> PowerShell `$env:PYTHONPATH = "$PWD;$PWD\playsim"` · bash `export PYTHONPATH="$PWD:$PWD/playsim"`.

### 4b. Frontend (separate terminal)

```bash
cd pokerlab/web
npm install
npm run dev        # http://localhost:5173  (proxies /api → :8000)
```

Open **http://localhost:5173**, pick an opponent (grouped by difficulty), and play. The bot
acts instantly; the table pauses on your turn for **fold / check-call / raise** (slider +
½-pot / pot / all-in). When a hand ends you get a **Hand review** (EV per decision);
**Session review** (top-right) lists every hand you've played; the scoreboard tracks
hands, net bb, bb/100, record, and EV left on the table.

> After changing backend Python, restart `uvicorn`. The frontend hot-reloads on its own.
> New trained checkpoints are picked up live (the picker rescans on each load — no restart).

---

## 5. Training your own bots (instructions)

Install the heavier RL dependencies once (CPU PyTorch is enough):

```bash
pip install -r pokerlab/requirements-rl.txt
# smaller torch download: pip install torch --index-url https://download.pytorch.org/whl/cpu
# (set PYTHONPATH as in 4a if running from source)
```

**Against a fixed style** (fast to see learning — it exploits the style's leak):

```bash
# tiny smoke (seconds) — proves the pipeline
python -m pokerlab.rl.train --opponent rock --total-timesteps 2048 --num-envs 4 \
    --num-steps 32 --opp-equity-samples 4 --out pokerlab/rl/checkpoints/smoke.pt
python -m pokerlab.rl.eval --checkpoint pokerlab/rl/checkpoints/smoke.pt --opponent rock --hands 300

# a real bot (minutes on CPU)
python -m pokerlab.rl.train --opponent solver --total-timesteps 400000 --num-envs 8 \
    --out pokerlab/rl/checkpoints/solver_buster.pt
```

**Self-play** (a genuinely strong, non-style-specific bot — learns vs frozen past selves):

```bash
python -m pokerlab.rl.train_selfplay --total-timesteps 400000 --num-steps 1024 \
    --snapshot-every 20 --pool-size 5 --out pokerlab/rl/checkpoints/selfplay.pt
python -m pokerlab.rl.eval --checkpoint pokerlab/rl/checkpoints/selfplay.pt --opponent solver --hands 3000
```

Checkpoints land in `pokerlab/rl/checkpoints/*.pt` and appear in the opponent picker under
**Trained** as `rl:<filename>`. (A few-thousand-step smoke is weak by design — give it the
full run for strength.)

---

## 6. Optional: the LLM "coach's take" (instructions)

Off by default. When enabled, it's *fed* the deterministic EV/equity numbers and asked to
explain them in 2-3 plain-English sentences — it never invents analysis, and the
deterministic coach works with or without it.

```bash
pip install anthropic
# set your key:
#   PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-..."
#   bash:        export ANTHROPIC_API_KEY="sk-ant-..."
# optional model override (default shown):
#   POKERLAB_NARRATOR_MODEL = claude-haiku-4-5-20251001
# restart uvicorn
```

A **"Coach's take"** button then appears under each hand review. Each press is one small,
billed API call (~a few hundred tokens). No key → the button simply doesn't show.

---

## 7. Tests

```bash
# from the repo root, with PYTHONPATH set (see 4a), on the venv that has the RL deps
python -m pytest pokerlab/tests        # 26 passed
```

Coverage spans the engine, the FastAPI server, the RL env + encoding, **PettingZoo AEC
conformance** (PettingZoo's own `api_test`), the self-play trainer, the EV/equity coach
(including forced-mistake scenarios + determinism), session/history tracking, the
walk-skip regression, and the narrator's gated-off behavior. RL/MARL tests skip
automatically if torch/pettingzoo aren't installed, so the game-spine tests run anywhere.

---

## 8. Project layout

```
pokerlab/
  engine/    game + roster (HandSession, GameSession, agents, roster)
  rl/        RL stack (encode, env, model, train, eval, policy,
             pettingzoo_env, train_selfplay) + checkpoints/
  coach/     coach.py (deterministic EV/equity) + narrator.py (optional LLM)
  server/    FastAPI app
  web/       Vite + React + TS + Tailwind UI
  tests/     pytest suite
  README.md  run commands · PLAN.md  checklist · OVERVIEW.md  this file
```

---

## 9. Status & notes for the team

- **All phases are built and the backend test suite is green (26 passed).**
- Open items are operational, not code: run a full training / self-play run for a strong
  bot, and do a browser pass to sign off on UI polish.
- **Don't edit `playsim`** — depend on it. **Don't commit/merge** without an explicit ask.
  Branch is `feat/ai-poker-lab`.
- The game spine runs with no RL deps; torch/pettingzoo are only needed to *train*. The
  LLM narrator is fully optional and isolated behind a key check.
