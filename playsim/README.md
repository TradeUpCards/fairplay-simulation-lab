# playsim — FairPlay play-simulation engine

Archetype agents that **actually play** No-Limit Hold'em on the
[PokerKit](https://github.com/uoftcprg/pokerkit) engine, so the signals our
detector watches — vpip, pfr, aggression, soft-play, robotic timing — **emerge
from play** instead of being typed in. Seeded and **byte-for-byte replayable**.

This is the engine specified in [`docs/archetype-play-profiles.md`](../docs/archetype-play-profiles.md)
and [`docs/learn/poker-sim-walkthrough.html`](../docs/learn/poker-sim-walkthrough.html).
playsim does **not** perform scoring itself — structured risk scoring lives in
`backend/scoring/`. The room-scale FairPlay routing policy *can* call backend
`scoring`/`router` at **decision time** (via `playsim/router_adapter.py`, the one
cross-package seam); realized chip-flow health stays playsim-side and
evaluation-only. (The legacy `backend/sim/` is deprecated; `playsim` supersedes it.)

> **Where this sits in the AI decision** ([`docs/learn/ai-hand-generation-decision.md`](../docs/learn/ai-hand-generation-decision.md)):
> these are **seeded-brain agents** — the deterministic substrate that powers
> the health/routing backtest and feeds the integrity detector. The LLM is *not*
> in this loop; it only explains the resulting evidence.

## Why an engine (not hand-set stats)

Today the generator *writes* each player's stats. Here an agent plays hands in
character and the stats are **measured** from how it played. That makes the
simulation a genuine test of the detector — it can't read back a field it was
handed ("the detector grading its own homework"). This is the **integrity loop**;
the same engine, run as a controlled Standard-vs-FairPlay experiment, is the
**health/routing loop**.

## Setup

> **Prerequisite — Python 3.12.** PokerKit requires Python **<3.14**. If your
> default `python3` is 3.14, install 3.12 (`brew install python@3.12`) — the
> `Makefile` and `Dockerfile` already target it. The **Docker path needs nothing
> but Docker** and is the most reliable.

**Local (Make does everything):**

```bash
make install     # 3.12 venv + deps + editable install   (one time)
make tables      # list demo tables + archetypes
make run         # play the cluster case → out/sim.db + out/features.json
make routing     # ★ Standard-vs-FairPlay: does routing improve table health?
make replay      # prove the run is byte-identical (determinism)
make test        # full test suite
```

**Docker (zero local Python):**

```bash
docker compose run --rm playsim run     --table case_c --hands 500 --seed 42 --db /data/sim.db
docker compose run --rm playsim routing --hands 600 --seed 42
docker compose run --rm playsim replay  --table case_c --hands 500 --seed 42
docker compose run --rm playsim population \
  --data-root /fixture --seed 42 --cap 400 \
  --out /data/playsim_hand_histories.json.gz \
  --features /data/sim_player_features.json.gz \
  --compact
# artifacts persist to ./out/
```

### The commands

| Command | What it does |
|---|---|
| `run --table T` | play a table, print the calibration report, write db/phh/features |
| `routing` | **the health loop (fixed rosters)** — Standard vs FairPlay, reports ΔHealth |
| `room-sim` | **the closed-loop room A/B** — seekers arrive over a horizon, a policy seats them, writes `room_sim_*`/`room_metrics_*`. Add `--behavior fit-aware` or `--behavior reason-aware`, plus `--debug-trace`. See `docs/learn/playsim-room-simulator-guide.html` |
| `health --table T` | play a table out (persistent stacks) and score its health |
| `population` | simulate `data/players.json` + `data/table_roster.json` into playsim-native hand JSON |
| `large-room-fixture` | generate a playsim-only 50-table / 1000-player data root for room-economics experiments |
| `large-room-sweep` | generate/reuse the large-room fixture, compare policy arms, and write JSON/Markdown results |
| `replay --table T` | re-run a seed twice and assert byte-identical (determinism) |
| `calibrate` | tune `postflop_aggression` until realized AF ≈ targets |
| `tables` | list demo tables and archetypes |

> **Room simulator (current focus).** The closed-loop, per-hand, multi-table room A/B (`room-sim`)
> compares table-routing *policies* (most-full / random / FairPlay router) over a shared seeded
> arrival stream, with a swappable `PlayerBehaviorPolicy` for leave/accept/re-seek. Start with the
> team guide (`docs/learn/playsim-room-simulator-guide.html`); the findings and the behavioral-model
> spec live in `docs/learn/playsim-room-routing-findings.md` and
> `docs/brainstorms/2026-06-24-behavioral-fidelity-fit-model-requirements.md`.

```bash
python -m playsim.cli run --table case_c --hands 500 --seed 42 \
    --db out/sim.db --phh out/hands.json --features out/features.json
python -m playsim.cli routing --hands 600 --seed 42
```

## What you get

A calibration report (realized vs. archetype target):

```
   player  archetype          vpip(r/t)   pfr(r/t)    AF(r/t)    timing  soft   net_bb
      198  cluster_member     0.39/0.30   0.26/0.23   2.37/2.15  0.69   -0.35   -1308.0
       62  healthy_anchor     0.38/0.28   0.21/0.18   1.79/1.88  0.67   +0.00   +1350.0
```

Plus three artifacts:
- **`--db`** SQLite (`runs`, `players`, `features`, `hands`) — queryable, replayable.
- **`--phh`** PHH-shaped hand histories (interoperate with the PHH ecosystem).
- **`--features`** the Contract-1 player features the scoring engine consumes.

## Population fixture runs

`population` is the Day-2 fixture path. It reads:

- `data/players.json` for player rows and `lifetime_hands`.
- `data/derived/classifications.json` for each player's archetype.
- `data/table_roster.json` for hour-0 seating.

Each seated player's hand target is `min(lifetime_hands, --cap)`. The runner
uses quota-leave: once a player reaches their target, they leave the table and
the remaining seated players continue until their own quota or until the table
breaks. This prevents low-volume players from being over-dealt while preserving
deterministic hand histories.

Full Docker run:

```bash
docker compose run --rm playsim population \
  --data-root /fixture \
  --seed 42 \
  --cap 400 \
  --out /data/playsim_hand_histories.json \
  --features /data/sim_player_features.json
```

For CI or artifact handoff, prefer gzip plus compact JSON:

```bash
docker compose run --rm playsim population \
  --data-root /fixture --seed 42 --cap 400 \
  --out /data/playsim_hand_histories.json.gz \
  --features /data/sim_player_features.json.gz \
  --compact
```

The output is a playsim-native corpus with top-level `meta`, `tables`, `hands`,
`player_index`, and `features`. `.gz` paths are compressed automatically; without
gzip, `--compact` still removes pretty-print whitespace.

Current fixture limitation: `table_roster.json` seats only the hour-0 players.
Players not seated there are not simulated yet, and a high-quota player can end
early if their table breaks before backfill exists.

For room-economics experiments, generate a larger playsim-only fixture instead of
mutating the canonical demo data:

```bash
python -m playsim.cli large-room-fixture \
  --out out/large-room-data \
  --players 1000 \
  --tables 50 \
  --active-tables 35

python -m playsim.cli room-sim \
  --data-root out/large-room-data \
  --horizon 480 \
  --arrival-mode continuous \
  --arrival-rate-per-hour 40 \
  --formation-mode forming \
  --behavior formation-aware \
  --liveness \
  --out-dir out/large-room-run
```

For a repeatable large-room policy comparison, prefer:

```bash
python -m playsim.cli large-room-sweep \
  --fixture-out out/large-room-data \
  --regenerate-fixture \
  --seeds 42,7,99 \
  --arrival-rates 40 \
  --horizon 480 \
  --out-json out/large-room-sweep.json \
  --out-md out/large-room-sweep.md
```

`fixture-once` remains the historical small-fixture replay mode. For large-room
economics, prefer rate-based `continuous` arrivals against the generated pool. See
`docs/learn/playsim-large-room-simulation.md`.

### The two loops

The same engine serves two validation loops (see
[`docs/learn/ai-hand-generation-decision.md`](../docs/learn/ai-hand-generation-decision.md) §4):

- **Integrity loop** (`run`) — does the detector *catch* bad behavior? Signals
  like soft-play and the bot's robotic timing emerge from play.
- **Health/routing loop** (`routing`) — does the router's seating retain more
  **paid seat-time**? The vulnerable cohort is seated either with skilled
  extractors (Standard) or among recreational peers (FairPlay) under matched
  seeds; players **log off** when their session (tilt-shortened by losses) runs
  out. The **north star is retained paid seat-time** — raw hands are just a
  throughput proxy (a table can churn hands by busting players fast):

```
  Standard vs FairPlay routing  (12 seeds avg)
                                 Standard   FairPlay
  ★ Paid seat-hours (cohort)         0.57       0.91
    Avg casual session (min)         11.4       18.2
    Health score                     28.6       71.8
    Rec loss velocity (bb/100)     1716.0      195.6
  ▶ Paid seat-time retained: +0.34 hrs (+60%)   ·   ΔHealth +43.1
```

> ⚠ **Circularity guardrail:** health is computed from first-principles chip flow
> (who won / lost / busted), **not** from re-running the scoring engine's
> `Health(T)`. That independence is what makes the comparison a real test.

> **Skill-edge model (honest note):** heuristic agents alone don't reliably win
> chips off weaker players (cards + variance dominate), so the engine applies a
> small **zero-sum per-hand skill-EV transfer** (`skill_edge`, a real bb/100
> quantity) so the predation→decay signal isn't buried in noise. It's a
> behavioral *input*; health/seat-time stay *derived*. A trained solver brain
> (`playsim.baselines`, V2) would make the edge emerge instead. Per-seed results
> are noisy (individual fish run hot/cold); the headline averages over seeds —
> the *population* effect FairPlay actually claims.

## Tapping in from a UI or API

`playsim/service.py` is the integration seam — one function returns a
JSON-serializable dict, no engine objects leak out:

```python
from playsim.service import simulate, simulate_routing

simulate("case_c", hands=500, seed=42)                  # integrity view + features
simulate("routing_standard", hands=600, persist=True)   # + health block
simulate_routing(hands=600, seed=42)                    # Standard-vs-FairPlay ΔHealth
```

Two integration modes:

1. **Frozen fixtures (recommended).** A batch job runs `simulate(...)` offline and
   commits the JSON; the frontend reads it statically. Deterministic, no runtime
   dependency, matches the lab's freeze-and-replay ethos — the demo can't break.
2. **On-demand API.** Wrap `service` in a thin HTTP route:

```python
# api.py  —  uvicorn api:app
from fastapi import FastAPI
from playsim.service import simulate, simulate_routing, list_tables

app = FastAPI()
app.get("/tables")(list_tables)

@app.get("/simulate/{table}")
def run(table: str, hands: int = 500, seed: int = 42, persist: bool = False):
    return simulate(table, hands=hands, seed=seed, persist=persist)

@app.get("/routing")
def routing(hands: int = 600, seed: int = 42):
    return simulate_routing(hands=hands, seed=seed)
```

Because runs are seeded, `GET /simulate/case_c?seed=42` is a pure function of its
query params — cache it forever. The scoring engine and pit-boss UI consume the
`features` block (Contract 1); a sim/health panel consumes `health` + `calibration`.

## Architecture

```
roster ──► runner ──► table (PokerKit referee) ──► HandRecords
                          │                              │
              archetype agent (one policy,        features.aggregate
              ten knob-sets) decides              (vpip/pfr/AF/timing/soft-play)
                          │                              │
              equity (preflop %ile + MC)          store / phh / features.json
```

- **`knobs.py`** — the ten archetypes (+ `solver_like`) as knob vectors with
  empirical targets from the 122-player fixture.
- **`agent.py`** — one parameterized policy; knobs bias every decision. Integrity
  layers: cluster soft-play, predator target-weak, bot determinism+flat timing.
- **`table.py`** — one hand on PokerKit; **we** control the deck (seeded) so it's
  reproducible; PokerKit enforces legality.
- **`runner.py`** — seeded session, rotates the button, aggregates features.
  `persist_stacks=True` carries chips over → bust dynamics (the health loop).
- **`features.py`** — the Contract-1 bridge (emergent signals).
- **`health.py`** — realized table health + the Standard-vs-FairPlay comparison.
- **`calibrate.py`** — the AF tuning loop (writes `calibration.json`).
- **`store.py` / `phh.py`** — SQLite + PHH export.
- **`service.py`** — the JSON API surface for a UI / HTTP layer.

## V1 / V2

- **V1 (this):** FairPlay archetype agents + PokerKit. Done.
- **V2:** stronger baseline brains for a *solver-like grinder* / strong regular.
  - Built-in now: the **`solver_like`** archetype (high-skill, balanced) — use
    `Player(id, "solver_like")` or the `solver_bench` table.
  - External: **`playsim.baselines.RLCardAgent`** adapts a trained
    [RLCard](https://rlcard.org/) CFR/RL agent under the same `act()` interface
    (`pip install "rlcard[torch]"`). PokerKit stays the referee; RLCard supplies
    the decision. OpenSpiel can be wired the same way.

## Calibration status (honest)

vpip, pfr, and timing_regularity calibrate **by construction** (looseness ≈ vpip,
pf_aggression ≈ pfr; the bot's flat timing reads ~1.0). **`aggression_factor`** is
tuned by the `calibrate` loop, which writes `calibration.json` (overlaid on the
knob defaults). After calibration most archetypes land close:

```
  new 0.93/0.89 · recreational 1.20/1.18 · household 1.55/1.55 · cluster 2.18/2.15
  bot_like 2.19/2.05 · anchor 1.73/1.88 · grinder 2.44/2.69 · predator 3.86/4.30
  (realized / target)
```

The **highest-aggression extreme** (solver-like AF 2.8, and predator 4.3) can hit
a **6-max multiway ceiling** — when a tight aggressor folds out preflop or can't
raise (capped/all-in), it can't generate enough bet/raise events to push AF to
the very top. That's a structural limit of heuristic play at a full table, not a
bug; the loop gets them as close as the policy allows and the report shows the
gap. Re-run any time with `make calibrate`.

## Determinism & responsible use

Every run is seeded end-to-end (deck + agent decisions), so `(table, seed, hands,
samples)` reproduces exactly — `replay` asserts it. These agents play **synthetic
chips in a sandbox** so the detector can be tested; this is **not** a tool for
real-money play, RTA, or actual collusion (see `CLAUDE.md` non-goals).
