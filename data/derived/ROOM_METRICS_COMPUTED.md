# `room_metrics_*_computed.json` — computed reference (NOT the demo fixtures)

**These are reference artifacts, not the demo's headline data.** The demo reads the
hand-authored `data/room_metrics_{standard,fairplay}.json` (`generated:
static-fixture-day2`), which encode the scripted Day-2 spine (P-104 → T-8, T-22
suppressed, cluster P-200 held at T-11, etc.). **Those are untouched.** The frontend
still binds them.

## What these are

The output of the room-sim CLI run that produced the table-formation result, frozen
here as evidence behind `docs/learn/playsim-table-formation-gap.md`:

```bash
PYTHONIOENCODING=utf-8 python -m playsim.cli room-sim \
  --seeds 42,7,99 --horizon 480 \
  --arrival-mode continuous --formation-mode forming \
  --out-dir out/promote
```

- `room_metrics_fairplay_computed.json` — `policy: fairplay_route`
- `room_metrics_standard_computed.json` — `policy: standard` (most-full)

They share the v1 `{meta, hours}` shape (identical hour-field keys to the headline
fixtures), so they could be swapped in, but their `meta` is generic computed
provenance (`generated: playsim-room-sim`, `schema_version: 0.2.0-derived`) with no
narrative `fixture_note`, and `reward_fee_ratio` is `0.0` (not modeled in the MVP).

## What they show

Room-wide cumulative paid seat-time at hour 8 (the `room_metrics` view):

| | hour-8 cumulative paid seat-min | winner |
|---|---|---|
| `fairplay` | 27,146 | **FairPlay** |
| `standard` | 26,629 | (+1.9%) |

The CLI's vulnerable-player view for the same run: standard **10.24** vs fairplay
**10.467** seat-hours (**+2.2%**, `routing_helped=True`).

## Caveats

- **Single (master) seed.** Each `room_metrics_*` file is the canonical **seed-42**
  run. The seed-stable 3-seed mean (fairplay 10.76 vs most-full 10.69, +0.65%) lives
  in the comparison harness, not in these files — see the doc.
- **Illustrative, not validated.** Seeded and reproducible, but uncalibrated synthetic
  output. Never quote as a retention *claim*. See `docs/learn/playsim-calibration-data.md`.
