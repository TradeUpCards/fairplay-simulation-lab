# Playsim room-routing: what we built, and why Standard beats FairPlay (so far)

**Date:** 2026-06-24
**Audience:** teammates + agents picking up the playsim routing work
**Status:** findings from the MVP closed-loop room simulator (PR #43, branch `feat/playsim-room-simulator`)
**Source code:** `playsim/playsim/{room,router_adapter,policies,arrivals,room_export}.py`
**Reproduce:** `playsim/analysis/room_policy_comparison.py`

---

## TL;DR

We built a closed-loop room simulator so we could test — instead of assume — whether FairPlay's
"route vulnerable players to healthy tables" idea actually retains more paid seat-time. **It
doesn't, in this model.** Across 4-hour and 8-hour runs over all 12 tables and 3 seeds:

- **Standard (most-full open table) wins or ties** on vulnerable paid seat-time.
- **FairPlay-route is competitive at 4h but falls ~9% behind by 8h** — more time makes it *worse*, not better.
- A neutral **Random** baseline ≈ Standard, so Standard is not a strawman-strong baseline.
- Our attempted fix, **FairPlay-balanced** (spread fish across healthy tables), **backfired** — it was the worst arm at both horizons.

The mechanism is **table liveness / churn**, not the routing decision itself: health-aware routing
scatters players, so more tables fall below the 2-player dealing quorum and **break**, displacing
players who then can't re-seat. Most-full concentrates players, keeps tables alive, and loses less
seat-time to churn. This is the payoff of building the sim honestly: a plausible product
intervention measurably backfires for a non-obvious systems reason.

**Important:** this is a result about *this synthetic model at this scale*, not a verdict on real
poker rooms. See [Caveats](#caveats).

---

## Why we built this

The previous Standard-vs-FairPlay comparison (`playsim routing` / `service.simulate_routing`) pitted
two **hand-authored rosters** (`routing_standard` / `routing_fairplay`) against each other. That
tests whether *a healthy table composition* retains players better than *an unhealthy one* — which
is nearly tautological. It never exercised the real router, and nothing in the sim made a seating
*decision*.

We wanted to answer the actual product question: **does the routing policy that chooses the seats
earn more retained paid seat-time?** That requires a closed loop — seekers arriving over time, a
policy placing each one, players bleeding and leaving, tables breaking — with the comparison driven
by *decisions*, not pre-built compositions.

---

## What we built

A per-hand, multi-table **room orchestrator** (`playsim/playsim/room.py`) that generalizes the
single-table `run_session` loop:

- A shared, **seeded, policy-independent arrival stream** (`arrivals.py`): the unseated players from
  `data/players.json` each seek a seat once over the horizon. Both A/B arms consume the *identical*
  stream — only placement differs.
- A swappable **seating-policy seam** (`policies.py`):
  - `StandardPolicy` — most-full open table (what real rooms do for liquidity). No backend.
  - `RandomPolicy` — uniformly random open table (neutral "no intelligence" baseline). No backend.
  - `FairPlayRoutePolicy` — the **real frozen backend router** (`backend/scoring/router.py`) via the
    cross-package adapter; seats the best non-gated open table.
  - `FairPlayProtectPolicy` — experimental, disabled-by-default; defers vulnerable seekers below a
    safety threshold.
  - `FairPlayBalancedPolicy` — experimental load-balanced variant (added to test the fix below).
- One **cross-package adapter** (`router_adapter.py`) — the *only* playsim module that imports
  `backend/scoring`. It owns the `int ↔ "P-*"` id seam and assembles backend-shaped table dicts.
- Canonical output + a derived v1 adapter (`room_export.py`): `room_sim_{standard,fairplay}.json`
  (full causal trace) is the source of truth; `room_metrics_*` is a derived compatibility view.

### The guardrail (load-bearing)

Routing uses **backend composition-driven predicted health** (`score_table(..., sessions=None)` →
`P_bleed = 0`). Playsim's **realized chip-flow health is evaluation-only** and never feeds a routing
decision. A structural test enforces that `room.py` never imports `playsim/health.py`. This keeps
the comparison a real test rather than a tautology.

### Headline metric

**Retained paid seat-time for the vulnerable cohort** (`new` / `recreational` / `promo_hunter`),
where seat-time accrues per hand dealt while seated at an active (≥2-player) table. It's a *sum*, so
when seats are scarce it rewards keeping more vulnerable players seated and dealing.

---

## Results

All runs: 12 tables, seeds `42, 7, 99` (averaged), equity samples = 6, 40bb stacks, `skill_edge=1.6`.

### 4-hour horizon (240 min)

| policy | cohort seat-hrs | arrival survival (min) | table breaks | break-displacement balks |
|---|---|---|---|---|
| random | 9.66 | 7.9 | 27.0 | 15.0 |
| **most-full** | **9.99** | 8.4 | **20.0** | 16.7 |
| fairplay | 9.84 | 8.8 | 28.7 | 26.0 |
| fairplay-balanced | 8.62 | 2.1 | 47.3 | 44.7 |

### 8-hour horizon (480 min)

| policy | cohort seat-hrs | arrival survival (min) | table breaks | break-displacement balks |
|---|---|---|---|---|
| random | 9.94 | 9.0 | 25.7 | 14.3 |
| **most-full** | **10.06** | 8.6 | 28.3 | 24.3 |
| fairplay | 9.16 | 4.5 | 37.7 | 34.3 |
| fairplay-balanced | 8.62 | 2.0 | 48.7 | 45.7 |

### What the numbers say

- **Most-full wins or ties at both horizons.** At 4h it's effectively tied with FairPlay (9.99 vs
  9.84, ~1.5%); by 8h it leads FairPlay by ~9% (10.06 vs 9.16).
- **FairPlay degrades with time.** Competitive at 4h → clearly behind at 8h. The hypothesis that "an
  8-hour horizon gives table-health time to express as longer survival" is **refuted** — FairPlay's
  arrival survival actually *drops* (8.8 → 4.5 min) as the run lengthens.
- **Random ≈ Most-full.** The neutral baseline is within ~1–3% of most-full, so most-full is a fair,
  not-inflated baseline. FairPlay loses to a coin flip too.
- **The balanced "fix" is the worst arm.** More on that below.

---

## Why Standard (most-full) is better — the mechanism

It is **not** a bad routing decision. We probed the frozen router directly: given a clean choice
between a predator nest (predicted health 31.7) and a balanced table (90.0), the router correctly
picks the healthy table (rank 57.0 vs 35.2). The decision logic is sound.

The cause is **table liveness / churn**, visible in the `breaks` and `break-displacement balks`
columns:

- A table that drops below 2 seated players **breaks**. Its occupants are displaced and must
  re-seek; many find no open seat and **balk** (lose all further seat-time).
- **Most-full concentrates** players onto the fullest tables, keeping them above the dealing quorum →
  fewest breaks (20 at 4h) and fewer failed re-seatings.
- **Health-routing scatters** attention across tables by health → more tables hover near quorum →
  more breaks (FairPlay 29→38) and far more break-balks (26→34) → more seat-time lost to churn.

At this room scale (12 tables, ~95% initial occupancy), the **binding constraint is keeping tables
alive**, and concentration is structurally better at that. The health benefit (vulnerable players at
safer tables) is real but small, and it is swamped by churn losses that *grow with the horizon*.

This also matches reality: real cardrooms run **table-balancing** (consolidate short games, break
the emptiest) precisely to preserve liquidity. Most-full is a crude version of that, and it's hard
to beat on a throughput-shaped metric.

---

## What we tried that failed: FairPlay-balanced

Hypothesis: if greedy concentration onto the single healthiest table is the problem, **spread** fish
across the healthy-enough tables (pick the acceptable table with the fewest fish already seated).

It **backfired badly** — worst seat-hrs at both horizons (8.62) and by far the most breaks (47–49).
Spreading fish thin put isolated fish onto non-fish tables (faster bleed) and fragmented the room
below quorum (catastrophic churn). This is strong confirmation that **at this scale liquidity
(concentration) beats distribution** — the opposite of the load-balancing intuition. We kept the
policy in the tree (behind the seam) because the negative result is itself the finding.

---

## Caveats (read before quoting this)

- **Model-specific.** This is a synthetic sandbox: heuristic archetype agents, a zero-sum
  `skill_edge=1.6` transfer, 40bb stacks, one arrival per unseated player, break-at-<2, a near-full
  12-table room. Different assumptions could flip the result. This is **not** evidence that
  risk-aware routing is bad in a real room.
- **The metric is throughput-shaped.** Cohort paid seat-time is a sum, so it structurally rewards
  liquidity. A per-player-survival or harm-avoided metric might rank the policies differently — worth
  exploring.
- **`arrival survival` is a noisy secondary signal** (the seated/balked sets overlap when a seated
  arrival is later displaced by a break). Trust `seat_hrs` as the headline; treat survival as
  directional.
- **The value here is the method, not a verdict.** We built an honest counterfactual and let it tell
  us something inconvenient. We deliberately did **not** tune the model to manufacture a FairPlay win.

---

## How to reproduce

```bash
cd playsim && make install          # one-time: 3.12 venv + PokerKit + editable install

# 4-hour and 8-hour N-way comparisons (random / most-full / fairplay / fairplay-balanced)
.venv/bin/python analysis/room_policy_comparison.py --horizon 240 --seeds 42,7,99
.venv/bin/python analysis/room_policy_comparison.py --horizon 480 --seeds 42,7,99

# The shipped Standard-vs-FairPlay-route A/B (writes room_sim_*.json + room_metrics_*.json)
.venv/bin/python -m playsim.cli room-sim --seeds 42,7,99 --horizon 480 --out-dir out

# Full suite (64 tests)
make test
```

Everything is seeded and deterministic — same `(seed, horizon, policy)` reproduces byte-identically.

---

## Open questions / next steps

1. **Pin the churn story tighter.** Attribute lost seat-time to specific break cascades; confirm
   health-routing's extra breaks come from leaving tables near quorum.
2. **Try a liveness-aware FairPlay.** Add a *liquidity/quorum* term to the rank (prefer healthy
   tables that stay above quorum) rather than naive spreading — the balanced variant spread the wrong
   way.
3. **Reconsider the metric.** Test a per-vulnerable-player survival or "bad sessions prevented"
   metric that isn't pure throughput, since FairPlay's value proposition is harm-avoidance, not seat
   count.
4. **Scale sensitivity.** Re-run with a less-full room (more open seats) — liquidity may stop being
   the binding constraint, letting the health benefit show.

---

## Update — fit-aware behavior (Phase 2/3): the verdict holds and deepens

We later added a fit-aware behavioral model (`FitAwareBehaviorPolicy`) behind the player-behavior
seam: leaving becomes a multi-factor session-budget shrink (loss + composition **table-pressure** +
style **fit-mismatch**), so the simulator can finally reward the router's `Fit` dimension. We then
swept the fit/pressure weight (`w`) across Standard vs FairPlay-route (4h, 6 tables, 3 seeds; via
`playsim/analysis/fit_sensitivity_sweep.py`):

| weight `w` | Standard seat-hrs | FairPlay seat-hrs | Δ | Standard breaks | FairPlay breaks |
|---|---|---|---|---|---|
| 0.00 (= default model) | 4.20 | 3.92 | **−0.28** | 3.3 | 2.0 |
| 0.15 (modest default) | 4.31 | 3.80 | **−0.51** | 3.3 | 6.3 |
| 0.30 | 4.22 | 3.51 | **−0.72** | 4.0 | 6.3 |
| 0.50 | 3.90 | 3.20 | **−0.70** | 4.0 | 9.0 |

Two things matter here:

1. **The anti-circularity guard passed.** The risk was that fit-aware leaving would make FairPlay win
   *by construction* (the leave model rewarding exactly what the router optimizes — predicted-vs-
   predicted circularity). It did **not**: FairPlay's deficit *grows* with `w` (−0.28 → −0.72). The
   liquidity/breaks mechanism dominates the composition-reward channel, so the result is not a
   tautology of the model's own assumptions.

2. **It deepens the core finding.** FairPlay's table breaks climb **2.0 → 9.0** as players get more
   responsive, while Standard's barely move. Making players *more sensitive to table conditions* — the
   regime where smart routing should matter most — makes greedy health-concentration **more fragile**:
   clustered cohort tables collapse together when players turn flighty. Richer behavior amplifies the
   churn penalty rather than surfacing a health benefit.

**Still illustrative, not validated.** This is an uncalibrated parametric model; the numbers are
directional. Calibration to real session-length / churn data (the gate before any retention *claim*)
remains future work. But across the default model, the fit-aware model, and a weight sweep — and
against random, most-full, and a load-balanced variant — Standard is consistently at least as good,
and the cause is consistently **table liveness**, not the routing decision.

---

## Related

- Behavioral-model spec: `docs/brainstorms/2026-06-24-behavioral-fidelity-fit-model-requirements.md`
- Calibration data note (why these numbers stay illustrative): `docs/learn/playsim-calibration-data.md`
- Brainstorm: `docs/brainstorms/2026-06-23-playsim-routing-comparison-requirements.md`
- Plan: `docs/plans/2026-06-23-001-feat-playsim-room-simulator-plan.md`
- Circularity guardrail decision: `docs/learn/ai-hand-generation-decision.md`
- playsim engine modes: `docs/learn/playsim-engine-modes.html`
