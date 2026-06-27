# Playsim large-room simulation design

**Date:** 2026-06-25
**Status:** implemented as a generated playsim-only fixture path; canonical demo
fixtures remain unchanged. Reviewed on 2026-06-25 after the first large-room
benchmark run; results are useful but still illustrative.

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

For the recommended repeatable policy comparison, use the large-room sweep
command. It generates the fixture if needed, runs the same seeded arrival stream
through each policy arm, and writes both JSON and a short Markdown report:

```bash
.venv/bin/python -m playsim.cli large-room-sweep \
  --fixture-out out/large-room-data \
  --regenerate-fixture \
  --seeds 42,7,99 \
  --arrival-rates 40 \
  --horizon 480 \
  --samples 1 \
  --out-json out/large-room-sweep.json \
  --out-md out/large-room-sweep.md
```

Default policy arms:

- `standard`: most-full / liquidity baseline.
- `fairplay`: current backend FairPlay router.
- `fairplay_liveness`: opt-in liveness-aware FairPlay that can seed or grow a
  forming healthy table when no good dealable seat exists.

The sweep's north-star metric is **total paid seat-hours across all users and
tables**. It also reports **vulnerable paid seat-hours** as the FairPlay cohort
check, plus mechanism metrics such as breaks, wait-balks, no-good-existing-seat
count, forming seats, and formation activations.

For policy decisions, the sweep explorer also derives a tradeoff metric:
**vulnerable-seat-hours gained per total-seat-hour lost**. This is only meaningful
when a candidate policy improves vulnerable paid seat-hours while reducing total
paid seat-hours; it answers how much vulnerable cohort benefit the policy bought
for each room-wide paid seat-hour it gave up.

`large-room-sweep` defaults to `--samples 1` because this is still a hand-level
poker simulator. A 50-table, 8-hour, 3-seed, 3-policy run with higher equity
samples is expensive; use higher sample counts as sensitivity checks, not as the
day-to-day benchmark default.

## First benchmark results

Core Standard-vs-FairPlay benchmark, run from `playsim/`:

```bash
.venv/bin/python -m playsim.cli large-room-sweep \
  --fixture-out out/large-room-data \
  --regenerate-fixture \
  --seeds 42,7,99 \
  --arrival-rates 40 \
  --horizon 480 \
  --samples 1 \
  --policies standard,fairplay \
  --out-json out/large-room-benchmark-core-3seed-s1.json \
  --out-md out/large-room-benchmark-core-3seed-s1.md
```

3-seed mean result:

| policy | total paid seat-hours | vulnerable paid seat-hours | arrivals seated | arrival balks | breaks | wait balks | forming seats | formation activations | final active tables |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `standard` | 1599.23 | 42.33 | 285.3 | 21.3 | 0 | 0 | 15.0 | 19.3 | 48.3 |
| `fairplay` | 1571.34 | 41.91 | 282.7 | 24.0 | 0 | 0 | 16.3 | 24.0 | 49.3 |

Read this as an early benchmark, not a verdict. On these three seeds and this
low-sample setting, Standard still wins the room-economics north star:

- Standard beats FairPlay-route by **27.89 total paid seat-hours** (`+1.77%` vs
  FairPlay-route).
- Standard also slightly wins vulnerable paid seat-hours (`42.33` vs `41.91`).
- Both arms have zero breaks and zero wait-balks. That means the large-room
  fixture fixes the old one-way table-death artifact, but it does **not** by
  itself prove FairPlay wins.

Liveness-aware mechanism check, same fixture and seed 42 only:

| policy | total paid seat-hours | vulnerable paid seat-hours | arrivals seated | arrival balks | breaks | wait balks | forming seats | formation activations | final active tables |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `standard` | 1679.54 | 46.37 | 300 | 26 | 0 | 0 | 17 | 21 | 50 |
| `fairplay` | 1656.02 | 43.58 | 298 | 28 | 0 | 0 | 16 | 27 | 50 |
| `fairplay_liveness` | 1672.46 | 42.29 | 296 | 30 | 0 | 0 | 16 | 76 | 50 |

The liveness-aware arm changes the mechanism: it has many more formation
activations (`76` vs Standard's `21`) and narrows Standard's total-seat-time lead
on this seed (`0.42%` behind Standard vs FairPlay-route's `1.42%` behind). It did
not improve vulnerable paid seat-hours in this run. The next question is not
"did formation flip the result?" but "under what calibrated arrival, fit,
patience, and table-composition assumptions does liveness-aware FairPlay beat or
lose to Standard?"

## Review critique

What is strong about this approach:

- It keeps the small canonical fixture intact for readable scoring demos,
  regression tests, and docs anchors.
- It gives the room simulator enough liquidity to test formation/fill dynamics:
  50 tables, 35 active at hour 0, and a large unseated pool.
- It keeps arrivals deterministic and policy-independent, so Standard and
  FairPlay see the same demand stream.
- It avoids inventing synthetic players during the run; every arrival comes from
  the generated 1000-player roster.

What remains weak or illustrative:

- The archetype mix is hand-set, not calibrated to Hijack traffic.
- Relationships, devices, households, and clusters are empty, so this fixture is
  only a room-economics fixture. It is not an integrity or collusion benchmark.
- The initial table composition is random within archetype mix; it is not fitted
  to real table ecology or stake-specific behavior.
- Continuous arrivals draw without replacement from the unseated pool. That is
  clean for a single 8-hour room day, but it does not model repeat visits,
  players returning later, or a market larger than the generated roster.
- The simulator still cannot create table IDs beyond the 50-table roster. Empty
  tables can fill, but the room capacity is fixed.
- Full large-room sweeps are slow because every table still plays hand-by-hand
  poker with equity evaluation. For large Monte Carlo economics, this may need a
  faster event-level layer later; for now, keep large-room playsim benchmarks
  small and explicit.

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

The large-room sweep intentionally defaults to `continuous`. `fixture-once` is
still available in `room-sim`, but it is not the right default for this economics
question because it means "every currently unseated fixture player arrives once"
rather than "demand arrives at a market rate."

## What this does not solve yet

- It does not create tables beyond the 50-table roster during the run.
- It does not draw players with replacement.
- It does not model repeat daily visits by the same player.
- It does not calibrate the 1000-player archetype mix to real Hijack traffic.

Those are valid next steps, but this gets the simulator into the right scale regime
for the current table-formation and liveness-aware routing work.
