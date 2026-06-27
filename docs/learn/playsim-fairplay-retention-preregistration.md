# Pre-registration — can FairPlay beat Standard at large-room scale, honestly?

**Date:** 2026-06-26
**Status:** pre-registered BEFORE seeing diagnostic results. Committed first on purpose.
**Author:** P3 (scoring) checkout. Coordinate with sogwiz (large-room track, #65) and
Sargon (PRD #59) before any code change.

## Why this exists

The small-room (12-table) "FairPlay flip" (+0.65%) was a small-pool/low-sample
artifact; at large-room scale sogwiz's #65 shows **Standard still leads** FairPlay-route
(1599 vs 1571 total paid seat-hours) and even FairPlay-liveness does not overtake
(1672 vs 1680, single seed). This document pre-commits the experiment so the result is
honest — not tuned until FairPlay wins.

## Root-cause hypothesis (from code, not yet from data)

The north-star metric (total paid seat-hours = table-minutes at ≥2 seated) rewards
concentration, and the sim has **no health → retention feedback loop**: the leave
decision (`runner.py:cohort_should_leave`) ignores table health/predator exposure
entirely. So FairPlay's health benefit has no causal path to the metric.

## The claim under test (committed in advance)

> When the model includes a health-driven attrition mechanism for the vulnerable
> cohort, FairPlay raises the **vulnerable cohort's retained seat-time** relative to
> Standard. The claim is about *vulnerable retention*, NOT raw total seat-hours.

## Falsification criterion (committed in advance)

The thesis **fails at this scale** if, with the attrition mechanism calibrated to an
external anchor (not to the FairPlay–Standard delta), FairPlay does not beat Standard
on vulnerable retained seat-hours across **all 3 seeds (42, 7, 99)**. We will report
that failure plainly.

## Metrics we will report (ALL of them, no post-hoc selection)

- Total paid seat-hours (north-star).
- Vulnerable paid seat-hours (cohort = new, recreational, promo_hunter).
- Mechanism metrics: breaks, wait-balks, no-good-existing-seat, forming seats,
  formation activations.
- Per policy arm: standard, fairplay, fairplay_liveness.

## Grid we will report (committed in advance)

- **Seeds:** 42, 7, 99 (every seed reported, not the best).
- **Arrival rates:** 10, 20, 30, 40 per hour (full curve reported, not the best cell).
- **Samples:** 1 (50-table hand-level sweeps are expensive; same as #65). Noted as a
  low-sample caveat; a winner survives only if it is seed-stable.

## Anti-p-hacking commitments

1. **Report the full grid, win or lose.** No cherry-picking a rate or seed.
2. **Any new parameter is calibrated to an EXTERNAL anchor** (e.g. a plausible
   session-length reduction for a vulnerable player at a maximally predatory table),
   locked BEFORE the policy comparison — never tuned against the FairPlay–Standard delta.
3. **One mechanism at a time, with ablation** to attribute which lever did the work.
4. **The metric is fixed here, in advance.** Changing the objective after seeing
   results is out of bounds.
5. **Illustrative on synthetic data — never a validated retention claim** (CLAUDE.md).

## Diagnostic phase (no code change) — what these runs decide

- **D1 — arrival-rate sweep (option 4):** is the large room oversubscribed (every seat
  fills → routing moot → Standard trivially wins)? Report total + vulnerable seat-hours
  for all 3 policies at rates 10/20/30/40.
- **D2 — #3 in isolation:** does liveness scoring (frag-decouple + size-fit, already
  built behind `--liveness`) move the result vs plain fairplay at any rate? This is the
  fairplay vs fairplay_liveness contrast within the same sweep.

**Decision rule:** if the diagnostics are flat-Standard across all rates (and liveness
does not win anywhere seed-stably), that is the evidence that justifies building the
structural retention loop (option 1). If FairPlay/liveness already wins seed-stably at
some plausible rate with no code change, we investigate *why* before claiming anything.
