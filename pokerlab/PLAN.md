# pokerlab — Build Plan & Checklist

**What we're building:** a standalone **AI poker lab** — a web game where a human plays
heads-up No-Limit Hold'em against configurable AI opponents, *including a bot the user
trains themselves with reinforcement learning*, and gets **post-hand coaching** on every
decision. "The agents become opponents you can train against."

**Thesis / unifying idea:** every opponent — a hand-tuned heuristic character, a
PPO-trained neural net, and the human — sits behind **one `act(obs, rng) -> Decision`
seam**. That's why training and play share the *same* PokerKit engine (no adapter, no
impedance mismatch): a bot trained in the RL env drops straight into the live game.

**Boundaries (locked):**
- Standalone top-level `pokerlab/`. We **depend on `playsim`** (its bots + Observation/
  Decision seam + equity), but **never edit** playsim / backend / frontend.
- Matches the FairPlay design language (Vite + React 19 + TS + Tailwind v4, ink/brass/felt
  theme tokens) so it looks native to the family.
- Capstone / AI-demo track — shares the engine + design, not FairPlay's product thesis.
- Branch `feat/ai-poker-lab` off `origin/main`. Nothing committed/merged without the user
  asking. The user runs heavy commands / dev servers; nothing is pushed automatically.

---

## Architecture (one seam, three agent kinds)

```
Human (web UI)  ─┐
Heuristic bot    ─┼─► act(obs) seam ─► HandSession (steppable, over PokerKit)
RL-trained bot   ─┘                     │
                                        ▼
            GameSession (persistent stacks, button rotation, pauses for the human)
                                        │
                FastAPI turn API  ◄──►  Vite/React/Tailwind UI  ◄── CoachPanel (EV review)
```

- `engine/` — `HandSession` (steppable NLHE), `GameSession` (multi-hand, human-aware),
  `agents.py` (heuristic roster), `roster.py` (heuristic + discovered RL checkpoints; lazy torch).
- `rl/` — `encode` (obs↔action seam), `env` (Gymnasium env over the engine), `model`
  (Actor-Critic), `train` (PPO), `eval`, `policy` (`RLPolicyAgent` behind the act seam),
  `pettingzoo_env` (AEC multi-agent env) + `train_selfplay` (self-play PPO).
- `coach/` — deterministic EV/equity post-hand analysis (Option A) + an optional,
  gated LLM narrator (`narrator.py`).
- `server/` — FastAPI turn API. `web/` — the game UI.

---

## Checklist (where we are)

### Phase 1 — Game spine ✅ DONE
- [x] Steppable `HandSession` over PokerKit (pauses for a human turn)
- [x] Human-aware `GameSession` (stacks, button rotation, auto-plays bots)
- [x] Heuristic bot roster: Rock, Calling Station, Maniac, Grinder, Solver-Like
- [x] FastAPI turn API (`/api/styles`, `/api/games`, `…/action`, `…/next`)
- [x] Web game UI (table, action bar, style picker) on the FairPlay theme
- [x] Backend smoke tests green

### Phase 2 — Track A: RL bot (the named "Option B") ✅ DONE (training run is the user's)
- [x] Obs/action encoding seam (`encode.py`) — 116-dim obs, 5 discrete actions
- [x] Gymnasium env over PokerKit (`env.py`) — learner vs fixed opponent
- [x] Actor-Critic model + CleanRL-style PPO trainer + eval
- [x] `RLPolicyAgent` — checkpoint behind the same `act(obs)` seam
- [x] **Trained bot wired into the roster** — checkpoints auto-discovered, appear in the
      picker tagged "Trained · PPO" (lazy torch); verified end-to-end + test green
- [~] **User action:** run a real training run to produce a strong checkpoint
      (smoke proven: +875 bb/100 edge over random; a 400k-step run gives a tough bot)

### Phase 3 — Post-hand coaching (Option A: deterministic EV/equity) ✅ DONE (backend)
- [x] Per-decision analyzer: Monte-Carlo equity vs a random range + pot odds → signed
      EV leak in bb; value/bluff/thin classification on bets; hindsight "actual" equity
      kept separate from the verdict
- [x] `GameSession.coaching()` + `GET /api/games/{id}/coaching`
- [x] `CoachPanel` UI under the hand result (verdict-coded rows, villain reveal)
- [x] Coach tests green (threshold logic + forced-mistake scenarios + determinism)
- [ ] **Verify the CoachPanel in-browser** (written, not yet run — no Node in the build env)

### Phase 4 — Polish / stretch ✅ DONE
- [x] **Self-play** — PettingZoo AEC env (`pettingzoo_env.py`, passes `api_test`) +
      self-play PPO (`train_selfplay.py`): one policy learns both seats vs a frozen
      opponent pool of its past selves. Pipeline smoke-verified; tests green.
      **User action:** run a full self-play run for a strong `rl:selfplay` bot.
- [x] **Difficulty tiers** — every opponent tagged Beginner→Expert (heuristics) / Trained
      (RL); the picker groups by tier.
- [x] **Hand-history replay + session stats** — per-hand records with cached coaching,
      a "Session review" panel (expand any past hand), and a live scoreboard
      (hands, net bb, bb/100, record, EV lost).
- [x] **Optional LLM narrator** (`coach/narrator.py`) — a grounded "coach's take" over
      the EV numbers; fully gated on `ANTHROPIC_API_KEY` + the `anthropic` SDK, off by
      default. Model via `POKERLAB_NARRATOR_MODEL` (default `claude-haiku-4-5-20251001`).

---

## Run & verify

Backend, frontend, and the train→play loop: see **[README.md](README.md)**.
Backend tests (26, green): `python -m pytest pokerlab/tests` with
`PYTHONPATH = "<root>;<root>/playsim"` on the `.venv` that has pokerkit + torch + pettingzoo.

## Current position

**All phases built and backend-tested green.** The lab now: a playable HU game vs
heuristic + RL + self-play bots (grouped by difficulty), deterministic EV/equity coaching
with an optional LLM narration, hand-history replay, and live session stats.

Open items (all yours):
1. Run a full `train` / `train_selfplay` for a strong `rl:*` opponent.
2. Browser pass (`npm run dev`): play a session, check the Hand-review panel, Session
   review, the difficulty tiers, and — if you set `ANTHROPIC_API_KEY` — the Coach's take.
   Report anything off and I'll fix it.
