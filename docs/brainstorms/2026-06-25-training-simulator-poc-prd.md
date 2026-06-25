# PRD / work-order — FairPlay Poker Training Simulator (POC)

**Date:** 2026-06-25
**For:** a new owner + their coding agent (separate track)
**From:** this checkout
**Status:** ready to pick up. Self-contained; read §0–§2 then the reuse map.

---

## 0. What this is — and what it isn't

A **single-player poker training game**: a human plays **6-max** No-Limit Hold'em
against configurable AI bots, to:

1. **Learn to play better against specific player types** (rock, maniac, calling
   station, grinder, predator, solver-like).
2. **Identify player types when they're not known up front** (a "read the table"
   mini-game).
3. **Get AI-assisted post-hand coaching** — what they could have done differently and
   *why it's better against that type*.

**It's a POC, not production.** And be clear-eyed: this is **orthogonal to FairPlay's
mission**. FairPlay is a table-health/integrity copilot; this is a *training coach* —
it reuses the same engine (PokerKit + the agent seam) and the same AI architecture,
but it is a **different product with a different user**. Pick it knowing it advances
the **capstone / AI-product demo** goal, not the FairPlay-product goal. They share an
engine, not a thesis. (Context: `docs/learn/playsim-next-simulation-ideas.md` Idea 2;
`docs/learn/demo-roadmap.html` Optional Track B.)

---

## 1. Why it's cheaper than it looks — the reuse map

Two of the three capabilities are mostly *existing engine*, and the third reuses the
AI-Investigator architecture. **Don't reinvent any of this:**

| Need | Reuse (already exists) |
|---|---|
| Deal real NLHE hands | `playsim/playsim/table.py` — PokerKit hand loop (`play_hand`), legality-enforced |
| Bot personalities | `playsim/playsim/agent.py` (`ArchetypeAgent.act`) + `knobs.py` — 10+ archetypes incl. grinder, calling-station/recreational, aggressive/predator, rock-like reg, `solver_like`, `bot_like` |
| Per-decision equity for coaching | `playsim/playsim/equity.py` — Chen percentile + Monte-Carlo equity |
| Hand records | `playsim/playsim/hand_export.py` — `hand_to_dict`, per-hand docs |
| **The coach itself** | `backend/investigator/` — structured-summary → guardrailed Claude → explanation. **The coach is the AI Investigator pointed at teaching instead of risk.** |

> **The "LLM is never the detector" rule does NOT block this.** That rule is about
> *risk detection*; an LLM *coach* is explicitly fine (it teaches, it doesn't judge a
> player for integrity). Reuse the investigator's prompt+guardrails+structured-output
> scaffolding for the coach.

So the genuinely **new** build is: the **human-play loop**, the **6-max table UI**,
and the **coach content** (assembling the structured hand summary + the coaching
prompt).

---

## 2. The three capabilities → concrete build

