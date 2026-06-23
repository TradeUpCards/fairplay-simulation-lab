# Design — Poker Outcome Simulator

**Date:** 2026-06-22
**Status:** Design — approved shape, pending spec review
**Branch:** `feat/poker-outcome-sim`

---

## 1. Purpose

A **standalone, deterministic No-Limit Texas Hold'em simulator** that generates poker data by mapping
each player **archetype to an agent** whose decision quality is tuned by a **skill percentage** (learner
≈ 10%, professional ≈ 100%) plus archetype **style**. Running many hands across tables yields varied,
realistic outcomes — full **hand histories** plus **per-player stats** rolled up from actual play.

The point: behavioral features (`vpip`, `pfr`, `aggression_factor`, …) **emerge from real hands** instead
of being hand-authored, which is higher data integrity and ties each stat back to its inputs.

## 2. Locked decisions

| # | Decision | Choice |
|---|---|---|
| Role | How the data is used | **Standalone hand simulator** first; mapping into the repo's Contract-1 schemas is a later phase. |
| Output | What "outcomes" means | **Both** — full hand histories AND per-player/table stats rolled up from them. |
| Fidelity | Engine realism | **Full NL Hold'em cash** — real 5-of-7 evaluation, all four streets, blinds + button rotation, all-ins + side pots, 6- and 9-max. |
| Skill model | How agents decide | **① Tool-based strong/weak policy blend** — agents call tools; skill% mixes a solid and a beginner policy; archetype adds style knobs. |
| Engine | Build vs buy | **PokerKit now, behind a swappable `Engine` seam.** A future native engine is a one-adapter drop-in. |
| Determinism | Reproducibility | One master seed in the sim layer; byte-identical outputs for a given config+seed. |

## 3. Architecture & module layout

A new top-level `sim/` package. The `Engine` interface sits between the driver and PokerKit; everything
above the seam is engine-agnostic.

```
sim/run.py            entrypoint: config → outputs
  └─ sim/driver.py    drives tables/hands; owns the seeded deck; emits log events
       ├─ Engine (seam, sim/engine/base.py)     interface + shared types only
       │    └─ PokerKitEngine (sim/engine/pokerkit_engine.py)  ← only file importing pokerkit
       │       … NativeEngine (future)            ← same interface, drop-in
       ├─ sim/agents/  archetype · policy · tools  (consume DecisionContext only)
       └─ sim/log.py + sim/stats.py
```

**Modules:**
- `sim/engine/base.py` — the **seam**: an `Engine` protocol + shared types `Card`, `Action`
  (`fold` / `check_call` / `raise_to(amount)`), `DecisionContext`, `HandResult`. No PokerKit knowledge.
- `sim/engine/pokerkit_engine.py` — `PokerKitEngine(Engine)`: the only module importing `pokerkit`;
  translates to/from `create_state` / `deal_hole` / `deal_board` / `fold` / `check_or_call` /
  `complete_bet_or_raise_to`, reading `actor_index` / `stacks` / `bets` / `total_pot_amount` /
  `pots` / `payoffs`.
- `sim/agents/archetype.py` — archetype config (skill% + style knobs); `policy.py` — strong / beginner /
  blend; `tools.py` — `hand_equity`, `pot_odds`, `position`. **Engine-agnostic** (consume `DecisionContext`).
- `sim/deck.py` — seeded shuffle + deal order (determinism owner; deck handed to the engine to deal).
- `sim/driver.py` — orchestrates tables/hands/streets/actions; the core loop.
- `sim/log.py` — hand-history events; `sim/stats.py` — pure rollup to behavioral features.
- `sim/run.py` — entrypoint; `sim/config/` — master seed + table/archetype config;
  `sim/requirements.txt` — `pokerkit`, `treys`.
- **Outputs → `data/sim/`**: `hand_histories.json`, `player_stats.json` — kept separate from the locked
  Contract-1 `data/` files.

**Boundaries doing the work:** (1) the `Engine` seam — swap PokerKit→native via one adapter; (2)
`DecisionContext` — the agent/skill layer is testable in complete isolation (feed a context, assert an action).

## 4. The skill model

**Inputs — `DecisionContext`:** hole cards, board, `to_call`, `pot`, `stack`, `position`, `n_opponents`,
`big_blind`, `street`.

**Tools (pure reads over the context):**
- `hand_equity(hole, board, n_opponents, rng)` — Monte-Carlo: sample opponent hands + remaining board from
  the unseen deck, evaluate via treys, return win prob ∈ [0,1]. Seeded → deterministic; sample count is a config knob.
- `pot_odds(pot, to_call)` — breakeven equity to call.
- `position(ctx)` — early / middle / late / blind bucket.

