# P1 Integration Guide — Wiring the UI to P2 + P3

> **For:** P1 (Product + Review UX). **From:** P3 (Scoring + Evidence Engine).
> **Purpose:** what data exists, which file feeds which UI surface, and the one
> rule you cannot get wrong. Everything here is shipped and on disk today — no
> "coming soon".
>
> **The demo spine you own:** `lobby recommendation → pit-boss review/override →
> Standard-vs-FairPlay simulation → eval evidence`. Each link below maps to a
> file you read.

---

## 0. The 30-second mental model

There are two kinds of data file, and **mixing them up is the one mistake that
sinks the project:**

| Bucket | Files | Who may see it |
|---|---|---|
| 🟢 **Player-facing safe** | `data/derived/router_lobby.json` → `player_lobby` view **only** | the lobby / any screen a player sees |
| 🔴 **Operator-facing only** | everything else: `health_scores`, `integrity_scores`, `classifications`, `seating_scores`, the router's `operator_view`, all raw `data/*.json`, and `seeded_case_labels.json` | pit-boss console, case detail, eval panel — **never** a player screen |

> **The lobby must never show:** a numeric health/risk score, a player
> classification (archetype), a seating-risk level, or any
> "predator/integrity/cluster/collusion" language. The lobby shows **neutral
> badges + table facts only**. P3 already pre-filtered the `player_lobby` view to
> exactly the safe fields — **render that view as-is and you cannot leak.** Do
> not reconstruct the lobby from raw `table_roster.json` (it contains
> `style_volatility_label: "...Predatory-Mix"` and other operator language).

Two other rules that show up in copy you write:
- **Never state a player cheated, never recommend an automatic ban.** The
  product *recommends, explains, and lets a human decide.* Bands say "elevated
  for review," never "these players cheated."
- **Three separate lenses:** table-health ≠ integrity ≠ promo-abuse. A grinder
  is a *health* concern, not an integrity one; a household is *monitor*, not
  *escalate*. The scores already keep these apart — keep them apart in the UI.

---

## 1. Contracts at a glance

- **Contract 1 (P2):** the simulated room — `data/*.json` (players, roster,
  sessions, relationships, hourly metrics, the seeded answer key).
- **Contract 2 (P3):** scores + recommendations — `data/derived/*.json`
  (frozen, regenerable JSON you bind the UI to). **This is your primary feed.**
- **Contract 3 (evidence packet):** P4 defines, P3 produces — for the AI
  Investigator. Not needed for the lobby/pit-boss click path; wire later.
- **Contract 4 (UI state):** what you build.

**Determinism:** every `data/derived/*.json` is reproducible — same inputs →
byte-identical output. Regenerate any of them with
`python scripts/build_<score>.py`. A presenter can run the whole demo from these
static files. You never call Python live; you read JSON.

---

## 2. Which file feeds which screen

| UI surface (Contract 4) | Read this | View / key |
|---|---|---|
| **Player lobby** | `data/derived/router_lobby.json` | `routed[i].player_lobby[]` (🟢 safe) |
| **Pit-boss console — table list** | `data/derived/health_scores.json` | `health_scores[]` (band, terms, reason codes) |
| **Pit-boss console — routing view** | `data/derived/router_lobby.json` | `routed[i].operator_view[]` (full rank/score breakdown) |
| **Case detail — integrity** | `data/derived/integrity_scores.json` | `assessments[]` (band, signal families, **counter-evidence**) |
| **Case detail — players** | `data/derived/classifications.json` | `classifications[]` (archetype + reason codes) |
| **Case detail — seating recommendation** | `data/derived/seating_scores.json` | `seeking_players[].candidate_tables[]` |
| **Simulator comparison** | `data/room_metrics_standard.json` vs `data/room_metrics_fairplay.json` | `hours[]` KPI cards |
| **Eval panel** | `data/seeded_case_labels.json` + the score files | answer key vs computed |

---

## 3. Screen-by-screen wiring

### 3a. Player lobby 🟢

Read `router_lobby.json → routed[].player_lobby`. Each entry is already safe:

```json
{ "table_id": "T-1", "stakes": "0.25/0.50", "game_type": "NL Hold'em",
  "max_seats": 9, "seated_count": 8, "open_seats": 1, "pace_label": "moderate",
  "badge": "recommended", "badge_label": "Recommended for you" }
```

- Render `badge_label` as the chip text. The four badges:
  `recommended` → "Recommended for you" · `good_fit` → "Good fit" ·
  `available` → "Available" · (`hidden_gated` tables are **already absent** from
  `player_lobby` — a table under integrity review never appears here).
- Order is already rank-sorted (best first). Show table facts (`stakes`,
  `pace_label`, seats) — all neutral.
- **Do not** add health %, "risk", or skill labels to this screen.

