# FairPlay Poker Outcome Simulator (`sim/`)

A standalone, **deterministic No-Limit Texas Hold'em simulator** that generates poker data by mapping each
player **archetype to an agent** whose decision quality is tuned by a **skill percentage** (learner ≈ 10%,
professional ≈ 100%) plus archetype **style**. Running many hands across tables produces hand histories and
per-player behavioral stats — the behavioral features (`vpip`, `pfr`, `aggression`, …) **emerge from real
play** instead of being hand-authored.

> Full design: [`docs/superpowers/specs/2026-06-22-poker-outcome-sim-design.md`](../docs/superpowers/specs/2026-06-22-poker-outcome-sim-design.md)
> · implementation plan: [`docs/superpowers/plans/2026-06-22-poker-outcome-sim.md`](../docs/superpowers/plans/2026-06-22-poker-outcome-sim.md)

## Quick start

```bash
# 1. set up the environment (first time only)
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows PowerShell  (macOS/Linux: source .venv/bin/activate)
pip install -r sim/requirements.txt

# 2. generate the data
python -m sim.run --config sim/config/default.json
#    -> writes data/sim/hand_histories.json + data/sim/player_stats.json

# 3. run the tests
python -m pytest sim/tests -q
```

## Outputs (`data/sim/`)

- **`player_stats.json`** — per player: `lifetime_hands`, `vpip`, `pfr`, `aggression_factor`,
  `avg_pot_size_bb` (over *contested* hands), `hands_contested`, `net_chips`, and the `archetype`
  (provenance — every stat traces to its inputs).
- **`hand_histories.json`** — `events` (every action: `street`, `kind`, `amount`, `to_call`, `pot`,
  `equity`, `voluntary`, `is_raise`, `is_bluff`) and `results` (per-seat `net` + `pot_bb`).

## Archetypes & knobs

Seven behavioral archetypes ([`agents/archetype.py`](agents/archetype.py)), each = **skill%** + style knobs
**aggression**, **tightness** (preflop range width), **bluff_freq**:

| Archetype | skill | leans |
|---|---|---|
| `new` | 0.10 | loose, timid |
| `recreational` | 0.35 | loose-passive |
| `regular` | 0.60 | balanced |
| `grinder` | 0.85 | tight-aggressive |
| `aggressive_predatory` | 0.90 | loose-aggressive |
| `healthy_anchor` | 0.75 | solid-stable |
| `promo_hunter` | 0.30 | minimal play |

## How a turn is decided

On its turn an agent sees a `DecisionContext` (hole, board, to_call, pot, stack, position, …) and:
1. **Preflop range gate** — plays a hand only if its Chen-formula strength clears a threshold set by
   `tightness` + position; unplayable hands fold without computing equity.
2. **Skill blend** — with probability `skill` it follows the **strong** policy, else the **beginner**
   (calling-station) policy.
3. **Style overlay** — `aggression` upgrades some calls to raises; `bluff_freq` turns some folds into
   (tagged) bluff-raises.

Decision **tools** ([`agents/tools.py`](agents/tools.py)): `hand_equity` (Monte-Carlo win prob via treys),
`pot_odds`, `position`, `preflop_strength` (Chen).

## Architecture

A swappable **`Engine` seam** keeps everything engine-agnostic:
- [`engine/base.py`](engine/base.py) — the `Engine` protocol + shared types (`Action`, `DecisionContext`, `HandResult`).
- [`engine/pokerkit_engine.py`](engine/pokerkit_engine.py) — the **only** module that imports `pokerkit`.
  A future native engine is a drop-in implementing the same protocol.
- [`deck.py`](deck.py) seeded deck · [`driver.py`](driver.py) hand loop · [`log.py`](log.py) event log ·
  [`stats.py`](stats.py) rollup · [`run.py`](run.py) entrypoint.

## Determinism

One **master seed** drives everything; per-table **dealing** and **decision** RNG streams are derived
separately (so changing `equity_samples` never changes which cards are dealt). Same config + seed →
byte-identical output (asserted by `tests/test_run_and_calibration.py`).

## Configuration ([`config/default.json`](config/default.json))

`master_seed`, `equity_samples`, `blinds`, `starting_stack`, `hands_per_table`, and `tables` (each with
`seats` mapping a `player_id` to an `archetype`).

## Known limitations

The *typical* pot is realistic (median ≈ 11 bb), but the **mean** is inflated by occasional all-ins; **skill
≠ profit** over a few hundred hands (variance + no opponent adaptation); equity is computed vs. *random*
opponents (no opponent modeling); position affects only the preflop gate; and **seat-time** (join/leave/quit)
is not modeled — that, plus mapping to the Contract-1 `seat_events.json`/`players.json` schemas, is the
deferred next phase.

---

**Note:** `sim/cases/` and `sim/counterfactual/` are **pre-existing P2 fixtures** (demo-case JSON +
counterfactual decision list) that predate this simulator — they are not part of this package.
