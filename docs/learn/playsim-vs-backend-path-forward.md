# Path Forward — `playsim/` vs `backend/sim/`

**Date:** 2026-06-23 · **Decision owner:** single owner (per `CLAUDE.md`) · **Status:** recommendation

## TL;DR

**Adopt `playsim/` as the one poker-simulation engine. Deprecate `backend/sim/`** — keep its
design spec (`docs/superpowers/specs/2026-06-22-poker-outcome-sim-design.md`) and its `Engine`-seam
idea as reference, but stop generating data from it. **Do not touch `backend/scoring/` or
`backend/app/`** — those are not in the comparison and remain canonical.

The framing "playsim vs backend" is slightly off: `backend/` is three things, only one of which
overlaps playsim.

| `backend/` subdir | What it is | In this decision? |
|---|---|---|
| `backend/scoring/` | Canonical, frozen scoring engine — the source of truth | **No — keep.** Not duplicated by playsim. |
| `backend/app/` | Live FastAPI/SSE rescoring API over `scoring/` | **No — keep.** |
| `backend/sim/` | PokerKit poker-outcome generator (the Superpowers spec) | **Yes — deprecate.** |
| `playsim/` | PokerKit play-simulation engine + routing/health lab | **Yes — adopt.** |

So the real question is **`backend/sim/` vs `playsim/`** — two PokerKit-based archetype poker
simulators. playsim is a strict superset.

## Why playsim wins

**1. It covers all 10 canonical archetypes; `backend/sim` covers 7.**
`backend/scoring/classify.py` locks 10 archetypes (D7). playsim's `knobs.py` implements all 10 +
`solver_like`. `backend/sim` implements only the 7 *behavioral* ones and **explicitly defers** the
3 structural/integrity types (`cluster_member`, `shared_device_household`, `bot_like`) — exactly the
ones the integrity detector exists to catch.

**2. Its output is the Contract-1 feature bridge the scorer actually consumes.**
playsim's `features.py` emits `vpip, pfr, aggression_factor, avg_pot_bb, timing_regularity, net_bb,
soft_play_delta` — the fields `backend/scoring` reads. `backend/sim` writes `player_stats.json` that
still needs a "map into Contract-1" phase that was scoped out and never built.

**3. It produces the integrity signals; `backend/sim` produces none.**
Soft-play delta (member-vs-member EV), robotic timing regularity, target-weak predation **emerge
from play** in playsim. `backend/sim` is behavioral-only by design — it can't feed the detector.

**4. It is the demo spine.**
`CLAUDE.md`'s spine is `lobby → pit-boss → Standard-vs-FairPlay 8-hour simulation → eval`. That
middle link **is** playsim's `routing` loop (retained paid seat-time, realized health, multi-seed
averaging). `backend/sim` reloads stacks and keeps seating static — it structurally cannot answer
"did routing retain play-time?"

**5. It already has the integration seam.** `playsim/service.py` returns JSON-only dicts for the
frozen-fixtures-or-API pattern the lab uses everywhere else.

**Migration cost is ~zero.** Nothing in `frontend/` consumes either sim's output today (`data/sim/`
is referenced only by `backend/sim`'s own README). Deprecating `backend/sim` breaks no consumer.

## What `backend/sim` got right (preserve, don't delete the ideas)

- **The `Engine` protocol seam** (`engine/base.py`) — a clean PokerKit-vs-native abstraction. playsim
  isolates PokerKit inside `table.py` but doesn't formalize the protocol. If/when a native engine is
  wanted, lift this abstraction into playsim.
- **The skill% blend story** (strong/beginner policy mixed by `skill ∈ [0,1]`) is a more legible
  pedagogical model than playsim's knob-vectors. Worth keeping as the *explanation* of the skill dial.
- **The spec itself** is the origin story: "behavioral stats emerge from real hands, not hand-authored
  fields." Keep `docs/superpowers/specs/...` as the canonical write-up of that insight.

## Shared honest caveat (true of both)

Neither engine reliably demonstrates **skill → profit** at modest hand counts — cards and variance
dominate, and heuristic agents don't model opponents. `backend/sim` documents this; playsim works
around it with a small **zero-sum `skill_edge` EV transfer** (a labeled modeling *input*, with health
and seat-time still *derived*). The real fix for both is a trained brain — and **playsim already has
the seam** (`playsim.baselines.RLCardAgent`, the `solver_like` archetype). This is the V2 win that
removes the caveat.

## The path forward (phased)

**Phase 0 — Decide & commit (now).**
- Declare playsim the canonical poker-simulation engine. **Commit it** (it is currently untracked).
- Mark `backend/sim/` deprecated: add a `DEPRECATED.md` pointing to playsim; stop committing
  `data/sim/*` from it. Leave the code + spec in-tree as reference for one release, then remove.
- Pick playsim's home. Two clean options:
  - **(a) Promote to `backend/sim/`** — replace the old package; tidy under the `backend/` tree the
    spec/`CLAUDE.md` already reference. *(Recommended — one Python project, one import root.)*
  - **(b) Keep top-level `playsim/`** — preserves its self-contained Docker/Make/pyproject as a
    standalone lab. Choose this only if you want the sim shippable independently of `backend/`.
- Drop the stale "does not touch teammate-owned `sim/`, `scoring/`, `data/`" note in playsim's README —
  that was the old multi-owner framing `CLAUDE.md` retired. Single owner now; playsim *may* import
  `backend/scoring` directly (needed for Phase 3).

**Phase 1 — Wire playsim → scoring.**
Freeze `playsim.service.simulate(...)` features into the data layer and let `backend/scoring` consume
them, so the detector grades emergent stats (the "no grading its own homework" goal).

**Phase 2 — Demo spine.**
Freeze `simulate_routing(...)` (Standard-vs-FairPlay, multi-seed) to a derived JSON; build the
frontend comparison panel. Label it honestly: **V1 is a fixed counterfactual, not router proof.**

**Phase 3 — V3 router-in-the-loop (the strong backtest).**
playsim starts from a room snapshot, calls canonical `backend/scoring/router.py`, seats the cohort
where the router recommends, then scores realized health **independently** (first-principles chip
flow — never re-running `Health(T)`, to avoid circularity). Now allowed since single-owner removed the
import boundary.

**Phase 4 — V2 brains.**
Swap `RLCardAgent`/`solver_like` in behind the existing `act()` seam so the skill edge **emerges**
instead of being injected — retires the `skill_edge` caveat.

## One-line recommendation

> Use **playsim** as the single poker-simulation engine; it's a superset that covers all 10 canonical
> archetypes, emits the Contract-1 features and integrity signals the scorer consumes, and owns the
> Standard-vs-FairPlay routing loop that is the demo spine. Deprecate `backend/sim`, keeping its spec
> and `Engine` seam as reference. `backend/scoring` and `backend/app` are unaffected.
