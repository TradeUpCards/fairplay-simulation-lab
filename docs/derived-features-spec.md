# Derived-Features Spec — honest predictor expansion for the classification challenger

> **Status:** proposal / handoff to the poker-sim owners (P2b/P2c — Bram/Cleo).
> **Audience:** whoever owns `backend/sim/` + the Contract-1 `data/*.json` fixtures.
> **Author context:** written from the model-builder side (P3 challenger ①). The
> challenger currently trains on **9 numeric behavioral features** only
> (`ml/challenger.py:34`). This spec catalogs the *honest* features we could add,
> where each comes from, and how to produce them at population scale.

## Why this exists

The model builder's classification challenger is the "honest" foil to the rule
champion: it must earn class separation from **observable behavior**, never from
truth-adjacent stamps. Three candidate fields in `players.json`
(`bot_similarity_score`, `soft_play_delta`, `timing_regularity`) are **label
stamps** — e.g. every `bot_like` player has `bot_similarity_score == 0.870` and
`timing_regularity == 0.880` exactly (constant within the class). Adding them
would make rare classes trivially separable → circular. **They stay out.**

The legitimate way to grow past 9 features is **richer simulated behavior**, not
more stamps. PR #32's poker simulator (`backend/sim/`, `data/sim/*.json`) now
produces real per-action play, which is exactly the honest derivation surface.

## Sequencing — a hard dependency chain (do not reorder)

Variable generation is **downstream of the simulator**. There is nothing to
derive until the sim has produced per-player hands for the *full population*:

1. **Sim run (P2)** — seed each of the 122 `P-*` players with their archetype's
   policy; deal **N ≥ 200 hands** each (so the longest rolling window, 200, is
   well-defined). → per-player `hand_histories` + `results`.
2. **Variable generation (P2/P3)** — derive the ~45 honest features off step 1;
   emit a `{P-*: {feature: value}}` table joinable to `players.json`.
3. **Selection pipeline (model builder)** — IV screen → VarClus → stepwise on the
   wide pool from step 2.

Steps 1–2 gate step 3: the selection layer can be *scaffolded* against the
existing 9 features, but it has no real pool to act on until the sim run lands.

### Design questions the sim run must resolve
- **Source-of-truth reconciliation.** `players.json` already carries static
  `vpip`/`pfr`/`aggression_factor`/`avg_pot_size_bb`. Does the sim **regenerate**
  these from play (one consistent generative process for *all* behavioral
  features), or only **append** new columns alongside the static 9? Regenerating
  is cleaner — otherwise the static-9 and the sim-derived features may not cohere
  for the same player.
- **Hands per player** — fixed N, or proportional to `lifetime_hands`? (Rolling
  windows need N ≥ their longest window or they're undefined / NaN-imputed.)
- **Determinism** — per-player seed so the run is reproducible (CLAUDE.md rule).
- **Join key** — emit strictly by `P-*` id; no `SIM-*` namespace in the output.

## The catch (must be solved first)

The new sim data is **12 `SIM-*` agents on 4 tables** — a *calibration* run, not a
per-player feature table. The lobby population is **122 `P-*` players**. To use any
of the features below as predictors, the simulator must be **run seeded per
population player by that player's archetype**, emitting one feature row per
`P-*` id, joinable to `data/players.json`. Until that join exists, this is a
data-generation task, not a model-builder change.

Secondary caveat: **N per archetype is tiny** (some archetypes have 1–2 agents).
Honest features won't help a class with one training example held out (LOO).

## Source data (what's available today)

| Source | Grain | Time axis | Key fields |
|---|---|---|---|
| `data/sim/hand_histories.json` → `events` (6,702) | one action | **hand index** (`T1-H0000…`, ordered; no wall-clock) | `kind` (fold/check_call/raise_to), `street`, `amount`, `to_call`, `pot`, `equity`, `voluntary`, `is_raise`, `is_bluff` |
| `data/sim/hand_histories.json` → `results` (3,600) | one hand | hand index | `net`, `pot_bb`, `dealt_in` |
| `data/sessions.json` (74) | one session | **wall-clock** (`start_hour`/`end_hour`, 8h sim) | `duration_min`, `paid_seat_time_intervals`, `exit_reason`, `status` |
| `data/seat_events.json` (192) | join/leave | **wall-clock** (`hour` + `offset_min`) | `event_type`, `table_id` |

## Honesty classification (load-bearing)

- ✅ **Observable** — derivable by watching the table: action frequencies,
  outcomes (net/pot), session timing, seat events. *These are fair game.*
- ⚠️ **Semi-observable** — uses each player's own hole-card `equity`, which an
  outside observer wouldn't see. Usable as a *discipline* descriptor but flag it.
- ❌ **Leaky** — `is_bluff` is the policy's internal truth flag (the agent *knows*
  it bluffed). Same category as the integrity stamps. **Exclude.**

---

## Catalog of derivable features

