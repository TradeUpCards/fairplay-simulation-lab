# Calibration data for the room simulator — why it's the gate, and how we'd get it

**Date:** 2026-06-24
**Audience:** team (product + data + eng)
**Status:** decision note — the one thing between "illustrative" and a defensible claim
**Related:** `docs/learn/playsim-room-routing-findings.md` ·
`docs/brainstorms/2026-06-24-behavioral-fidelity-fit-model-requirements.md`

---

## TL;DR

Every retention number the room simulator produces today is **illustrative, not validated**, because
the player behavioral model (how long someone stays, when they leave, whether they accept a seat) runs
on **hand-authored parameters**. A simulation can only answer *"given this behavior model, does routing
help?"* — so if we author the behavior, we're testing our own assumptions, not reality. **Calibration —
fitting the model's parameters to real session/churn data — is what turns the whole machine from a
hypothesis explorer into something that can make a claim.** No amount of additional engineering or
agent "intelligence" substitutes for it; only data (or a live A/B) does.

---

## Why it matters

Our findings are robust *as a mechanism story* — across the default model, the fit-aware model, a weight
sweep, and four routing policies, Standard wins and the cause is table-liveness/churn. But the
**magnitudes** (how many seat-hours, how much retention) and even the **sign** of the routing effect
depend on parameters we currently set by hand:

- session length by archetype (`session_min_for`) and its spread
- the tilt curve (how fast losing shortens a session)
- the fit/pressure weights (`w_fit`, `w_pressure`) — the whole fit-aware thesis lives here
- decline propensity (how often a player rejects a recommended seat)

A reviewer's fair question — *"did FairPlay actually do worse, or did you just pick parameters that say
so?"* — has no good answer until those parameters are grounded. Calibration is the answer.

## What calibration would add

1. **Trustworthy retention numbers.** The seat-hours deltas become estimates of a real quantity, not
   artifacts of chosen constants.
2. **A pinned operating point instead of a sweep.** Today we *sweep* `w_fit`/`w_pressure` because we
   don't know the true value. Calibration replaces the sweep with a fitted value (with confidence
   bounds), so the comparison runs at the real behavior, not a grid.
3. **Real funnel magnitudes.** The acceptance funnel (offered → accepted → declined → balked) gets true
   rates, so we can size the acceptance vs retention channels.
4. **A credible go/no-go.** "FairPlay routing changes vulnerable paid seat-time by X% (95% CI …)"
   becomes a statement product can act on — or a clear signal to change the policy (e.g., the
   liveness-aware variant) before any rollout.

## What data we actually need

In rough priority — the model needs to learn three relationships:

| Target relationship | Minimum data | Fits these parameters |
|---|---|---|
| **Session length by player segment** | completed-session durations tagged by archetype/segment | `session_min_for`, spread |
| **Loss rate → session shortening** | per-session duration + that session's win/loss (bb or $) | the tilt curve constants |
| **Table conditions → leaving** | session duration + table composition at the player's table over time | `w_pressure`, `w_fit` |
| **Accept/decline of a seat** | lobby events: a seat was offered/recommended and taken or not | decline propensity |

The first two are the floor (they make survival realistic). The third is what makes the *fit/routing*
thesis testable. The fourth is only needed if we turn the decline channel on.

## The path to calibration data (best → weakest)

1. **Real operator data (gold standard).** Session/seat-event logs + hand histories + table-composition
   snapshots from an actual online poker room (a partner/operator, or FairPlay's own platform if/when
   it exists). This is the only source that links *table conditions* to *leaving* — the relationship the
   thesis hinges on. **Constraints:** data-sharing agreement, privacy/PII handling, and the project's
   responsible-use stance (aggregate/derived stats, not raw player data, wherever possible).
2. **A live pilot / production A/B (the real validator).** If even a small slice of real traffic can be
   routed FairPlay-vs-Standard, it measures the retention effect *directly* — which is strictly stronger
   than calibrating a sim. If this is on the table, it changes the sim's role from "make the claim" to
   "design the experiment and bound expectations."
3. **Public / third-party proxies.** Published poker session-length studies, operator transparency
   reports, licensed hand-history datasets, academic online-poker churn datasets. Gets us realistic
   *session-length distributions* (targets 1–2) but usually **not** the table-composition→leave link
   (target 3). Document fidelity and gaps.
4. **Expert priors (de-risk only, not validation).** Structured elicitation from experienced
   players/operators to bound plausible parameter ranges. Useful to keep the sweep honest and set
   sensible defaults; it does **not** validate — label any such run illustrative.

## How we'd fit it (sketch)

- Estimate target session-length distributions per segment; fit `session_min_for`/spread by matching
  moments (or MLE on a survival model).
- Regress observed session length on realized loss rate to fit the tilt curve.
- If composition data exists, regress leave hazard on composition-derived pressure and on style fit to
  fit `w_pressure`/`w_fit`. **Critically: fit table-pressure response from *behavior data*, not from
  the router's health formula** — otherwise we re-introduce the predicted-vs-predicted circularity the
  sim is built to avoid (see the findings doc).
- Validate on a **held-out** slice: does the calibrated sim reproduce the held-out session-length
  distribution and churn rate it never saw? Report the gap.

## Decision

Until tier-1 (operator data) or tier-2 (pilot) exists, all room-sim retention outputs remain **labeled
illustrative**, and the fit/pressure weights stay **swept, not claimed**. Tier-3/4 can sharpen defaults
and ranges but does not lift the illustrative label. This is not a blocker to *building* (the model and
harness are done); it is the blocker to *claiming*. The single highest-leverage next step for the
behavioral thesis is securing tier-1 or tier-2 data.
