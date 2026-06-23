# Data ask — full-population poker-sim run

> **To:** the poker-sim owner (`backend/sim/`, P2b/P2c).
> **From:** P3 / model-builder. **Scope:** *just* the simulation run — feature
> derivation and model variable-selection are downstream and handled by P3.

## The ask

Extend the existing poker simulator so it produces simulated play for the **full
122-player population** (`P-*`), not just the 12 `SIM-*` calibration agents it
covers today. Each lobby player should get a run of hands seeded by their
archetype, emitted in the same hand-history shape you already produce.

That's the whole ask. What we do with the output (derive features, cluster, fit
models) is P3's downstream work — you don't need to build any of that.

## Output contract

Same structure as today's `data/sim/hand_histories.json` (an `events` list + a
`results` list), but keyed to the population's `P-*` ids so it joins to
`data/players.json` on `player_id`:

- **`events`** — one row per action, with the fields you already emit:
  `player_id` (now `P-*`), `hand_id`, `table_id`, `street`, `kind`, `amount`,
  `to_call`, `pot`, `equity`, `voluntary`, `is_raise`, `is_bluff`.
- **`results`** — one row per hand: `player_id`, `hand_id`, `table_id`, `net`,
  `pot_bb`, `dealt_in`.

No new fields required — just the same emission over all 122 players.

## Requirements

- **Volume — scale to the player, no flat floor.** Generate
  **`min(lifetime_hands, CAP)`** hands per player, with `CAP ≈ 300–500` (enough
  headroom for the longest downstream trailing window). Rationale:
  - **No floor.** `lifetime_hands` varies enormously by archetype — `new` players
    have a *median of ~29* lifetime hands (max ~58), grinders have *~190k*. A flat
    "≥200" would falsify the low-volume archetypes (a `new` player with 200 hands
    isn't "new"). Low-volume players keep their true short history.
  - **Cap the high end.** Don't generate full careers — 12 grinders × ~190k hands
    is millions of hands for no benefit. A bounded *recent* window per player is
    enough and realistic (you observe recent play, not a months-long career).
  - **Short histories are fine, not a gap.** A trailing window longer than a
    player's available hands is simply **undefined → emit `null`/NaN**; downstream
    handles it as missing. **Do not fabricate extra sessions to hit a number.**
    (Multiple sessions/days of history *do* accumulate naturally for high-volume
    archetypes — that's expected; just don't force it on casuals.)
- **Seeding:** seed each player's run by their **archetype**, and make the whole
  run **deterministic / reproducible** (per-player seed) — CLAUDE.md hard rule.
- **Join key:** emit strictly by `P-*` id; no `SIM-*` ids in the output.

## One decision for you to make

`data/players.json` already carries static behavioral fields — `vpip`, `pfr`,
`aggression_factor`, `avg_pot_size_bb`. Does this run:

- **(a) Regenerate** those four from the simulated play — so one generative
  process is the source of truth for *all* behavioral fields (cleaner; nothing can
  disagree per player), **or**
- **(b) Leave them static** and only emit the raw hands alongside?

Either works for P3; we just need to know which, because (a) means the static
values in `players.json` get overwritten and (b) means they don't. **(a)** is the
cleaner default if it's not much extra work on your side.

---

*Downstream (P3, not part of this ask): deriving the honest feature pool from this
output and running it through IV → variable-clustering → stepwise selection in the
model builder.*
