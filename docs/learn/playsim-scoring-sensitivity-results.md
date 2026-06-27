# Playsim scoring sensitivity results

**Status:** experimental playsim-only sweep, generated 2026-06-27.

This sweep asks whether FairPlay-liveness is losing room-wide seat-time because
the current scorer gives the wrong signal about short-handed, forming, or
liveness-sensitive tables. It does **not** change canonical backend scoring.
Each variant temporarily patches scorer constants inside the analysis process,
runs the same seeded room simulation, then restores the defaults.

## How to rerun

From `playsim/`:

```bash
.venv/bin/python analysis/scoring_sensitivity_sweep.py \
  --regenerate-fixture \
  --out-json out/scoring-sensitivity-sweep.json \
  --out-md out/scoring-sensitivity-sweep.md \
  --out-html out/scoring-sensitivity-explorer.html
```

Open:

```text
playsim/out/scoring-sensitivity-explorer.html
```

The run uses 50 tables, 35 active starting tables, 1000 players, seeds
`42,7,99`, arrival rates `20,40` per hour, 480-minute horizon, and
`formation-aware` behavior.

## Variants tested

- `baseline`: current liveness-aware scorer and FairPlay-liveness thresholds.
- `router_liveness_heavy`: router rank weights shift toward health/liveness.
- `frag_soft`: occupancy fragility penalty reduced from 30 to 10.
- `short_active_grace`: 2-player active tables get a 50% fragility discount.
- `short_fit_neutral`: removes short-table fit penalties for new/recreational
  players and softens predator/grinder short-table bonuses.
- `loose_liveness`: lowers FairPlay-liveness health floors for dealable/forming
  tables.

## First read

FairPlay-liveness still does **not** beat Standard on the north-star economics
metric in this sweep: every variant has negative mean total paid seat-hour delta
at both tested arrival rates.

At `20/hr`, several variants improve vulnerable paid seat-hours while losing
total paid seat-hours. The best tradeoff is `short_fit_neutral`:

| variant | rate/hr | total delta | vulnerable delta | tradeoff |
|---|---:|---:|---:|---:|
| `short_fit_neutral` | 20 | -2.60 hrs | +2.15 hrs | 0.83x |
| `baseline` | 20 | -2.83 hrs | +1.96 hrs | 0.69x |
| `router_liveness_heavy` | 20 | -7.28 hrs | +3.92 hrs | 0.54x |
| `short_active_grace` | 20 | -3.90 hrs | +2.01 hrs | 0.52x |

At `40/hr`, none of the variants produces a reliable vulnerable-seat-hour gain.
That suggests the scoring issue is most visible in tighter/intermediate demand,
not in the higher-arrival-rate regime tested here.

## Interpretation

The useful signal is not "change scoring so FairPlay wins." The useful signal is
that **short-table fit treatment is the most promising scoring hypothesis so far**:
it improves the vulnerable cohort with the smallest total seat-hour cost in this
grid.

The variants that soften fragility or lower liveness thresholds create more
formation activity, but they also lose substantially more total room throughput.
That is evidence against simply making thin/forming tables look healthier.

Recommended next scoring discussion:

1. Keep total paid seat-hours as the economics north star.
2. Keep vulnerable paid seat-hours as the FairPlay cohort check.
3. Treat `short_fit_neutral` as the leading scoring hypothesis to review.
4. Do not relax fragility broadly without a stronger mechanism, because the first
   sweep shows it can make the throughput tradeoff worse.
5. Add any future scoring change as an opt-in variant first, then rerun this
   dashboard before touching canonical defaults.
