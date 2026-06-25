# PRD / work-order — liveness-aware routing + table-formation behavior

**Date:** 2026-06-25
**For:** Sargon (playsim owner) + his coding agent
**From:** P3 (scoring/evidence) — this checkout
**Status:** ready to pick up. The P3 side (changes #1/#2 below) is owned by P3 and
will be delivered behind an opt-in flag; **this doc specifies the two playsim-side
changes (#3, #4) and the one shared seam.**

---

## 0. Background — read these first

- `docs/learn/playsim-table-formation-gap.md` — the model limitation: the room could
  only **drain** (fixed roster, tables shrink/break but never form or grow). You've
  already shipped `--formation-mode forming` + continuous arrivals, which is the
  foundation this builds on.
- `docs/learn/playsim-room-routing-findings.md` — why Standard beats FairPlay so far
  (table-liveness/churn), and your own flagged next-scoring-question: *"whether
  fragility should consider `target_seats` / table mode, not only `seated_count /
  max_seats`."*

**The thesis we're testing:** FairPlay looks worse partly because (a) the router
**scores intentionally short-handed / forming tables as fragile** and steers players
away from them, (b) **Fit ignores table size** (some players prefer short-handed),
and (c) **no player will *start* a table** — everyone needs an existing dealable
seat. Fix those and a health-routing policy can finally *form and grow a fresh
healthy table* for a vulnerable player, which is its real-world mechanism.

---

## 1. The four changes and who owns them

| # | Change | Lives in | Owner |
|---|--------|----------|-------|
| 1 | **Frag-decouple** — `P_frag` treats a `forming` / sub-`target_seats` table as *not fragile* | `backend/scoring/health.py` | **P3** (delivered behind `liveness_aware` flag) |
| 2 | **Size-fit** — `Fit` gains a per-archetype table-size preference (keyed on `seated_count`/target) | `backend/scoring/seating.py` | **P3** |
| 3 | **Player propensity** — per-archetype willingness to *seed / accept a 1–2 person table* | `playsim/playsim/behavior.py` | **Sargon (this doc)** |
| 4 | **Liveness-aware FairPlay policy** — decides *when to seed/grow* a forming healthy table | `playsim/playsim/policies.py` | **Sargon (this doc)** |
| — | **Seam** — table dict carries `table_mode` + `target_seats` | `room.py` / `router_adapter.py` ↔ `health.py`/`seating.py` | **shared** |

#1+#4 are the **load-bearing pair**: #1 lets a forming table *score* well; #4 makes
FairPlay *use* it. Neither helps alone.

---

## 2. The seam (do this first, with P3) — `table_mode` + `target_seats`

P3's `p_frag`/`fit` need to know a table is *intentionally* short-handed, not
collapsing. So the table dict the adapter passes to the backend router gains two
fields:

- **`table_mode`** ∈ `{"forming", "active", "draining"}` — the room's current view of
  the table. `forming` = below quorum and trying to grow; `active` = dealable;
  `draining` = active but trending down / about to break.
- **`target_seats`** : `int` — the seat count the table is aiming for (e.g. 6), so
  fragility/occupancy can be judged against intent, not just `max_seats`.

**Playsim populates these** in `make_table_dict` (`playsim/playsim/router_adapter.py`)
from the live `_Table` state in `room.py` (you already track the lifecycle for
formation mode — surface it). **P3 consumes them** in `health.p_frag` and
`seating.fit`, gated by the `liveness_aware` flag (default off → frozen demo scores
unchanged → validators still pass).

> Agree the exact field names/semantics with P3 before building #1/#4 — this is the
> one piece neither side owns alone. Names above are the proposal; lock them in a
> 5-minute sync.

---

## 3. Change #3 — player new-table / short-table propensity (`behavior.py`)

**Goal:** model that *some* players will start or join a 1–2 person table, instead of
the current rule where every seeker needs an existing dealable seat (and break-reseek
*refuses* a near-empty table → balk, `room.py:355-357`).

**Where:** extend the `PlayerBehaviorPolicy` seam (`behavior.py`) — same pattern as
`DefaultBehaviorPolicy` / `FitAwareBehaviorPolicy` / `ReasonAwareBehaviorPolicy`. Add
a propensity hook the room loop consults when the only available option is a
forming/sub-quorum table, e.g.:

- `accept_forming_seat(offer) -> bool` and/or `will_seed_table(archetype, ...) -> bool`.
- Per-archetype propensity: aggressive/grinder *higher* (short-handed = more
  hands/hour, isolate weak players, less multiway variance); `recreational`/`new`
  *lower* (prefer fuller, social tables). Numbers are documented defaults,
  **illustrative until calibrated** — flag them as such (as you did for the
  fit-aware weights).

**Integration:** `room.py` should consult this when, under `--formation-mode
forming`, the seeker's best option is to seed an empty table or join a forming one.
Today `_route_seeker` (`room.py:344`) + the break-reseek `require_pair` guard force a
balk; the propensity hook is what lets the *willing* archetypes take that seat.

**Defaults / safety:** conservative defaults so that with the existing flags off, the
behavior is **byte-identical** to today. Deterministic (seeded; no RNG that breaks
replay — follow the existing pattern). Gate the new behavior on formation mode being
on.

---

## 4. Change #4 — liveness-aware FairPlay policy (`policies.py`)

**Goal:** a FairPlay variant that, when there's no good *dealable* healthy seat,
**seeds a fresh table or grows a forming one** toward a healthy composition — rather
than only ranking existing candidates (which is why plain FairPlay scatters into
breaks).

**Where:** new policy class in `policies.py` (e.g. `FairPlayLivenessPolicy`) behind a
new `--policy`/seam selector, **opt-in**, default off — the headline result must not
change silently. Reuse the `RouterAdapter` (the only module that imports
`backend/scoring`); don't re-implement ranking.

**Behavior:**
- Uses the **`liveness_aware` backend scoring** (P3's #1/#2) so forming/short-handed
  healthy tables now rank competitively and size-fit is in play.
- When the best dealable option is poor (predator-heavy / about to break), prefer
  **seeding a new table** or **joining a forming healthy one** for a vulnerable
  seeker, using `table_mode`/`target_seats` to find the growth path.
- **Must not collapse into Standard.** Explicitly: do *not* just prefer the fullest
  dealable table. If the policy degenerates to "most-full," it's wrong — add a test
  that it diverges from `StandardPolicy` on a seeded scenario.

**Hard guards (keep intact):**
- **Anti-circularity:** route on backend **predicted** health (`sessions=None` →
  `P_bleed=0`); realized chip-flow health stays eval-only; `room.py` must still not
  import `playsim/health.py` (the structural test must keep passing).
- **A/B invariant:** both arms consume the *same* seeded arrival stream; only the
  policy differs.
- **Determinism:** seeded, byte-identical replay for a given `(seed, horizon, policy,
  flags)`.

---

## 5. Acceptance criteria

1. **Opt-in, no silent change.** With the new flags off, the 2×2 and existing
   headline reproduce **byte-identically**. Frozen demo scoring (`data/derived/*.json`,
   pinned validators) is untouched — P3's flag defaults off.
2. **The experiment runs the full 2×2 × policies:** `{fixture-once, continuous}` ×
   `{none, forming}` × `{FairPlay-route, FairPlay-liveness}`, reporting vulnerable
   cohort **paid seat-hrs**, **breaks**, **wait-balks**, and the formation metrics
   (`forming_seat_count`, `formation_activation_count`, `table_reactivation_count`).
3. **The headline question is answered:** does liveness-aware routing + formation +
   propensity **narrow or flip** the Standard-vs-FairPlay gap, and *which lever*
   moved it (formation availability vs ranking vs propensity)?
4. **Tests:** new tests for the propensity hook, the liveness-aware policy (incl. the
   "does-not-collapse-into-Standard" assertion), and the `table_mode`/`target_seats`
   seam.
5. **Honest labeling:** still **illustrative, not validated** — uncalibrated
   parametric model. No retention *claim* without calibration; results are
   directional. Keep the caveat in any doc you update.

---

## 6. Suggested sequence

1. **Seam first** (with P3): lock `table_mode` + `target_seats`; P3 lands the
   `liveness_aware` scoring flag (#1/#2) reading them; you populate them in
   `make_table_dict`.
2. **#4** liveness-aware policy (the unlock) → re-run the 2×2 → measure.
3. **#3** propensity (sharpen *who* seeds/joins) → re-run → measure the delta.
4. Update `playsim-table-formation-gap.md` with the result table.

P3 (this checkout) will hand you the `liveness_aware` flag + the field-consumption
side; ping P3 when the seam names are locked.
