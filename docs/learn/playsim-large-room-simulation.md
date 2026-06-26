# Playsim large-room simulation design

**Date:** 2026-06-25
**Status:** implemented as a generated playsim-only fixture path; canonical demo
fixtures remain unchanged.

## Why this exists

The original room-sim fixture is intentionally small: 12 tables, 68 hour-0 seated
players, and about 54 unseated classified players. That is useful for replayable
debugging and explaining the mechanism, but it is too small for table-formation
economics. With such a small finite pool, both `fixture-once` and `continuous`
mostly answer "how does this tiny room drain?" rather than "can policies form,
fill, break, and refill tables over an 8-hour session?"

The large-room path creates a separate fixture root with:

- 50 tables
- 35 active tables at hour 0
- 1000 generated players using the existing playsim archetypes
- 15 empty tables available for future formation
- enough unseated demand that some players may never join during an 8-hour run

This should be the default shape for room-economics experiments. The canonical
`data/players.json` and `data/table_roster.json` remain the scoring/demo fixture.

## How to generate it

From `playsim/`:

```bash
.venv/bin/python -m playsim.cli large-room-fixture \
  --out out/large-room-data \
  --seed 42 \
  --players 1000 \
  --tables 50 \
  --active-tables 35
```

The command writes a self-contained data root:

```text
out/large-room-data/
  players.json
  table_roster.json
  relationships.json
  devices.json
  derived/classifications.json
```

Then run room-sim against that generated root:

```bash
.venv/bin/python -m playsim.cli room-sim \
  --data-root out/large-room-data \
  --horizon 480 \
  --arrival-mode continuous \
  --arrival-rate-per-hour 40 \
  --formation-mode forming \
  --behavior formation-aware \
  --liveness \
  --out-dir out/large-room-run
```

## Arrival-mode decision

For the small canonical fixture, `fixture-once` remains useful because it is the
historical reproducibility baseline: every unseated fixture player arrives once.
It should stay available for regression and for comparing against old findings.

For large-room economics, `continuous` should be the primary arrival mode. It
answers the better product question: given a market demand rate, how do routing
policies affect paid seat-time, breaks, wait-balks, and table formation? With a
1000-player pool, continuous arrivals no longer exhaust the whole room by default.

So the recommended framing is:

- `fixture-once`: legacy/debug baseline for small fixture replay.
- `continuous`: primary large-room economics mode.
- replacement/replenishing arrivals: future work if we need multiple sessions per
  player or a market larger than the generated player pool.

We do not need to remove `fixture-once`, but we should stop treating the old 12-table
fixture-once result as the main FairPlay economics result.

## What this does not solve yet

- It does not create tables beyond the 50-table roster during the run.
- It does not draw players with replacement.
- It does not model repeat daily visits by the same player.
- It does not calibrate the 1000-player archetype mix to real Hijack traffic.

Those are valid next steps, but this gets the simulator into the right scale regime
for the current table-formation and liveness-aware routing work.
