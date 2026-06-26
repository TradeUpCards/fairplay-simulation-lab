# PRD / work-order — diurnal demand model + table-fill-rate capacity controller

**Date:** 2026-06-26
**For:** Sargon (playsim owner) + his coding agent
**From:** Cory (P3, scoring/routing)
**Status:** ready to pick up. Two sim changes + one combined experiment. Gated on nothing;
builds directly on the diagnostic finding merged in #67.

---

## 0. Background — read first

- `docs/learn/playsim-fairplay-retention-diagnostics-results.md` (#67) — the diagnostic
  sweep. FairPlay beats Standard on **vulnerable retained seat-hours** seed-stably at
  arrival rates 10–20, but the win **erodes to 0/3 by the saturated rate 40**. The
  operating point (demand vs capacity) is decisive; the mechanism (realized-chip-flow →
  later tilt-leave) is ablation-confirmed.
- `docs/learn/playsim-large-room-simulation.md` (#64) — the 50-table / 1000-player fixture
  and `large-room-sweep`.

**The product question this work-order answers:** real demand isn't a flat rate, and a
real operator can open tables. Does FairPlay's *off-peak* vulnerable-retention advantage
survive a realistic **daily demand cycle**, and can a **capacity controller** that keeps
the room out of saturation extend that advantage **through the peak**?

---

## 1. The two changes

| # | Change | Lives in | Owner |
|---|--------|----------|-------|
| 1 | **Diurnal arrival model** — `--arrival-mode diurnal`, a sine-modulated Poisson stream | `playsim/playsim/room.py` (+ CLI) | Sargon |
| 2 | **Capacity controller** — a room-fill-rate KPI + auto-spin-up of new tables | `playsim/playsim/room.py` (+ CLI) | Sargon |
| — | **Metric reporting** — emit metrics *by time-of-day bucket*, not just totals | `room_export.py` / sweep | shared (Cory can take) |

Both default OFF so existing results are unchanged (same discipline as `--formation-mode`).

---

## 2. Change 1 — diurnal arrivals

Today arrivals are `fixture-once` or flat `continuous`. Add `--arrival-mode diurnal`:

- **Rate function:** `rate(t) = base * (1 + amplitude * sin(2π (t − phase) / period))`,
  clamped ≥ 0, sampled as a seeded Poisson stream (preserve the A/B invariant: same stream
  into every policy arm, as `continuous` already does).
- **New params:** `--arrival-rate-base`, `--arrival-amplitude` (0–1), `--arrival-period-min`
  (default 1440 = 24h), `--arrival-phase-min`.
- **Horizon note:** the current 480-min (8h) horizon only sees part of a 24h cycle. Either
  extend the horizon to 1440 for a full cycle, or document that an 8h run is a single
  shoulder→peak slice. Recommend a full-cycle option for this experiment.
- **Determinism:** seeded; `--arrival-mode diurnal` with a fixed seed must replay identically.

---

## 3. Change 2 — capacity controller (fill-rate KPI + auto-spin-up)

Add a room-level KPI and a control policy that opens tables when the room gets too full.

- **KPI (primary):** `room_fill_rate = seated_players / available_seats` across active +
  forming tables. (Secondary to report: fraction of active tables with zero open seats —
  the "forced into near-full tables" signal.)
- **Control rule:** when `room_fill_rate > fill_high_threshold` (sustained for
  `spinup_cooldown_min`), open a new table from the empty pool (becomes a `forming` table
  the router/liveness can seed). Cap at `max_tables`.
- **New params:** `--capacity-control` (flag), `--fill-high-threshold` (e.g. 0.85),
  `--spinup-cooldown-min`, `--max-tables`.
- **Why it should help FairPlay specifically:** keeping fill-rate below saturation
  preserves the **formation headroom** FairPlay needs to route a vulnerable player to a
  fresh healthy table instead of a near-full predatory one — exactly the dynamic that
  disappears at rate 40. It also reduces wait-and-leave balks.
- **Product framing:** this is a real operator feature (auto-open tables), and a natural
  **tunable for the RL routing loop** (`2026-06-26-rl-routing-loop-concept.md`) — the
  threshold becomes a learnable action.

---

## 4. The combined experiment (pre-register first)

Run: **diurnal demand × {capacity-control off, on} × {standard, fairplay, fairplay_liveness}**,
full-cycle horizon, seeds 42/7/99. Report **vulnerable retained seat-hours and total
seat-hours by time-of-day**.

- **Pre-registered hypothesis:** with capacity control on, the room stays below saturation
  at peak, so FairPlay's vulnerable-retention advantage (today off-peak only) **holds
  through the peak** too.
- **Falsification:** if FairPlay still loses vulnerable retention at the diurnal peak
  across all 3 seeds with the controller on, the controller does not rescue it — report that.

Follow the same anti-p-hacking discipline as #67: commit the grid/metric/criterion before
running; **calibrate the fill-rate threshold to an operational target** (e.g. "hold
fill-rate near 80%"), never to the FairPlay-minus-Standard delta; report every cell.

---

## 5. Guardrails

- **Determinism:** both features seeded and replayable.
- **Defaults OFF:** preserves prior headlines and keeps these as explicit experiments.
- **Illustrative synthetic data — never a validated retention claim** (CLAUDE.md).
- **A/B invariant:** one seeded demand stream shared across all policy arms.

## 6. Open questions

1. Horizon: extend to 1440 (full day) or document the 8h slice?
2. KPI definition: seat-utilization vs near-full-table fraction as the trigger — or both?
3. Should the controller also *close/merge* tables off-peak, or let natural breaks handle it?
4. Threshold calibration source (operational target vs a small pre-run scan)?
5. Ownership of the by-time-of-day metric reporting (Cory can take if Sargon owns the sim).

## Related

- `docs/learn/playsim-fairplay-retention-diagnostics-results.md` (#67) — the finding this builds on.
- `docs/brainstorms/2026-06-26-rl-routing-loop-concept.md` — the controller threshold as an RL action.
- `docs/learn/playsim-fairplay-retention-preregistration.md` — the pre-registration pattern to reuse.
