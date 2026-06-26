# Note for Sargon — your formation work flipped the result

**Date:** 2026-06-25
**From:** P3 (scoring/evidence) — this checkout
**Re:** `--formation-mode forming` + continuous arrivals (PR #57/#58) and PRD #59

---

## TL;DR

Your formation work did the job. With **continuous arrivals + forming tables**,
FairPlay flips from losing (~−10% at 8h in the baseline) to a **small but seed-stable
win on all 3 seeds**. So the four changes in PRD #59 (`liveness-aware-routing-and-
formation-prd.md`) are now an **optional enhancement, not the rescue** the demo needed.

## What we ran

The 2×2 lever sweep (single seed 42, 8h) plus a 3-seed confirmation of the winning
cell. Full table and caveats: `docs/learn/playsim-table-formation-gap.md` → *Results*.

| | formation `none` | formation `forming` |
|---|---|---|
| `fixture-once` | −10.2% (baseline) | −4.6% (gap halves; breaks → 0) |
| `continuous` | −13.3% (demand alone hurts) | **+3.2% → FairPlay wins** |

3-seed confirmation (continuous + forming, seeds 42/7/99, 8h): FairPlay **10.76** vs
most-full **10.69** mean (**+0.65%**), winning on **all 3 seeds**, **breaks = 0**.

Two takeaways: **formation is the lever** (it helps in both arrival modes), and **the
flip needs both** demand *and* forming (only that cell crosses zero). Demand without a
formation mechanism actually made FairPlay *worse*.

> These are **illustrative synthetic numbers, not a validated retention claim** — the
> point is that the model's *ranking* of the policies flips once it can form tables.

## What this means for PRD #59

The PRD's premise — "FairPlay looks worse partly because the router scores forming
tables as fragile, Fit ignores size, and no one will start a table" — is sound, but
**formation alone already inverts the baseline**, so #1–#4 are no longer load-bearing
for the demo:

- **#1 Frag-decouple** (P3, `health.py`) — *deferred.* Optional: would let forming
  tables score well and could widen the +0.65% margin, but isn't needed to flip it.
- **#2 Size-fit** (P3, `seating.py`) — *deferred.* Same: enhancement, not rescue.
- **#3 Player propensity** (`behavior.py`) — optional realism; would make the forming
  dynamic behaviorally richer, not change the verdict.
- **#4 Liveness-aware FairPlay policy** (`policies.py`) — the most interesting "make
  the margin bigger" lever, but a *nice-to-have* now, not a blocker.

**Recommendation:** keep PRD #59 open as an enhancement track and reprioritize it
below demo-critical work. If you want to pursue the margin, **#1 + #4 together** are
still the load-bearing pair (one lets a forming table score well, the other makes
FairPlay use it — neither helps alone). The shared seam (`table_mode` + `target_seats`
in `make_table_dict`) is still the right first step if/when that track resumes.

## Pointers

- Result + caveats: `docs/learn/playsim-table-formation-gap.md`
- Why numbers stay illustrative: `docs/learn/playsim-calibration-data.md`
- The enhancement PRD: `docs/brainstorms/2026-06-25-liveness-aware-routing-and-formation-prd.md`
