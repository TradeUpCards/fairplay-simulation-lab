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

## Phasing (this spec modifies the room-sim plan; it does not replace it)

The closed-loop room simulator already exists and ships in PR #43. This spec is the **next layer**,
sequenced so scope stays bounded and each phase is independently shippable:

- **Phase 1 — `PlayerBehaviorPolicy` seam (behavior-preserving).** Extract today's player decisions
  (cohort tilt-leave, always-accept, re-seek-once) from `room.py`/`runner.py` into one swappable seam,
  with the *current* rules as the default implementation. Small refactor, guarded by the existing
  determinism tests (same pattern as the `apply_hand_accounting` extraction). **Buildable now.**
- **Phase 2 — fit-aware parametric model behind the seam.** Multi-factor leave (loss + table-pressure
  + fit-mismatch + session budget), fit-aware join, archetype tolerances. Ships with **documented
  default parameters** (see "buildable vs validated" below).
- **Phase 3 — calibration, funnel reporting, sensitivity sweeps.** Fit parameters to data; report the
  acceptance/retention **funnel** separately; sweep fit/pressure weights. **This is where the
  anti-circularity guards live** — no retention *claim* before this phase.
- **Phase 4 — optional agentic / RL behavior experiment** (does emergent behavior differ from the
  calibrated parametric model?).

**Buildable vs validated (load-bearing).** Phases 1–2 can ship on documented default parameters and
are *not* blocked by the absence of calibration data. Calibration (Phase 3) is required only to make
**numeric retention claims**; until then, outputs are labeled illustrative. Missing data is never a
blocker to building the seam or the model.

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
- **Avoid predicted-vs-predicted circularity (the table-pressure trap).** The composition signal that
  makes a player *leave* (table pressure) is essentially the inverse of the composition signal the
  router *optimizes* (`backend Health = 100 − P_pred − P_frag − P_clus`). If the leave model rewards
  exactly what the router avoids, **FairPlay wins by construction** — the "baked-in numbers" critique
  in a new form that the existing predicted-vs-*realized* guardrail does not catch (both sides are
  composition). Guards: (a) table-pressure *strength* is calibrated to real leave behavior, not
  assumed; (b) the pressure weight is swept from 0, and any FairPlay win that appears *only* at high
  pressure weight is reported as an internal-consistency / mechanism check, **not evidence**;
  (c) prefer including pressure signals the router does *not* use (pace, volatility) to reduce overlap.
- **Backward-compatible by construction.** With the fit weight set to 0, the model must reproduce the
  current loss-rate-only behavior, so existing results are a recoverable special case and the change
  is regression-comparable.
- **One inspectable behavioral seam.** All player decisions — join/accept-decline, re-seek on table
  break, and leave/churn — live behind a single `PlayerBehaviorPolicy` component, parallel to the
  existing `SeatingPolicy`. Player behavior becomes one swappable, testable thing (and the eventual
  V2 agentic variant is just another implementation of the same seam), instead of logic scattered
  across `room.py` and `runner.py`.
- **Self-describing runs.** Every behavioral parameter (weights, tolerances, thresholds, seeds) is
  serialized verbatim into the output `run_config`, so a run is auditable and replayable from its own
  artifact with no external state. This is the simulator's observability primitive (see Dependencies).

## Requirements

**Player behavioral policy (the seam)**
- R1. Consolidate **join/accept-decline, re-seek-on-break, and leave/churn** behind a single
  `PlayerBehaviorPolicy` seam (parallel to `SeatingPolicy`); the room loop calls it rather than
  embedding the rules. Re-seek on break uses the *same* policy as initial join.
- R2. **All behavioral parameters are recorded verbatim in the output `run_config`** (weights,
  tolerances, thresholds, RNG seeds) so every run is self-describing, diff-able across runs, and
  replayable from its own artifact.

**Fit & preference (archetype-specific tolerance)**
- R3. Each player has a **preference profile** with archetype-specific tolerances (preferred table
  style / stakes / pace), derived from archetype defaults (+ player fields where available).
- R4. A **behavioral `fit(player, table)` signal**, defined consistently with
  `backend/scoring/seating.py`'s `Fit`, that the leave and join models consume.

