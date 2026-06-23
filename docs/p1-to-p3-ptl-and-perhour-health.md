# P1 → P3 — coordination ask: PTL ownership + per-hour health

**From:** P1 (demo UI) · **To:** P3 (scoring + evidence engine) · **Date:** 2026-06-22
**Status:** ✅ **RESOLVED 2026-06-22** (team decision) — see Resolution below.

## Resolution (2026-06-22)

Answered with the team; all three asks closed.

1. **PTL ownership → P1 derives it UI-side (for now).** P3 will not champion
   `scoring/ptl.py`. P1 implemented the fallback in `frontend/src/lib/ptl.ts`
   (`PTL = volatility(archetype) × pressure(table)`, archetype-gated, deterministic,
   `{code, detail, signals}` reason codes), wired into the seat-ring (U5). If P3
   later ships `ptl_scores.json`, the binding swaps in `PitBossTable` with no other
   change. **U2 + U5 seat-heat are now built.**
2. **Hot-PTL exemplar → undecided, defaulted to P-104.** No team answer yet, so
   the U2 validator pins to the clean contrast already in the data: **P-104 (new)
   hot at T-22, cool at T-8** (`frontend/tests/ptl.test.ts`). Note: T-11 still has
   **no seated fish** — its ring reads all-cool (cluster + grinders), which is
   truthful. If a hot seat at the flagged table is wanted for the demo, P3 seats a
   recreational player at T-11. (T-22's promo-hunter does render *warm*.)
3. **Per-hour table health → deferred.** Re-rank as the clock advances is out of
   scope until there's live/per-hour data. The index stays snapshot-ranked;
   `rankTables()` already re-sorts whatever it's handed, so a future series is a
   drop-in. **U4 live re-rank is settled-deferred, not blocked.**

---

_Original ask (for the record):_

## Context

P1 has shipped the demo spine against your frozen Contract-2 — player lobby,
pit-boss index, Standard-vs-FairPlay simulator, and the eval panel are all
clickable and bound to `data/derived/*.json` (5 of 7 plan units, 50 tests
green). The two remaining units need decisions only you can make. The UI binds
*your* result either way; nothing here asks P1 to own scoring.

Plan reference: `docs/plans/2026-06-21-001-feat-fairplay-demo-ui-plan.md` (U2, U4).

---

## Ask 1 — who owns per-seat PTL? (blocks U2 → U5)

PTL (per-seat *propensity to leave*, 0–1) is the **one score not in Contract-2**
and the only thing the demo computes. The pit-boss table view (U5) renders it as
per-seat heat on the seat-ring; that's the "fish about to bolt at an unhealthy
table" beat.

**Preferred:** you own it as a first-class champion — `scoring/ptl.py` +
`scripts/build_ptl.py` → `data/derived/ptl_scores.json`, with reason codes, the
same shape as your other scores. Then it's just another Contract-2 file P1 binds.

**Fallback:** P1 derives it UI-side from `seating_scores` + `classifications` +
health terms. Works for the demo, but it's scoring living in the frontend and
will be reworked if you later adopt a champion. P1 would rather not, per the
"compute nothing but PTL, and even that prefers a P3 home" guidance.

**Spec (from plan U2), for whoever owns it:**
- Per-(player × table). Layer 1 baseline volatility (archetype from
  `classifications` + `avg_session_minutes` vs an archetype baseline +
  `sessions_last_30d` + promo signals) × Layer 2 table pressure (Fit mismatch +
  `seating_risk` + table band + `P_pred`).
- **Archetype-gated direction contract:** vulnerable archetypes (new /
  recreational) carry the signal and run **hot**; predators / grinders / anchors
  / colluders sit **cool**; promo_hunter spikes once qualified.
- Deterministic; emits `{code, detail, signals}` reason codes. PTL ∈ [0,1],
  1.0 = most likely to leave.

> **Q1:** Will you own `scoring/ptl.py`, or should P1 derive PTL UI-side?

---

## Ask 2 — pin the PTL validator targets to real entities

The plan's U2 validator names players (`P-150` "victim hot", `P-CA/CB/CC`
"colluders cool") that **don't exist in the shipped data**. Actual T-11 roster:

| Seat | Player | Archetype | Expected PTL |
|------|--------|-----------|--------------|
| cluster | P-198, P-199 | `cluster_member` | **cool** (coordinating, not leaving) |
| + 3rd seat | P-200 (`cluster_member`) | the seat that fills (Standard) / is held (FairPlay) | cool |
| grinders | P-171, P-172 | `grinder` | cool |

So at T-11 there is **no seated recreational/new "fish"** — the hot-PTL exemplar
the demo wants. The clean hot-vs-cool contrast that *does* exist in the data is
**P-104 (new)**: PTL **high at T-22** (beginner-unfriendly, seating-risk high) and
**low at T-8** (balanced) — this maps directly to your `seating_scores` and is a
solid validator target.

> **Q2:** What's the canonical hot-PTL exemplar for the seat-ring beat? Options:
> (a) keep it P-104 at T-22 vs T-8 (already in the data), and/or (b) seat a
> recreational player at T-11 so the flagged table also shows a fish at risk.
> Either way, please confirm the concrete `{player, table} → expected PTL band`
> pairs so U2's validator pins to real IDs, not the stale `P-150/P-CA` ones.

---

## Ask 3 — per-hour table health for live re-rank (affects U4/AE4)

`health_scores.json` is a single snapshot, so the pit-boss index (U4) ranks the
current state only. Live re-rank as the sim clock advances (R7/AE4) needs health
**per hour**. `rankTables()` already re-sorts whatever it's handed, so a series
drops in with no UI change.

> **Q3:** Can you freeze a per-hour health series (e.g. `health_by_hour.json`,
> `hours[].health_scores[]`)? Or is hour-by-hour re-rank the interactive moment
> that justifies revisiting the deferred FastAPI — i.e. scope it out of the
> static demo for now?

---

## TL;DR for P3

1. **Own PTL** as `scoring/ptl.py` (preferred) or tell P1 to derive it.
2. **Confirm the hot-PTL exemplar** and concrete validator `{player,table}→band`
   pairs (the plan's `P-150/P-CA` IDs aren't in the data).
3. **Per-hour health** series for live re-rank — ship it, or confirm re-rank is
   deferred.
