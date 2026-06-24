---
date: 2026-06-24
topic: behavioral-fidelity-fit-model
---

# Fit-aware, calibrated behavioral model for the room simulator

## Summary

Replace the simulator's loss-rate-only leave decision and forced seat placement with a **fit-aware,
multi-factor stay / leave / choose model**, so the room simulator can actually test the FairPlay
thesis — "better-fit tables retain players longer" — instead of a proxy it structurally can't reward.
The model stays **parametric, seeded, and replayable** (no LLM in the loop) and is **calibrated**
against target session-length / churn distributions so its retention numbers mean something. An
agentic/LLM decision layer is explicitly deferred to a later V2 experiment.

## Problem Frame

The thesis is about player–table **fit** and **choice**: a player stands up for reasons tied to table
dynamics, and routing them to a better-suited table keeps them seated longer. The current simulator
cannot express that:

- **Leaving is single-factor.** `cohort_should_leave` (in `playsim/playsim/runner.py`) responds only
  to chip-loss rate (loss → tilt → shorter session). Style mismatch, pace, boredom, stop-loss/win-goal
  — none exist.
- **Joining has no agency.** The policy *forces* a placement; the player never accepts or declines a
  recommendation, even though the real product *recommends* and a human *decides*.
- **The router optimizes a dimension the player model ignores.** `backend/scoring/seating.py` ranks
  partly on a `Fit(P,T)` term (0.30 weight), but a simulated player's retention is blind to fit — a
  perfectly-fit seat earns *no* extra seat-time unless it also reduces losses. The router believes in
  fit; the behavioral model doesn't. **The simulator therefore cannot reward the exact variable the
  thesis is built on**, which makes routing comparisons test the wrong thing.

Consequence: the current "FairPlay loses to Standard" result is real *for this model* but is downstream
of a behavioral model too thin to carry the thesis (see
`docs/learn/playsim-room-routing-findings.md`). This spec closes that gap on the behavioral side.

## Key Decisions

- **Parametric, not agentic (for v1).** A calibrated parametric stay/leave/choose model preserves
  determinism/replay (a hard product rule), is far cheaper at scale, and — critically — can be
  *calibrated to data*. An LLM/agentic player is just another ungrounded prior; intelligence ≠
  fidelity. The agentic version is a separate V2 *experiment* (does it differ from the calibrated
  parametric model?), not a prerequisite.
- **Define fit once, consistently with the router.** The behavioral fit signal must align with
  `backend/scoring/seating.py`'s `Fit` (style keys / fit matrix) so the router and the player model
  agree on what "fit" means — otherwise the experiment is incoherent.
- **Calibration gates numeric claims.** Until the model is fit to real (or best-available proxy)
  session-length / churn data, its retention numbers are labeled **illustrative, not validated**. No
  simulation validates the thesis on hand-authored parameters — only calibration (or a production A/B)
  does.
- **Backward-compatible by construction.** With the fit weight set to 0, the model must reproduce the
  current loss-rate-only behavior, so existing results are a recoverable special case and the change
  is regression-comparable.

## Requirements

**Fit & preference**
- R1. Each player has a **preference profile** (preferred table style / stakes / pace tolerance),
  derived from archetype defaults (+ player fields where available).
- R2. A **behavioral `fit(player, table)` signal**, defined consistently with
  `backend/scoring/seating.py`'s `Fit`, that the leave and join models consume.

**Multi-factor leave model**
- R3. Replace the single-factor leave decision with a **multi-factor leave hazard** combining:
  chip-loss/tilt (existing), **fit mismatch**, base session length, and optional **stop-loss /
  win-goal** thresholds; factor weights are configurable.
- R4. The **leave reason** is recorded in the causal trace per departure (`tilt`, `mismatch`,
  `session_complete`, `stop_loss`, `win_goal`).
- R5. With the fit-mismatch weight = 0, the model **reduces to current behavior** (regression-comparable).

**Join agency**
- R6. An arriving player **accepts or declines** the policy's recommended seat with a fit-dependent
  probability (models "recommend → human decides"); a decline considers alternatives or balks.
- R7. The accept/decline outcome and its driver are recorded in the routing-decision trace.

**Calibration & determinism**
- R8. A **calibration routine** fits the model's parameters to target session-length and churn
  distributions, with the data source documented; uncalibrated runs are labeled illustrative.
- R9. The model is **seeded and byte-replayable** — no LLM/network call in the simulation loop.
- R10. Re-run the 4-way A/B (random / most-full / fairplay / fairplay-balanced) under the fit-aware
  model, plus a **sensitivity sweep** on the fit weight, and report whether the router's Fit dimension
  now earns retention.

## Acceptance Examples

- AE1. **Regression.** Fit weight = 0 → run output matches the current model within seeded tolerance.
  **Covers R5.**
- AE2. **Fit earns retention.** The same player, all else equal, stays longer at a high-fit table than
  a low-fit one. **Covers R2, R3.**
- AE3. **Choice is real.** A player offered a low-fit recommendation can decline; the decline (and its
  reason) appear in the trace. **Covers R6, R7.**
- AE4. **Reasons are attributed.** Every departure in the trace carries a leave reason; the mix shifts
  with table composition. **Covers R4.**

## Success Criteria

- Fit has a **measurable, calibratable** effect on retention (not hard-wired), and the router's `Fit`
  term is now behaviorally rewarded.
- Determinism/replay holds; the prior result is recoverable at fit weight 0.
- A documented **calibration** step and a **sensitivity analysis** accompany any retention claim;
  uncalibrated runs are clearly labeled illustrative.
- The re-run A/B is interpretable: we can say whether fit-aware retention changes the
  Standard-vs-FairPlay conclusion, and attribute *why*.

## Scope Boundaries

### Deferred for later
- **Agentic / LLM decision layer** — a V2 experiment to test whether emergent agent reasoning differs
  materially from the calibrated parametric model. Not required to test the thesis.
- Full per-player behavioral heterogeneity beyond archetype-derived preferences.
- Fit-aware leave for the *non-cohort* field (predators/regulars) — start with the cohort.

### Outside this effort's identity
- Real-time / production lobby routing (an explicit product non-goal).
- Claiming real-world validation of the routing→retention thesis without real data or a production A/B.
  The simulator tests "given this behavioral model, does routing help"; it does not prove the thesis.

## Dependencies / Assumptions

- **Fit definitions** reused from `backend/scoring/seating.py` (style keys, fit matrix) so router and
  player model agree.
- **The load-bearing dependency: calibration data.** Access to real (or best-available proxy)
  session-length and churn distributions. If unavailable, the model is built but its numbers stay
  illustrative until data exists.
- Existing room loop (`playsim/playsim/room.py`), the `cohort_should_leave` seam, and the policy seam
  (`policies.py`).

## Outstanding Questions

### Resolve before planning
- What calibration data do we actually have or can synthesize? (Blocks *validation*, not *building*.)
- How is player preference represented — per-archetype defaults, or per-player vectors? Does the
  fixture carry enough signal?

### Deferred to planning / implementation
- Does the liquidity/table-break confound from the current findings persist under fit-aware leaving?
  (Likely yes — breaks are mechanical — worth confirming, and may motivate an operator-side
  table-balancing model as a separate effort.)
- Should join agency model a "wait for a better seat" option, or only accept/decline/balk?

## Related
- Findings that motivate this: `docs/learn/playsim-room-routing-findings.md`
- Team guide: `docs/learn/playsim-room-simulator-guide.html`
- Current leave model: `playsim/playsim/runner.py` (`cohort_should_leave`, `_effective_session_min`)
- Router Fit term: `backend/scoring/seating.py`