**Leave / churn (probability + session budget)**
- R5. Replace the single-factor leave decision with a **multi-factor leave hazard / session budget**
  combining: **loss velocity** (existing tilt), **table pressure**, **fit mismatch**, base session
  length, and optional **stop-loss / win-goal** thresholds; factor weights are configurable. The
  decision may be a seeded **probabilistic hazard** rather than a hard threshold (it must still draw
  from the run's RNG so replay stays byte-identical).
- R6. **Table pressure** is a behavioral input — a composition-derived signal (aggressor load,
  predator/vulnerable ratio, active-cluster pressure, short-handed fragility) the player perceives,
  computed **without any future chip-flow / realized outcome**, distinct from the player's *own*
  realized loss. Because this overlaps the router's predicted-health terms, it carries the
  **predicted-vs-predicted circularity guard** (see Key Decisions): its weight is calibrated (not
  assumed) and swept from 0, and it should prefer router-independent components (pace, volatility)
  where possible.
- R7. The **leave reason** is recorded per departure (`tilt`, `table_pressure`, `mismatch`,
  `session_complete`, `stop_loss`, `win_goal`).
- R8. With the fit-mismatch and table-pressure weights = 0, the model **reduces to current behavior**
  (regression-comparable).

**Join & re-seek agency**
- R9. An arriving (or break-displaced) player **accepts or declines** the policy's recommended seat
  with a fit-dependent probability (models "recommend → human decides"); a decline considers
  alternatives or balks. **Decline is a separately-toggleable channel, default OFF in the first
  fit-aware build**, so the *retention* channel is measured before the *acceptance* channel is added
  (decline-because-bad-fit can otherwise manufacture a routing win through acceptance alone).
- R10. The accept/decline outcome and its driver are recorded in the routing-decision trace.
- R11. **Funnel reporting:** the summary separates `offered → accepted → retained`, plus `balks` and
  `declines`, per arm — so a routing win is attributed to the acceptance channel vs the retention
  channel rather than conflated into one seat-time number.

**Calibration & determinism**
- R12. A **calibration routine** fits the model's parameters to target session-length and churn
  distributions, with the data source documented; uncalibrated runs are labeled illustrative.
- R13. The model is **seeded and byte-replayable** — no LLM/network call in the simulation loop.
- R14. Re-run the 4-way A/B (random / most-full / fairplay / fairplay-balanced) under the fit-aware
  model, plus a **sensitivity sweep** on the fit and table-pressure weights, and report whether the
  router's Fit dimension now earns retention.

**Decision-trace fidelity (room_sim schema)**
- R15. Each **backend-routed** `routing_decisions` entry carries a minimal **rationale** in the
  *default* trace — the chosen table's `rank`, `health`, `delta_health`, `seating_risk`, `badge`,
  `integrity_gated` (alongside the existing `reason` and `table_id`) — so the artifact answers "why
  *this* table?" without re-running. Standard/Random carry no rationale (no backend decision). *(Shipped.)*
- R16. A **`--debug-trace`** tier attaches the **full ranked candidate list** to each decision and is
  the home for any future verbose per-hand/per-player internals; the default `room_sim_*` stays the
  compact decision/session/summary trace. Per-hand hand histories remain a *separate* artifact
  (`playsim_hand_histories_*`), never inlined into `room_sim_*`. *(Shipped.)*

## Acceptance Examples

- AE1. **Regression.** Fit and table-pressure weights = 0 → run output matches the current model
  within seeded tolerance. **Covers R8.**
- AE2. **Fit earns retention.** The same player, all else equal, stays longer at a high-fit table than
  a low-fit one. **Covers R4, R5.**
- AE3. **Table pressure shortens sessions.** A cohort player at a high-predation table leaves sooner
  than at a low-predation table of equal personal loss. **Covers R5, R6.**
- AE4. **Choice is real.** A player offered a low-fit recommendation can decline; the decline (and its
  reason) appear in the trace. **Covers R9, R10.**
- AE5. **Reasons are attributed.** Every departure carries a leave reason; the mix shifts with table
  composition. **Covers R7.**
- AE6. **Runs are self-describing.** The output `run_config` contains every behavioral parameter; a
  second run from only that artifact reproduces the result. **Covers R2.**
- AE7. **Decisions are explainable.** Every backend-routed seating in `routing_decisions` carries the
  six rationale fields; `--debug-trace` adds the full candidate list; Standard/Random carry neither.
  **Covers R15, R16.**

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
- **External LLM-observability tooling (LangChain / LangSmith) for the deterministic sim.** The
  simulation has no LLM in its loop; its observability primitive is the causal trace + `run_config` +
  `--debug-trace`. (LLM tracing belongs only to the AI Investigator subsystem, if anywhere — not here.)

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