### A. Outcome / results axis  (✅ observable)
- **`win_pct`** — hands won / hands contested
- **`net_bb_per_100`** — win rate (the poker-standard skill metric)
- **`net_stdev`** — variance / swinginess (recreational 75–90 vs grinder ~35 in the 12-agent sample)
- **`showdown_win_pct` (W$SD)** and **`wtsd`** (went-to-showdown rate)
- **`big_pot_freq`** — share of hands with `pot_bb` above a threshold
- **`allin_freq`**

### B. Action-style axis  (✅ observable)
- **`fold_pct`** — tightness (recreational ~0.11–0.16 vs grinder ~0.69–0.81)
- **`threebet_pct`**, **`fourbet_pct`** — preflop reraise aggression
- **`cbet_pct`** (flop raise as preflop aggressor), **`turn_barrel_pct`**, **`river_barrel_pct`**
- **`fold_to_cbet`**, **`fold_to_threebet`**
- **`checkraise_pct`**
- **`postflop_aggression`** — aggression *by street* (finer than the 9's single `aggression_factor`)
- **`limp_pct` / `open_raise_pct`**

### C. Discipline / equity axis  (⚠️ semi-observable — flag in UI)
- **`avg_equity_invested`** — mean hole-card equity when voluntarily committing chips
- **`equity_realization`** — net won vs equity put in (over/under-realizing)
- **`calls_light_freq`** — calls with low equity *and* poor pot odds (station signal)
- ~~`bluff_rate` (`is_bluff`)~~ — ❌ leaky, do not use

### D. Rolling / trajectory  (hand-index axis, ✅ observable)

The **multi-timespan family.** Each core metric is computed over a ladder of
trailing hand-windows — **`{20, 50, 100, 200}`** — short = reactive/tilt,
long ≈ stable baseline (the sim gives ~300 hands/player, so a 200-window is
most of a history). Per core metric that's 4 columns:

- **`rolling_vpip_{20,50,100,200}`** — looseness trajectory
- **`rolling_aggr_{20,50,100,200}`** — aggression trajectory
- **`rolling_net_{20,50,100,200}`** — recent-form / win-rate trajectory
- **`tilt_delta`** — short-window aggression − long-window baseline (the *gap* is
  the signal, not either level)
- **`betsize_escalation`** — monotonic growth in bet sizing across the session

⚠️ **Multicollinearity:** the four windows of one metric are highly correlated
with each other *and* with the lifetime value. For a WoE/logistic scorecard that's
tolerable (it won't break the fit) but adds little independent signal and burns
degrees of freedom. Recommendation: **emit all four windows** so the analyst can
*choose* in the binner, but expect to keep only 1–2 windows per metric in the
final model. `tilt_delta` (the short−long *difference*) is usually worth more than
any single window level.

### E. Velocity / acceleration  (the time-derivative features)
*Hand-index axis (✅ observable):*
- **`aggression_velocity`** — Δ aggression per 10 hands
- **`steam_after_loss`** — change in VPIP/bet-size in the K hands *after* a big loss (tilt/chase signature)

*Wall-clock axis from sessions/seat_events (✅ observable):*
- **`sessions_per_hour`** — session-frequency velocity over the 8h window
- **`seat_time_accel`** — is paid seat-time per session rising hour-over-hour?
- **`table_hop_rate`** — joins per hour / distinct tables per window
- **`reentry_velocity`** — re-buy / re-entry cadence
- **`chase_index`** — session length *after* a losing session vs after a winning one

### F. Seat-time / room behavior  (sessions + seat_events, ✅ observable)
- **`avg_paid_seat_time`**, **`paid_seat_ratio`**
- **`hit_and_run_freq`** — short-session / early-exit rate (`exit_reason`)
- **`table_diversity`** — distinct tables per window
- **`co_seating_concentration`** — repeatedly seated with the same players
  ⚠️ *integrity-adjacent (collusion lens) — keep for the integrity score, not the
  archetype challenger, to avoid blurring health vs integrity.*

---

## Master decision table

**This table is about *candidate-pool membership*, not model membership.** We do
**not** hand-pick which attributes go into the logistic regression. We make every
*honest* attribute **available** to the selection pipeline (IV screen → VarClus →
stepwise — see next section), and the statistics decide what survives. So the only
per-attribute call is: *honest enough for the pool, or does it leak?*

Legend: ✅ In pool (already in model) · 🟢 In pool · 🟡 In pool · 🟠 Conditional
(semi-leaky / wrong lens — gated out by default) · 🔴 Excluded from pool (stamp /
id / leaky). The 🟢/🟡 split is only a rough *signal-strength prior* for reviewing
results — it does **not** decide inclusion; stepwise does.

| Attribute | Source | Decision |
|---|---|---|
| `registered_days_ago`, `lifetime_hands`, `avg_session_minutes`, `sessions_last_30d`, `vpip`, `pfr`, `aggression_factor`, `avg_pot_size_bb`, `promo_redemptions_30d` | players.json | ✅ Keep (the 9) |
| `promo_eligible` | players.json | 🟠 Hold (weak/redundant) |
| `player_id`, `display_name` | players.json | 🔴 Exclude (id) |
| `device_group_id`, `household_id`, `cluster_id` | players.json | 🔴 Exclude (structural, sparse, integrity lens) |
| `bot_similarity_score`, `soft_play_delta`, `timing_regularity` | players.json | 🔴 Exclude (label stamps) |
| `net_bb_per_100`, `win_pct`, `net_stdev`, `wtsd` | results | 🟢 Add P1 |
| `showdown_win_pct`, `hands_contested`, `big_pot_freq`, `allin_freq` | results / player_stats | 🟡 Add P2 |
| `fold_pct`, `postflop_aggression`, `threebet_pct` | events | 🟢 Add P1 |
| `cbet_pct`, `turn_barrel_pct`, `river_barrel_pct`, `fold_to_cbet`, `fold_to_threebet`, `fourbet_pct`, `checkraise_pct`, `limp_pct`, `open_raise_pct` | events | 🟡 Add P2 |
| `avg_equity_invested`, `equity_realization`, `calls_light_freq` | events (equity) | 🟠 Hold (semi-leaky) |
| `bluff_rate` | events (`is_bluff`) | 🔴 Exclude (truth flag) |
| `rolling_vpip_{20,50,100,200}`, `rolling_aggr_{20,50,100,200}`, `rolling_net_{20,50,100,200}` | events (hand index) | 🟡 Add P2 (emit all; keep 1–2 each) |
| `tilt_delta`, `betsize_escalation` | events (hand index) | 🟡 Add P2 |
| `steam_after_loss` | events (hand index) | 🟢 Add P1 |
| `aggression_velocity` | events (hand index) | 🟡 Add P2 |
| `sessions_per_hour`, `seat_time_accel`, `table_hop_rate`, `reentry_velocity`, `chase_index` | sessions / seat_events | 🟡 Add P2 |
| `avg_paid_seat_time`, `paid_seat_ratio`, `hit_and_run_freq`, `table_diversity` | sessions / seat_events | 🟡 Add P2 |
| `co_seating_concentration` | seat_events | 🟠 Hold (integrity lens only) |

### Pool tally
- **In the candidate pool (honest):** the 9 + ~45 derived ≈ **~54 candidates**
  (incl. the 12 rolling columns).
- 🟠 **Conditional (gated out by default):** ~7 — the equity-based discipline
  metrics and `co_seating_concentration` (integrity lens). Available behind an
  explicit "include semi-observable" / "integrity lens" switch, never default.
- 🔴 **Excluded from the pool entirely:** 9 — 3 stamps, 3 structural ids, 2 player
  ids, 1 bluff-flag. These must **never** reach stepwise; a stamp would be selected
  and silently leak the label.

## Selection pipeline (this is what decides the model)

The wide candidate pool flows through a standard scorecard variable-reduction
pipeline. **This is the real build implication** — the model builder today only
has manual in/out checkboxes + IV; it has no clustering or stepwise. To use a
~54-candidate pool we need:

1. **Fine/coarse binning + IV** *(exists)* — `ml/scorecard.py` already produces
   WoE/IV per variable. Use IV as the first screen (drop `IV < ~0.02` — useless).
2. **Variable clustering (VarClus-style)** *(to build)* — cluster the surviving
   candidates by correlation (e.g. hierarchical on |corr|, or a PCA-split VarClus),
   and keep the best representative per cluster by **lowest `1 − R²` ratio** (the
   SAS rule) or simply highest IV within the cluster. This is what dissolves the
   `rolling_*_{20,50,100,200}` redundancy automatically — the four windows land in
   one cluster and only the most predictive survives.
3. **Stepwise logistic** *(to build)* — forward/backward selection on the cluster
   representatives, entry/stay by p-value or AIC, so the final model self-limits
   its degree count (no manual "keep under 20" rule needed — stepwise stops when
   marginal lift dies). Honest evaluation stays **leave-one-out** (`combine_loo`).

Net: the analyst's job shifts from *picking variables* to *reviewing and overriding
the pipeline's picks* (force-in / force-out, adjust the coarse bins) — which is the
authentic FICO scorecard workflow, and keeps the human-in-the-loop control surface.

## Deliverable contract (what the model builder needs back)

A JSON file keyed by `P-*` id, one row per population player, e.g.:

```json
{ "P-100": { "fold_pct": 0.34, "postflop_aggression": 0.58,
             "net_bb_per_100": -1.2, "net_stdev": 79.8, "wtsd": 0.41,
             "threebet_pct": 0.07 }, ... }
```

`ml/service.py::_df()` would left-join this onto `players.json` by `player_id`;
the new columns then appear as toggleable variables in the scorecard editor with
the same WoE/IV binning as the existing 9.

## Out of scope / guardrails
- No real player data, no real RTA — synthetic only (CLAUDE.md hard rule).
- Integrity-adjacent features (`co_seating_concentration`, anything using
  `is_bluff`/`equity` as a "caught" signal) belong to the **integrity** lens, not
  the archetype challenger. Keep health ≠ integrity separation intact.
- Determinism: the per-population sim run must be seeded and reproducible.