> Demo beat (CASE-A): for P-104, T-8 shows **Recommended for you**, T-14 **Good
> fit**, T-22 **Available** (not promoted), and T-11 (cluster under review) is
> **not in the list at all**. That's the whole "routed to safety" story, visible
> with zero operator data.

### 3b. Pit-boss console — table health 🔴

Read `health_scores.json → health_scores[]`:

```json
{ "table_id": "T-22", "health": 38.0, "band": "beginner_unfriendly",
  "integrity_candidate": false,
  "terms": { "P_pred": 40.0, "P_frag": 22.0, "P_clus": 0.0, "P_bleed": 0.0 },
  "reason_codes": [ { "code": "predation_pressure",
    "detail": "Predation pressure 40/45 — skill-weighted aggressor load 2.0 against 0 recreational/new seat(s).",
    "signals": { "aggressor_weight": 2.0, "vulnerable": 0, "pressure": 2.0 } }, ... ] }
```

- Show `health` (0–100) + `band` as the headline. Bands: `healthy` (70–100) ·
  `fragile` (50–69) · `beginner_unfriendly` (30–49) · `collapsed` (0–29).
- The four `terms` are the penalty breakdown — a natural bar/stack viz
  (P_pred/P_frag/P_clus/P_bleed).
- **`integrity_candidate: true`** means a high-band cluster is seated → render a
  "surface to review queue" flag regardless of the number (T-11).
- **Render `reason_codes[].detail` verbatim** for the "why". Do not hand-write
  explanations — that's a PRD DoD rule (UI driven by computed reason codes).

### 3c. Case detail — integrity 🔴

Read `integrity_scores.json → assessments[]`. Each group (cluster / household /
overlap / bot account):

```json
{ "group_id": "CL-001", "group_kind": "cluster", "member_ids": ["P-198","P-199","P-200"],
  "band": "high", "convergence_count": 4, "recommended_action": "hold_for_pitboss_review",
  "signal_families": [ {"code":"device_link", "detail":"...", "signals":{...}}, ... ],
  "corroborating": [...], "counter_evidence": [...], "note": "..." }
```

- Bands: `low` · `neutral` · `high` · `manual_review` (the bot queue).
- `recommended_action` is the human action to offer: `monitor` ·
  `hold_for_pitboss_review` · `route_to_bot_review_queue`. **Offer it as a
  choice the operator confirms — never auto-execute, never "ban".**
- **You MUST render `counter_evidence` next to the finding.** This is a hard
  guardrail — the "no single signal is proof" story is visible, not hidden.
  - CL-001 (high): 4 `signal_families`, empty counter-evidence → recommend hold.
  - H-01 household (neutral): carries `household_counter_evidence` → "monitor
    only, do not escalate." **The false-positive trap is the demo's integrity
    moment — show why it's NOT escalated.**
  - OVL-001 (low): `legitimate_regular_counter_evidence` → benign overlap.
- `corroborating` = supporting context (not counted toward the band); show it
  secondary to the primary `signal_families`.

### 3d. Case detail — players & seating 🔴

- `classifications.json → classifications[]`: `{player_id, archetype,
  reason_codes[]}`. Use for the per-player archetype chip in the operator view
  (e.g. P-176 = `aggressive_predatory`). Render the reason-code `detail` for the
  "why this label".
- `seating_scores.json → seeking_players[].candidate_tables[]`: per player×table
  `fit`, `delta_health`, `seating_risk` (`low`/`medium`/`high`),
  `integrity_gated`, plus `table_health` / `table_band`. This is the "why P-104
  was routed away from T-22" panel — `seating_risk: "high"` + the reason codes.

### 3e. Simulator comparison (Standard vs FairPlay)

Read `room_metrics_standard.json` and `room_metrics_fairplay.json`, each
`hours[]` (hours 1–8). Each hour is a KPI snapshot:

```json
{ "hour": 1, "cumulative_paid_seat_time_minutes": 3900, "active_players": 69,
  "active_healthy_tables": 10, "new_player_retention_pct": 72,
  "avg_casual_session_length_minutes": 44, "early_table_breaks": 1,
  "projected_eod_paid_seat_time_minutes": 30200, "reward_fee_ratio": 0.27,
  "high_risk_seating_formations": 1, "hour_note": "..." }
```

- Drive the KPI cards / 8-hour trend lines from these fields. The story is the
  **divergence** between the two paths (FairPlay retains casuals, grows paid
  seat-time; Standard lets P-104 churn at T-22).
- `hour_note` gives the human caption per hour for free.

### 3f. Eval panel

