# Playsim room-routing: what we built, and why Standard beats FairPlay (so far)

**Date:** 2026-06-24
**Audience:** teammates + agents picking up the playsim routing work
**Status:** findings from the MVP closed-loop room simulator (PR #43, branch `feat/playsim-room-simulator`);
follow-up formation probes now live behind explicit arrival/formation flags.
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

**Follow-up now implemented:** the sim can now run the table-formation probe that this result
motivated. Use `--arrival-mode fixture-once|continuous` and `--formation-mode none|forming` to test
whether the result changes when demand can continue and empty tables can enter a non-paid `forming`
state before becoming active.

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
- A controlled **formation probe**: the original `fixture-once` / `formation none` behavior remains
  the baseline, while `continuous` arrivals and `formation forming` let us test whether the old
  result was partly caused by a one-way liquidity drain. A forming seat is not paid seat-time; the
  table must reach quorum before hands are dealt.

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
- **Original formation gap.** The headline tables above use the baseline room model, where the room
  mostly drains from a fixed hour-0 roster. That structurally favors policies that keep existing
  tables full. The new forming-mode experiment exists specifically to test whether allowing
  `empty -> forming -> active` table growth narrows or flips that result.
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

# Formation follow-up: compare {fixture-once, continuous} × {none, forming}
.venv/bin/python analysis/room_policy_comparison.py --horizon 480 --seeds 42,7,99 \
  --arrival-mode continuous --arrival-rate-per-hour 8 --formation-mode forming

# Full suite (currently 88 tests)
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
5. **Table formation 2x2.** Run `{fixture-once, continuous} × {none, forming}` and report both the
   headline seat-hours and the formation mechanics: `no_good_existing_seat_count`,
   `forming_seat_count`, `formation_activation_count`, and `table_reactivation_count`. This is the
   direct test of whether FairPlay was penalized by the old model's inability to seed and grow a
   fresh healthy table.

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

## Update — reason-aware re-seating (Phase 3 probe): split "done for the day" from "done with this table"

We added a **reason-aware** player lifecycle model behind the existing `PlayerBehaviorPolicy` seam.
This does not change the router. It changes what happens after a player exits a table:

| exit reason | modeled action |
|---|---|
| `tilt_bleed` | terminal / low willingness to keep playing |
| `profit_taking` | terminal positive exit |
| `time_budget_complete` | terminal neutral exit |
| `table_thinning` | re-seek with wait tolerance |
| `table_break` | re-seek with longer wait tolerance |
| `bad_fit_decline` | optional wait / retry |
| `boredom_low_action` | re-seek with wait tolerance |

Why this matters: the original default model treated voluntary/tilt exits as terminal and allowed
only immediate break-displacement re-seating. That is too coarse for the FairPlay thesis. A player
leaving because a thin table is dying is not necessarily done for the day; they may still want to
play if FairPlay or the room can find a dealable replacement seat.

### Short-horizon check

To smoke-test the mechanism, we ran the N-way comparison at a 2-hour horizon with the same seed set
and compared `default` versus `reason-aware` behavior:

```bash
cd playsim
.venv/bin/python analysis/room_policy_comparison.py --horizon 120 --seeds 42,7,99 --equity 6 --behavior default
.venv/bin/python analysis/room_policy_comparison.py --horizon 120 --seeds 42,7,99 --equity 6 --behavior reason-aware
```

Default behavior:

| policy | cohort seat-hrs | arrival survival (min) | table breaks | break-displacement balks | wait balks |
|---|---:|---:|---:|---:|---:|
| random | 10.18 | 10.7 | 12.3 | 5.0 | 0.0 |
| most-full | 9.63 | 8.8 | 12.7 | 9.7 | 0.0 |
| fairplay | 10.44 | 11.2 | 12.0 | 9.7 | 0.0 |
| fairplay-balanced | 9.03 | 5.5 | 29.0 | 27.7 | 0.0 |

Reason-aware behavior:

| policy | cohort seat-hrs | arrival survival (min) | table breaks | break-displacement balks | wait balks |
|---|---:|---:|---:|---:|---:|
| random | 9.01 | 9.9 | 27.0 | 15.3 | 0.0 |
| most-full | 8.87 | 9.6 | 16.7 | 14.0 | 3.0 |
| fairplay | 8.89 | 10.0 | 23.0 | 21.0 | 5.3 |
| fairplay-balanced | 7.97 | 5.6 | 46.0 | 43.0 | 32.0 |

Read this carefully: this is a **mechanism probe**, not a new validated result. At 2 hours, the
default model is noisy and FairPlay can win. Under reason-aware behavior, FairPlay and most-full are
roughly tied on cohort seat-hours, but FairPlay still creates more breaks and more delayed re-seat
failures (`wait_balks`). The new model therefore does **not** erase the liveness/churn concern; it
makes the concern more attributable by separating:

- terminal churn: tilt/bleed, profit-taking, time-budget completion;
- re-seat churn: table-thinning exits, table-break displacement, bad-fit declines, and wait expiry.

### New design approach

Going forward, room-sim results should be reported as a funnel, not a single churn bucket:

`offered -> accepted -> seated -> retained`

and separately:

- `terminal_exits_by_reason`
- `reseek_attempts_by_reason`
- `reseek_success_by_reason`
- `wait_balks`
- `break_displacement_balks`
- vulnerable paid seat-hours

This keeps the interpretation honest. If FairPlay loses because players leave satisfied after a time
budget or profit-taking exit, that is not a routing failure. If FairPlay loses because thin-table
players still want to play but cannot find a dealable replacement seat before their wait tolerance
expires, the next product problem is liquidity/table balancing, not necessarily seat-quality ranking.

---

## Related

- Behavioral-model spec: `docs/brainstorms/2026-06-24-behavioral-fidelity-fit-model-requirements.md`
- Calibration data note (why these numbers stay illustrative): `docs/learn/playsim-calibration-data.md`
- Brainstorm: `docs/brainstorms/2026-06-23-playsim-routing-comparison-requirements.md`
- Plan: `docs/plans/2026-06-23-001-feat-playsim-room-simulator-plan.md`
- Circularity guardrail decision: `docs/learn/ai-hand-generation-decision.md`
- playsim engine reference: `docs/learn/playsim-engine.html`
