# PRD / work-order — demand regimes, diurnal arrivals, and optional capacity control

**Date:** 2026-06-26
**For:** Sargon (playsim owner) + his coding agent
**From:** Cory (P3, scoring/routing)
**Status:** revised plan. Do **not** jump straight to a capacity controller. First run
a static visible-capacity sweep, then add diurnal arrivals/time-bucket reporting.
Capacity control is deferred until/unless we decide to model closed/reserve tables as
a real operator action.

---

## 0. Background — read first

- `docs/learn/playsim-fairplay-retention-diagnostics-results.md` (#67) — the diagnostic
  sweep. FairPlay beats Standard on **vulnerable retained seat-hours** seed-stably at
  arrival rates 10-20, but the win **erodes to 0/3 by the saturated rate 40**. The
  operating point (demand vs capacity) is decisive; the mechanism (realized-chip-flow
  to later tilt-leave) is ablation-confirmed.
- `docs/learn/playsim-large-room-simulation.md` (#64/#65) — the 50-table /
  1000-player fixture and `large-room-sweep`.

**The product question:** FairPlay's vulnerable-retention result depends on the room's
demand/capacity regime. What table inventory and arrival-rate regimes are realistic,
and does FairPlay's off-peak/shoulder advantage survive when demand follows a daily
curve?

---

## 1. Revised plan

| Phase | Change | Why |
|---|---|---|
| 1 | **Static visible-capacity sweep** — vary total tables / active tables and flat arrival rate | Maps the demand/capacity regimes before adding another mechanism. |
| 2 | **Diurnal arrival model** — `--arrival-mode diurnal`, a sine-modulated Poisson stream | Replaces artificial flat rates with a realistic daily demand curve. |
| 3 | **Time-bucket metric reporting** — emit metrics by hour / time bucket, not just totals | Shows where FairPlay helps: off-peak, shoulder, or peak. |
| 4 | **Optional capacity controller** — only if we model closed/reserve tables | Real operator action; deferred until the simpler sweeps prove it is needed. |

Defaults stay unchanged. New modes/experiments must remain explicit.

---

## Why this sequence

1. **Static sweeps avoid overbuilding.** We already know FairPlay's vulnerable-retention
   result changes by arrival rate. Before adding diurnal demand or an operator-style
   controller, we need to map which table-capacity regimes are tight, moderate, loose,
   or saturated.
2. **Diurnal arrivals should be informed by known regimes.** A daily demand curve is
   only useful if we understand what its low/shoulder/peak rates mean in the current
   room model. The static sweep gives us that interpretation layer.
3. **Capacity control is only meaningful if there is something to open.** Today, under
   `--formation-mode forming`, empty tables are already visible to routing. An "open a
   table" controller is not a real action unless some tables start as closed/reserve
   and invisible.
4. **One new mechanism at a time keeps attribution clean.** If we add diurnal demand,
   time-bucket reporting, closed tables, and a controller together, we will not know
   which lever changed the result. This sequence preserves the same anti-p-hacking
   discipline as the demand-curve diagnostics.

---

## 2. Phase 1 — static visible-capacity sweep

Before building diurnal demand or capacity control, run a static sweep that varies
table inventory and flat arrival rate. This answers the simpler and more immediate
question: does FairPlay need enough **visible forming capacity** to express its
table-formation strategy?

Important: "visible capacity" means tables already available to routing. This is not
an operator opening tables. It is a static experiment where unused tables can be
assigned to when the policy chooses them.

Suggested grid:

```text
table shapes:
  40 tables / 35 active at start   # tight, 5 empty/forming tables
  50 tables / 35 active at start   # current, 15 empty/forming tables
  60 tables / 35 active at start   # loose, 25 empty/forming tables
  70 tables / 35 active at start   # very loose, 35 empty/forming tables

arrival rates:
  10, 20, 30, 40 per hour

policies:
  standard, fairplay, fairplay_liveness

seeds:
  42, 7, 99
```

Report:

- total paid seat-hours
- vulnerable paid seat-hours
- arrival seated / balk counts
- average and peak fill rate
- near-full table fraction
- forming seats
- formation activations
- final active/forming/empty tables
- breaks and wait-balks

Interpretation:

- If FairPlay only helps with very loose capacity, the thesis depends on abundant
  spare table inventory.
- If FairPlay helps in moderate capacity regimes but loses in tight/saturated regimes,
  the result is more credible and matches the diagnostic demand-curve finding.
- If Standard wins everywhere, then the current FairPlay/liveness policy still does
  not convert formation headroom into retention value.

This phase does **not** need closed-table semantics.

---

## 3. Phase 2 — diurnal arrivals

After the static sweep maps the regimes, add `--arrival-mode diurnal`. Today arrivals
are `fixture-once` or flat `continuous`; diurnal should be another policy-independent
seeded arrival stream.

- **Rate function:** `rate(t) = base * (1 + amplitude * sin(2pi (t - phase) / period))`,
  clamped to `>= 0`, sampled as a seeded Poisson stream.
- **New params:** `--arrival-rate-base`, `--arrival-amplitude` (0-1),
  `--arrival-period-min` (default 1440 = 24h), `--arrival-phase-min`.
- **Horizon note:** the current 480-min (8h) horizon only sees part of a 24h cycle.
  Either extend the horizon to 1440 for a full cycle, or document that an 8h run is
  a single shoulder-to-peak slice. Recommend a full-cycle option for this experiment.
- **Determinism:** seeded; `--arrival-mode diurnal` with a fixed seed must replay
  identically.
- **A/B invariant:** the same generated arrival stream must feed Standard, FairPlay,
  and FairPlay-liveness.

Fit in the sequence:

```text
static capacity x flat arrival-rate sweep
  -> identify regimes
diurnal arrival model
  -> test one day moving through those regimes
optional capacity controller
  -> only if we want operator actions
```

---

## 4. Phase 3 — time-bucket metrics

Diurnal runs need metrics by time bucket. Totals can hide the mechanism because
FairPlay may help off-peak/shoulder while Standard wins at peak.

Recommended hourly fields:

- arrival count
- active tables
- forming tables
- average fill rate
- peak fill rate
- near-full table fraction
- total paid seat-hours
- vulnerable paid seat-hours
- arrival balks
- wait-balks
- formation activations

This should live in the sweep/reporting layer where possible. The room loop already
emits hourly rollups; extend that path before adding a new controller.

---

## 5. Phase 4 — optional capacity controller

Defer this until after phases 1-3.

We do **not** need closed-table semantics for the static capacity sweep or diurnal
arrival model. But we **do** need them for a real capacity controller. Without a
closed/reserve state, all empty tables are already visible under `--formation-mode
forming`, so "open a table" is not a meaningful control action.

If we build capacity control later, define:

```text
closed/reserve: not visible to router; not counted in visible capacity
forming: visible to router; can be seeded/grown; no paid seat-time until quorum
active: dealing; paid seat-time accrues
draining/empty: lifecycle states after use
```

Then the operator action is:

```text
if visible_room_fill_rate > threshold for cooldown:
    activate one closed/reserve table into forming
```

KPI definitions should be explicit:

- **Primary KPI:** `visible_room_fill_rate = seated_players / seats_in_visible_tables`.
  Closed/reserve tables are excluded.
- **Secondary KPI:** fraction of visible active tables with zero open seats, the
  "forced into near-full tables" signal.
- **Control rule:** when `visible_room_fill_rate > fill_high_threshold` sustained for
  `spinup_cooldown_min`, activate a closed/reserve table into `forming`. Cap at
  `max_visible_tables`.
- **New params:** `--capacity-control`, `--fill-high-threshold`,
  `--spinup-cooldown-min`, `--max-visible-tables`.
- **Why it should help FairPlay specifically:** keeping fill rate below saturation
  preserves the **formation headroom** FairPlay needs to route a vulnerable player to
  a fresh healthy table instead of a near-full predatory one.

---

## 6. Experiments to pre-register

### Experiment A — static capacity sweep

Run the Phase 1 grid. This is the next recommended experiment.

- **Hypothesis:** FairPlay's vulnerable-retention advantage appears in moderate-capacity
  regimes and erodes when the room is saturated.
- **Falsification:** if FairPlay loses vulnerable retention across all capacity/rate
  cells, the current policy does not convert formation headroom into retention value.

### Experiment B — diurnal day, no controller

Run: **diurnal demand x {standard, fairplay, fairplay_liveness}**, full-cycle horizon,
seeds 42/7/99. Report vulnerable retained seat-hours and total seat-hours by time bucket.

- **Hypothesis:** FairPlay's vulnerable-retention advantage is strongest
  off-peak/shoulder and weakens at peak saturation.
- **Falsification:** if FairPlay does not win vulnerable retention in any non-saturated
  bucket across all 3 seeds, the static demand-curve result did not survive the
  diurnal setup.

### Experiment C — optional capacity controller

Only after A/B. Run: **diurnal demand x {capacity-control off, on} x {standard,
fairplay, fairplay_liveness}**. This requires closed/reserve table semantics.

- **Hypothesis:** with capacity control on, the room stays below saturation at peak,
  so FairPlay's vulnerable-retention advantage holds through more of the peak.
- **Falsification:** if FairPlay still loses vulnerable retention at the diurnal peak
  across all 3 seeds with the controller on, the controller does not rescue it.

Follow the same anti-p-hacking discipline as #67: commit the grid/metric/criterion
before running. If Experiment C is reached, calibrate the fill-rate threshold to an
operational target (e.g. "hold visible fill-rate near 80%"), never to the
FairPlay-minus-Standard delta; report every cell.

---

## 7. Guardrails

- **Determinism:** every new stream/control decision must be seeded and replayable.
- **Defaults unchanged:** preserves prior headlines and keeps these as explicit
  experiments.
- **Illustrative synthetic data:** never a validated retention claim.
- **A/B invariant:** one seeded demand stream shared across all policy arms.
- **No p-hacking:** table shape, rate grid, metric, and win rule must be fixed before
  running the comparison.

## 8. Open questions

1. Static capacity grid: are `40/50/60/70` tables with `35` active the right first
   table shapes?
2. Diurnal horizon: extend to 1440 (full day) or document the 8h slice?
3. Time buckets: hourly, 2-hour, or named off-peak/shoulder/peak buckets?
4. KPI reporting: seat-utilization vs near-full-table fraction — report both?
5. If capacity control is later pursued, should the controller also close/merge tables
   off-peak, or only activate reserve tables during pressure?
6. Ownership of the by-time-of-day metric reporting.

## Related

- `docs/learn/playsim-fairplay-retention-diagnostics-results.md` (#67) — the finding
  this builds on.
- `docs/brainstorms/2026-06-26-rl-routing-loop-concept.md` — the controller threshold
  as a possible RL action if/when capacity control exists.
- `docs/learn/playsim-fairplay-retention-preregistration.md` — the pre-registration
  pattern to reuse.