`seeded_case_labels.json` is the **operator answer key** (7 cases, CASE-A…G):
each has `expected_category`, `expected_risk_lens`, `expected_seating_action`,
`is_false_positive_trap`, `eval_checks`, and `pit_boss_evidence_seed`. Show
"computed score vs expected" — e.g. CASE-C integrity computed `high` matches
expected `integrity_review`; CASE-E computed `neutral` matches "monitor, not
escalated". **Never expose this file in a player-facing path** — it's the answer
key.

---

## 4. The three mandatory demo cases → UI states

| Case | Entities | Lobby (player) | Pit-boss / case detail (operator) |
|---|---|---|---|
| **CASE-A** new player, bad table | P-104, T-22 (P-176/177), alt T-8 | T-8 "Recommended", T-22 "Available" (not promoted) | T-22 health **38** beginner_unfriendly; P-104 seating-risk **high** at T-22, **low** at T-8 |
| **CASE-C** true cluster | CL-001 (P-198/199/200), T-11 | T-11 **absent** (hard-gated) | CL-001 band **high**, 4 converging families, action **hold_for_pitboss_review** |
| **CASE-E** household FP trap | H-01 (P-192/193) | (no special lobby state) | H-01 band **neutral**, `household_counter_evidence` shown, action **monitor** — **must not escalate** |

The contrast between CASE-C (escalate) and CASE-E (don't) — both involving shared
devices — is the integrity-judgment centerpiece. The data already distinguishes
them; surface the **counter-evidence** to show *why*.

---

## 5. Reason codes — the "why" is data, not copy

Every score emits `reason_codes` (and integrity emits `signal_families` /
`counter_evidence`), each `{ code, detail, signals }`:
- `code` — stable key, safe for switch/icon logic.
- `detail` — operator-facing sentence; **render verbatim**.
- `signals` — the raw values behind it, for a tooltip/expandable.

This satisfies the PRD rule that important UI states are driven by computed
reason codes, not hand-written front-end text. If you find yourself typing an
explanation string, read it from `detail` instead.

---

## 6. Regenerating / gotchas

- Regenerate any feed: `python scripts/build_classifications.py` (and
  `build_integrity` / `build_health` / `build_seating` / `build_router`). Output
  is deterministic.
- **Join keys:** table ids are `T-<n>` (no leading zeros: T-1, T-3, …, T-22);
  player ids `P-<n>`. IDs are **not contiguous** — don't assume ranges.
- **`seating_scores` / `router_lobby` currently cover the demo seeking player
  P-104.** Add more by extending `SEEKING_PLAYERS` in the build scripts.
- **P_bleed is 0 across the static snapshot** by design (observed term; it lags
  composition). Don't treat a 0 as missing data.
- **Thresholds + band definitions** live in `docs/scoring-thresholds.md` — the
  single source of truth for every cutoff, if you need exact band boundaries for
  a legend.

---

## 7. Known drift to be aware of (so your deck matches the engine)

`docs/index.html` is the design narrative and has a few illustrative numbers that
**differ from the computed engine** — use the engine values for any live screen:
- §05 worked example shows Health 81/67 for T-8/T-14; the engine computes ~93
  (only T-22=38 is a pinned value). Ranks therefore differ (engine 60.5/56.1/26.3
  vs the doc's 55.2/44.2/13.0); **badge ordering is identical**.
- §04 shows ΔHealth ≈ −8 for P-104→T-22; the engine computes **+15** (table
  composition vs player-risk — the player danger lives in seating-risk = HIGH,
  not the ΔHealth sign). See `scoring-thresholds.md §4b`.
- The §05 T-11 card and a couple of stake labels are stale.

None of these affect the click path; they're flagged so a slide built from
`index.html` doesn't contradict a computed screen.

---

## 8. TypeScript types (`frontend/contract2.d.ts`)

Typed interfaces for every `data/derived/*.json` shape — import these instead of
`any`. They describe the data shape regardless of transport (file import now, or
an API later that serves identical shapes).

**The lobby type is structurally narrowed to enforce §0 at compile time.** Bind
player screens to `LobbyTable` — it has no `health`/`rank`/`seating_risk`/
`archetype` field, and every operator type is branded `OperatorOnly<…>`, so
passing operator data to a lobby component is a **compile error**:

```ts
function renderLobbyCard(t: LobbyTable) { /* ... */ }
renderLobbyCard(routed.player_lobby[0]);   // ✅
renderLobbyCard(routed.operator_view[0]);  // ❌ does not compile (TS2345)
```

Operator screens use `HealthScore` / `IntegrityAssessment` / `SeatingCandidate`
/ `RouterOperatorRow`. The `Contract2` interface bundles all five files.

---

**TL;DR:** bind the lobby to `router_lobby.json → player_lobby` (already safe),
bind every operator screen to the matching `data/derived/*.json`, render
`reason_codes[].detail` and `counter_evidence` verbatim, and never let an
operator field cross into a player screen. The data already enforces the lenses
and the separation — your job is to not undo them in the UI.