**Two reference policies:**
- **Strong** — equity-vs-odds + position aware: value-bet when `equity ≫ pot_odds`, call near breakeven,
  fold when behind, pot-fraction sizing, position-aware preflop ranges. A solid TAG, not GTO.
- **Beginner** — classic leaks: plays absolute hand strength not equity, calls too much, chases draws
  ignoring odds, limps, rarely folds top pair, ignores position.

**Skill dial:** `skill ∈ [0,1]`. Per decision, with probability `skill` take the **strong** action, else the
**beginner** one (seeded RNG). The "%" reads literally — plays correctly ~`skill` of the time.

**Archetype = skill% + style knobs** (`aggression`, `tightness` → preflop range width, `bluff_freq`, `tilt`),
applied on top of the chosen base action. The knobs make each archetype's *emergent* stats land on target:

| Archetype | skill | style | → emergent stats |
|---|---|---|---|
| new (learner) | ~0.10 | loose, timid | low pfr, erratic |
| recreational | ~0.35 | loose-passive | high vpip, low pfr, low aggr |
| regular | ~0.60 | balanced | mid everything |
| grinder | ~0.85 | tight-aggressive | low vpip, high aggr |
| aggressive_predatory | ~0.90 | loose-aggressive | high vpip+pfr+aggr |
| healthy_anchor | ~0.75 | solid-stable | healthy mid-high |
| promo_hunter | ~0.30 | min-play | few hands, short |

**Scope boundary:** the engine produces **behavioral** features only. It does **not** produce
structural/integrity fields (`cluster_id`, `device_group_id`, `soft_play_delta`, `bot_similarity_score`, …) —
those are coordination/device signals, not playstyle outcomes. Integrity archetypes (`cluster_member`,
`shared_device_household`, `bot_like`) map to a behavioral baseline here; collusion/soft-play is a **future
extension**, not v1.

## 5. Data flow

**Config in → data out.** `sim/config/` holds the master seed + a run config: tables (stakes, max seats,
starting stacks), seat assignment (archetype per seat), and run length (hands per table).

**Loop hierarchy:**
```
run(config, master_seed)
└─ per table   (seed = derive(master_seed, table_index))   ← independently reproducible
   └─ per hand (button rotates; fresh seeded deck)
      └─ per street (preflop → flop → turn → river)
         └─ per action:  ctx ← engine state
                         action ← agent.decide(ctx)        # tools + skill blend
                         engine.apply(action)
                         log.event(hand, street, actor, action, ctx)
      └─ on terminal:  log.result(payoffs, winners, final board, pot)
```

**Cash-game modeling choices:**
- **Reload to buy-in between hands** (e.g., top up to 100bb) — it's a cash game; no tournament-style busting.
- **v1 = static seating**: each player sits one table for the whole run = one "session" per player.
  Table-hopping / mid-run join-leave is deferred (it belongs to the `seat_events` mapping phase).

**Stat rollup (`sim/stats.py`, pure over the event log):**
- `vpip` = voluntarily-put-money-in-pot hands ÷ hands dealt in
- `pfr` = preflop-raise hands ÷ hands dealt in
- `aggression_factor` = (bets + raises) ÷ calls, postflop
- `avg_pot_size_bb` = mean pot (in BB) of contested hands
- `lifetime_hands`, `net_chips`, win-rate (bb/100)
- time fields (`avg_session_minutes`, `sessions_last_30d`) via a simple hands→time assumption (table
  `hands_per_hour`) — an explicit modeling approximation.

**Outputs → `data/sim/`:**
- `hand_histories.json` — per hand: id, table, button, blinds, seats (player_id, archetype, stack), full
  action sequence, board, pots, payoffs.
- `player_stats.json` — per player: rolled-up behavioral features + net/win-rate + the archetype + skill/style
  used (provenance — every stat traces to its inputs).

## 6. Determinism

- **One master seed** in `sim/config/`, owned by the sim layer (DECISIONS D1).
- **Derived, independent RNG streams**: per-table seed = `derive(master_seed, table_index)`; within a hand,
  **separate** streams for *dealing* vs *agent decisions/equity* so changing the equity sample count never
  shifts the cards. Every random draw (shuffle, Monte-Carlo equity, skill Bernoulli) pulls from these.
- **Engine-independent by construction:** the deck is built in `sim/deck.py` and handed to the engine to deal
  (PokerKit in manual-dealing mode, no auto-deal). The seam gives a future native engine the same guarantee.
- **Guarantee = acceptance test:** same config + seed → byte-identical outputs (run twice, diff is empty).
- **Build-step framing:** the sim is a seeded generation step that writes frozen JSON which gets committed;
  the demo consumes frozen data and never runs the sim live.

## 7. Error handling

- Missing `pokerkit` / `treys` → friendly "pip install -r sim/requirements.txt", not a traceback.
- Invalid config (seats > max, unknown archetype, non-positive blinds) → validated at load, fail fast with a
  clear message.
