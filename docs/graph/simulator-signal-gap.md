# 11 — Simulator Signal Gap & Raw-Event Generator Spec

> **Hand-off doc for the `sim/` owner (P2).** Answers one question: *does the simulation lab produce the
> signals needed to model and derive the production graph schema ([10](10-production-graph-schema.md))?*
> This is a **scoped raw-event generator spec, not a mandate to build a full poker simulator.** Verdict
> below is split into three levels so you build only what your goal needs.

## TL;DR — three levels

| Level | Sufficient today? | What it needs |
|---|---|---|
| **1 · Demo narrative** (3 cases · lobby → pit-boss → sim → eval) | ✅ **Yes** | current fixtures; integrity signals stay as pre-baked fields |
| **2 · Production-shaped derivation of *core integrity*** (soft-play, outsider-targeting, chip-flow, *real* convergence) | ❌ No | **`hand_events.json`** (+ full seating history) |
| **3 · Full production graph** (all of doc 10, incl. identity/geo/AML) | ❌ No | `hand_events.json` **+** login/IP/location **+** payment/customer identity |

The lab is a **rolled-up findings-view generator**, not a raw-event generator. The integrity signals it
ships (`soft_play_delta`, `outsider_pressure_signal`, `bot_similarity_score`) are **asserted as fields**, not
computed from simulated play — so we can attach them as evidence, but we can't *prove they fire*.

It is **enough for demo table-health/routing and composition-based `ΔHealth`, but not enough for production
`Health(T)` derivation** — the discriminating `Health(T)` terms (`winnings_concentration`,
`recreational_loss_velocity`, true `P_bleed`) need play outcomes the lab doesn't simulate.

## What's actually derivable today (with caveats)

Earlier framing overclaimed this. Accurate status — most behavioral signals are **partial or asserted**, not
clean derivations, because `seat_events.json` is a *sparse Day-2 fixture* (only case players detailed), not a
full event log:

| Signal | Status today | Full derivation needs |
|---|---|---|
| Raw nodes/edges (`Account/Table/Session/Seating/Device` + `USES_DEVICE`, `SEATED_AT`…) | ✅ derivable | — |
| `SHARES_DEVICE` | ✅ derivable | — (`device_group_id`) |
| Composition-based **`ΔHealth`** (router seat-time) | ✅ derivable | roster + player fields only |
| `CO_SEATED_WITH` | 🟡 current-window co-presence only | **historical** seating events for a real "14 of 18 recent tables" rate; today it's a pre-baked rollup |
| `TIMING_CORRELATED` | 🟡 case events only | join times across the **full population history**, not just detailed case events |
| `JOIN_PATTERN_MATCHES` | 🟡 too sparse for production confidence | enough repeated join/lobby events to clear threshold |
| `MUTUALLY_AVOIDS` | ❌ (doc-10 pot-level signal) | hand/action data — "co-seat but avoid meaningful pots/aggression." *A weaker table-level variant (deliberately never co-seating to evade detection) is derivable from full seating history.* |
| `SOFT_PLAYS_AGAINST` | 🟡 asserted as `soft_play_delta` scalar | `hand_events` (within-cluster action asymmetry) |
| `TARGETS_OUTSIDER` | 🟡 asserted as `outsider_pressure_signal` bool | `hand_events` (aggression + net flow vs non-members) |
| `CHIP_FLOW_TO` | ❌ absent | `hand_events` (pot results) |
| `IMPACTS_TABLE` | 🟡 demo-approximated | hand-level winnings/losses + recreational-cohort outcomes + health deltas |
| Production **`Health(T)`** (`winnings_concentration`, `recreational_loss_velocity`, `P_bleed`) | ❌ | `hand_events` + cohort outcomes |
| Identity/geo/AML half (`SHARES_IP/PAYMENT`, `ENTITY_MATCHES`, `impossible_travel`, `vpn_proxy_signal`) | ❌ | Additions 2–3 |

## The two gaps (why production signals can't be derived)