| Capability | Reuses | New to build |
|---|---|---|
| **1. Train vs player types** | `ArchetypeAgent` + `knobs.py` bots; `table.py` engine | Bot-style picker; seat a realistic mix at a 6-max table |
| **2. Identify types blind** | the same behavioral signals P3 classifies on (`features.py`) | Hide bot labels → after N hands the human guesses each opponent's archetype → reveal + score (this mirrors P3 classification — nice thematic tie-in) |
| **3. AI post-hand coaching** *(make-or-break)* | `equity.py` per-decision EV; the `backend/investigator/` pattern | Hand-summary assembler (human's decisions + board + opponent archetype/tendencies + equity at each decision) → **coach LLM call** → "you could have done X; vs a station that's better because Y" |

---

## 3. Architecture

```
┌─ 6-max table UI (frontend) ─────────────┐
│  human at one seat: fold / call / raise │
│  5 bot seats · board · pot · hand log   │
└───────────────┬─────────────────────────┘
                │ human action (HTTP/WS)
┌───────────────▼─────────────────────────┐
│  hand-loop service (reuse playsim)       │
│  table.py hand loop, but PAUSES for      │
│  human input at the human's seat;        │
│  bots = ArchetypeAgent.act               │
└───────────────┬─────────────────────────┘
                │ completed hand + per-decision equity
┌───────────────▼─────────────────────────┐
│  post-hand coach (reuse investigator)    │
│  structured hand summary → guardrailed   │
│  Claude (claude-opus-4-8) → coaching     │
└──────────────────────────────────────────┘
```

**The one real engine change:** `table.py` currently runs every seat through an agent
synchronously. The human seat must **await a decision** (pause the hand loop for human
input, resume on action). Add a `human_seat` hook / decision callback rather than
forking the engine. Keep the bots deterministic (seeded); only the human is live.

---

## 4. The coach (make-or-break) — DE-RISK THIS FIRST

Per Sargon's own analysis and the roadmap: **coaching quality is the make-or-break.**
"You should have folded" reads thin and sinks the demo no matter how polished the
table UI is. So **build the coach first, on a handful of canned hands, before any
table-UI work.**

- **Input (structured, grounded):** for each of the human's decisions — the board, the
  pot/odds, the human's action, the human's hole-card equity (from `equity.py`), and
  the **specific opponent archetype + its known leak/tendency** (from `knobs.py`).
- **Output (structured, like the investigator's summary):** per-decision assessment,
  the better line, *why it's better against this opponent type*, and the read on the
  opponent.
- **Guardrails:** grounded in the hand's facts + equity only; no fabricated cards or
  ranges; teaching tone. Reuse the investigator's structured-output + output-check
  scaffolding.
- **Scope v1 to the *decisive* opponent/spot** ("you were really playing a pot against
  the station in seat 5"). Full **multiway** equity/EV is a later coaching-depth phase
  — this is the one real cost of 6-max vs heads-up, so bound it in the coach, not by
  shrinking the table.
- **Model:** `claude-opus-4-8` via the Anthropic SDK (same as the investigator). Note:
  unlike the investigator (frozen demo artifact), coaching is on *live* human hands, so
  it's a **live call** per hand — plan for latency + per-hand cost.

---

## 5. Bots & difficulty

Map to existing archetypes; difficulty is **exploitability**, not a vague easy/hard:

- **Beginner:** static bot with obvious leaks (e.g. calling station).
- **Intermediate:** fewer leaks, basic positional awareness.
- **Advanced:** detects simple user patterns, adapts (a stretch goal — needs an
  opponent model).
- **Expert/solver-like:** the `solver_like` knob set / a stronger policy. **Do not
  claim GTO/optimal** — "solver-like" is a product label only.

Useful knobs already in `knobs.py`: fold frequency, preflop aggression, bluff rate,
value-bet threshold, call-down looseness. Expose **styles, not just strength** — a
player learns more from a bad-but-specific opponent than a generic "hard" bot.

---

## 6. Tech stack

- **Backend:** reuse the playsim engine (Python). A small FastAPI surface (the repo
  already has `backend/app/`) to start a hand, accept a human action, return state,
  and return the post-hand coaching. The engine pause-for-human-input is the core
  change.
- **Frontend:** the play UI in the existing React/Vite app (`frontend/`).
- **LLM coach:** Anthropic SDK; reuse `backend/investigator/` (prompt, guardrails,
  structured output, `claude-opus-4-8`). Check the `claude-api` reference for the
  current model id before wiring — don't hardcode from memory.

---

## 7. MVP milestone & scope boundaries

**Milestone (one question):** *"Can a user play 20 hands at a 6-max table of distinct
styles and come away understanding what each opponent does differently — with coaching
that actually explains why?"*

**Out of scope for v1:** real-money language · multiplayer · accounts · RL training
(keep the `act()` policy seam ready — `playsim/playsim/baselines.py` already scaffolds
an RL adapter — but don't build it) · GTO claims · adaptive/opponent-modeling bots
(stretch only) · full multiway coaching (decisive-spot only in v1).

---

## 8. Acceptance criteria

1. A playable **6-max** hand loop with the human at one seat and **3–4 distinct bot
   styles**; fixed blinds/stacks.
2. **Hand history** + a **post-hand coach** that produces **grounded, per-decision**
   feedback citing equity and the opponent's *specific* tendency (not generic advice).
3. A **blind "identify the type"** round: labels hidden → human guesses each
   opponent's archetype → reveal + score.
4. **Deterministic bots** (seeded; reproducible); the coach is the only live/LLM piece.
5. **Coaching-quality gate:** a reviewer agrees the feedback would actually help —
   tie this to per-decision EV + the named opponent leak, not vibes.
6. No real-money language; "solver-like" used only as a label (no GTO claim).

---

## 9. Hard rules / constraints

- **Reuse, don't reinvent:** the engine (`table.py`), the bots (`agent.py`/`knobs.py`),
  equity (`equity.py`), and the coach scaffolding (`backend/investigator/`).
- **Deterministic seeded bots**; byte-identical bot behavior for a given seed (the
  human is the only nondeterministic input).
- **6-max default, not heads-up.** Heads-up/short-handed is a strategically different
  game whose skills don't transfer, and it guts goals #1–#2 (you read a *roomful* of
  types). Bound multiway cost in the coach, not by shrinking the table. (See
  `demo-roadmap.html`.)
- **The LLM coach is fine** — teaching, not risk detection.

---

## 10. Suggested phasing

1. **Coach on canned hands** (de-risk the make-or-break) — assembler + prompt +
   structured output, graded on a few hand fixtures.
2. **Human-play hand loop** — `table.py` pause-for-human-input + a FastAPI surface.
3. **6-max table UI** + bot-style picker.
4. **Hand history** + wire the coach to live hands.
5. **Blind type-ID** mode + scoring.
6. **Difficulty presets** + polish.

---

## Related

- `docs/learn/playsim-next-simulation-ideas.md` — Idea 2 (the origin of this)
- `docs/learn/demo-roadmap.html` — Optional Track B (the scoped version + the 6-max rationale)
- `backend/investigator/` — the coach scaffolding to reuse
- `playsim/playsim/{table,agent,knobs,equity,hand_export}.py` — the engine + bots + equity