- **Illegal-action guard:** before applying, the agent's action is checked against the engine's legal actions
  (`can_*`) and **clamped** (raise below min → min or call; raise above stack → all-in), with a counter
  logged — a policy bug cannot crash a long run.

## 8. Testing (TDD, adversarial)

- **Spike / adapter gate (first):** one seeded hand end-to-end — confirm every decision is injected and a seed
  reproduces identical cards; assert payoffs for a scripted line; assert the adapter reads a multi-way all-in's
  side pots correctly. This is the PokerKit go/no-go.
- **Tools:** `pot_odds` math; `hand_equity` sanity (AA vs one random ≈ 0.85; made nuts on river = 1.0;
  deterministic given seed).
- **Policy/skill (no engine):** `skill=1.0` → always strong; `skill=0.0` → always beginner; style knobs shift
  the action as expected.
- **Stat rollup:** a hand-crafted event log rolls up to known `vpip` / `pfr` / aggression.
- **Emergent-behavior calibration (the meaningful one):** a modest run — assert each archetype's emergent stats
  land in expected bands and that **higher skill → higher win-rate** over many hands.
- **Determinism:** full run twice, same seed → identical outputs.

## 9. Scope / non-goals

- **In scope:** the `Engine` seam + `PokerKitEngine`; the tool-based skill model + archetype configs; the
  driver; the seeded deck; hand-history log; stat rollup; `data/sim/` outputs; the test suite above.
- **Out of scope (v1):** mapping outputs into the locked Contract-1 schemas (`players.json` / `sessions.json`
  / `seat_events.json`); structural/integrity fields; collusion / soft-play; table-hopping / mid-run movement;
  a native engine (the seam makes it a later drop-in); any UI; LLM agents (the tool seam keeps that door open).

## 10. Dependencies & how to run

```bash
pip install -r sim/requirements.txt     # pokerkit, treys
python -m sim.run --config sim/config/default.json
# → writes data/sim/hand_histories.json + data/sim/player_stats.json
```

## 11. File list (all new)

`sim/engine/base.py`, `sim/engine/pokerkit_engine.py`, `sim/agents/archetype.py`, `sim/agents/policy.py`,
`sim/agents/tools.py`, `sim/deck.py`, `sim/driver.py`, `sim/log.py`, `sim/stats.py`, `sim/run.py`,
`sim/config/` (master seed + a sample run config), `sim/requirements.txt`, the test suite under `sim/tests/`,
and outputs `data/sim/`. No existing files edited (sole prior change this branch: `.gitignore` += `.superpowers/`).

## 12. As-built realism pass + known limitations

After the first end-to-end run produced unrealistic, over-aggressive poker (≈365 bb average pots, no bet
sizes in the log), a realism pass was added on top of the v1 skill model:

- **Preflop range gate (`tools.preflop_strength`, Chen formula).** A hand is played preflop only if its
  absolute strength clears a threshold set by the archetype's `tightness` **and position** (`_preflop_threshold`).
  Unplayable hands fold without even computing equity (also a large speedup). This is what finally makes the
  `tightness` and `position` knobs matter, and pulls vpip into a realistic, differentiated range.
- **Open-raise, don't limp.** Playable hands in an unraised pot open-raise (good players raise) — fixing
  near-zero `pfr` and making the aggressive archetypes actually aggressive.
- **Postflop discipline.** Bets are ~½-pot and both policies fold more to **big bets** on later streets, so the
  *typical* pot stays small (median ≈ 11 bb).
- **Contested-pot metric.** `avg_pot_size_bb` is averaged over hands the player *contested* (not every dealt
  hand), matching the real field; `hands_contested` is reported alongside.
- **Auditable log.** Each event records `amount`, `to_call`, `pot`, `equity`, and `is_bluff` (bluff-raises are
  tagged at the policy layer via `Action.tag`), so value-vs-bluff and sizing are visible.

**Known limitations (documented, deferred):**
- **Mean pot > realistic.** The *median* pot is realistic (≈11 bb) but the *mean* (~80 bb) is inflated by
  occasional all-in pots — players still stack off in big pots more than ideal.
- **Skill ≠ profit at modest N.** `net_chips` is variance-dominated over a few hundred hands, and the agents
  don't adapt to opponent type (they bluff into calling-stations, which is -EV). Demonstrating skill→win-rate
  needs large-N **and** opponent-aware play.
- **No opponent modeling.** `hand_equity` is computed vs. *uniformly random* opponents; agents react to the
  betting situation (`to_call`, `n_opponents`) but don't model opponent ranges/tendencies.
- **Position** influences only the preflop range gate, not postflop lines.
- **Seat-time actions not modeled.** Quit / Leave / Join (table-hopping) remain out of scope — they belong to
  the deferred Contract-1 `seat_events` mapping phase.