**Gap 1 — no hand-level event stream.** `lifetime_hands` is a count; zero hand records. Every signal our
schema *derives from play* is currently a hand-set scalar/boolean.

**Gap 2 — no identity / network / payment substrate.** No `IP`, `Location`, or `PaymentInstrument`, and no
`Customer`/KYC spine (only `household_id` as a weak proxy).

Both are **explicit non-goals** in the lab's PRD §8 — a *deliberate* scope line, not a defect. This doc says
what crossing it takes, **if/when** we want the lab to validate the production detectors.

---

## Generator spec — synthetic, case-scoped additions

All synthetic (no real OSINT/KYC providers → consistent with the non-goal). Match the existing fixture style
(`schema_version`, `generated`, `fixture_note`, one list key). **Generate detail only for case-relevant
players/tables** — the "case players detailed, background summarized" pattern already in `seat_events.json`.
This keeps cardinality bounded (doc 10's anti-explosion rule).

### Prerequisite 0 — make `seat_events.json` the full seating log  *(cheapest unlock)*

The `CO_SEATED_WITH` / `TIMING_CORRELATED` / `JOIN_PATTERN_MATCHES` caveats all trace to one thing:
`seat_events` only details case players. Before any new file, **emit join/leave for the whole population over
the window** (background players can be terse). This alone moves co-seating/timing/join-pattern from "pre-baked
rollup" to *derivable* — no new schema, just fuller coverage.

### Addition 1 — `hand_events.json`  *(unlocks Level 2 — the highest-payoff addition)*

A minimal per-hand action + result stream, **only for tables/players in a seeded case**. This unlocks far more
than soft-play: it lets us recompute **VPIP/PFR/aggression**, the **table-health outcome terms**
(`winnings_concentration`, `recreational_loss_velocity`), and the behavioral collusion edges — all from real
play instead of asserted fields.

```jsonc
{
  "schema_version": "0.1.0",
  "fixture_note": "Case-scoped synthetic hands. NOT a full poker engine — only enough to derive signals.",
  "hands": [
    {
      "hand_id": "H-0001",
      "table_id": "T-11",
      "session_id": "SES-0101",
      "hour": 2, "offset_min": 14,        // or started_at
      "button_seat": 3,
      "players": ["P-198","P-199","P-200","P-150"],   // P-150 = outsider/victim
      "actions": [
        {"player_id":"P-198","street":"preflop","position":"BTN","action":"raise","amount_bb":3},
        {"player_id":"P-199","street":"preflop","position":"SB","action":"fold"},   // soft-play: B folds to A
        {"player_id":"P-200","street":"preflop","position":"BB","action":"call","amount_bb":3},
        {"player_id":"P-150","street":"preflop","position":"CO","action":"call","amount_bb":3}
      ],
      "all_in": false, "showdown": true, "hole_cards_known": false, "winner_id": "P-198",
      "result": { "pot_bb": 9, "rake_bb": 0.4, "net_by_player": {"P-198":6,"P-199":0,"P-200":-3,"P-150":-3} }
    }
  ]
}
```

**Field notes:** `button_seat`/`position` enable positional aggression metrics; `all_in`/`showdown`/
`hole_cards_known` support richer (optional) analysis; `result.net_by_player` + `pot_bb` (+ optional `rake_bb`)
drive chip-flow and winnings-concentration. **Derives:** `SOFT_PLAYS_AGAINST`, `TARGETS_OUTSIDER`,
`CHIP_FLOW_TO`, `MUTUALLY_AVOIDS` (pot-level), recomputed `VPIP/PFR/aggression`, and the `Health(T)` outcome
terms. **Minimum viable:** ~50–150 hands across the cluster table over the window — enough to clear threshold,
not a game engine.

### Addition 2 — `login_events.json` (+ small `ip_pool` / `location_pool`)  *(Level 3 — network/geo)*

```jsonc
{
  "schema_version": "0.1.0",
  "logins": [
    {"login_id":"L-0001","account_id":"P-198","session_id":"SES-0001",
     "hour":1,"offset_min":3,"device_id":"DG-001","ip_id":"IP-1001",
     "location":{"region":"TX-Houston","jurisdiction":"TX"},"vpn_flag":false}
  ]
}
```

**Derives:** `USES_IP`/`PLAYS_FROM_LOCATION` raw edges · `SHARES_IP` · `impossible_travel` · `vpn_proxy_signal`.
**Seed one adversarial hub on purpose:** a public-Wi-Fi / CGNAT `ip_id` shared by ~30 *unrelated* accounts — the
false-positive that validates doc 10's **`SHARES_IP` degree cap** (it must *not* become a ring). Cheap to seed,
strong eval.

### Addition 3 — identity layer: `customers.json` + `identity_candidates.json`  *(Level 3 — identity spine + ER)*

Two distinct things — don't conflate them:

```jsonc
// customers.json — GROUND TRUTH / KYC backbone. If two accounts share a customer_id, that IS the identity,
// not something the detector "recovers." Drives BELONGS_TO_CUSTOMER.
{ "customers": [ {"customer_id":"C-001","kyc_level":"verified","account_ids":["P-198","P-199"]} ] }

// identity_candidates.json — NOISY fuzzy features the ER layer FUSES into ENTITY_MATCHES for accounts that do
// NOT already share a known customer_id (the actual multi-accounting detection task).
{ "candidates": [
  {"account_a":"P-200","account_b":"P-198","features":{
     "device_overlap":0.0,"ip_subnet_match":0.6,"payment_token_similarity":0.0,
     "name_similarity":0.7,"login_time_overlap":0.5},"is_same_entity_truth":true} ] }
```

**`customers.json`** = the KYC spine (known, not detected). **`identity_candidates.json`** = the noisy signal ER
fuses into `ENTITY_MATCHES`, with `is_same_entity_truth` as the eval label. This is the honest separation of
*identity ground truth* from *entity resolution as a detection task*.

---

## Scoping guide — build only what the goal needs

| If the goal is… | Build | Skip |
|---|---|---|
| **Ship the capstone demo** (3 cases) | nothing — current fixtures suffice | all additions |
| **Honest *core integrity* derivation** (Level 2) | Prerequisite 0 + Addition 1 (`hand_events`) | 2 & 3 |
| **Production graph validation** (Level 3) | + Additions 2 (login/IP/location) and 3 (identity/payment) | — |

**Recommended order:** 0 → 1 → 2 → 3. Prerequisite 0 is nearly free; Addition 1 has the highest payoff (turns
the marquee cluster case from *asserted* to *derived* and unlocks the table-health outcome terms); 2 adds
geo/network + the degree-cap eval; 3 adds the identity spine + ER.

## Acceptance check — derive without the pre-baked field

Each addition is **done only when the loader/scorer re-derives the existing seeded verdicts without reading the
pre-baked fields:**

- Drop `soft_play_delta` → recompute `SOFT_PLAYS_AGAINST` from `hand_events`.
- Drop `outsider_pressure_signal` → recompute `TARGETS_OUTSIDER` from hand actions/results.
- Drop the cluster-level `co_seating.rate` → recompute from historical seating events (needs Prerequisite 0).
- Drop `bot_similarity_score`/known `customer_id` for the ER pair → recover `ENTITY_MATCHES` from
  `identity_candidates` features.
- **CASE-C still escalates; CASE-D and CASE-E remain monitor/benign; the high-degree shared-IP hub does NOT
  become a ring.**

That equivalence is the proof the substrate is real — and it doubles as the eval the PRD already wants
("true-risk ranks above false-positive traps").

> **One-liner for the hand-off:** the lab already *populates* and *demos* the graph. To make it *derive*
> core integrity instead of asserting it, do Prerequisite 0 + `hand_events.json` (Level 2). To exercise the
> full production graph, add the login/IP/location and identity/payment layers after that (Level 3). It stays
> synthetic and case-scoped — not a full poker simulator.
