# 12 — Fixture ↔ Graph Vocabulary Mapping (Contract-1 → Contract-3)

> **Purpose:** pin the mapping between the **P2 simulation fixtures** (Contract-1 field names, as actually
> shipped in `data/*.json`) and the **production graph vocabulary** in
> [production-graph-schema.md](production-graph-schema.md) (doc 10) — its Layer-2 `edge_type`s and Layer-4
> `evidence_type`s. This is the seam P4 builds the **evidence packet** (Contract-3) against, and P3 produces.
> Without this table the two drift: P2 ships `soft_play_delta`, doc 10 says `soft_play`, and the packet
> silently loses the link.
>
> **Owner:** P2 (Tate, Contract-1 seam). **Consumers:** P3 (produces packet), P4 (schema + eval). **Status:**
> reference — descriptive of current fixtures, not a rename mandate. Field names below are the *as-shipped*
> P2 fixture keys; the graph columns are the *target* vocabulary the packet should emit.

---

## The core idea

The fixtures are a **rolled-up findings view** (post-detection projection — see `dataset-vs-graph.html`): they
*assert* integrity signals as scalar/boolean fields on players and cluster records. Doc 10 is the **raw graph**
those fields project from. This table is the projection key — it says which fixture field becomes which graph
edge and which reviewer-facing reason code.

**Read it as:** *fixture field (what P2 ships) → Layer-2 edge (what it would be in the graph) → Layer-4
`evidence_type` (what the analyst/LLM sees in the packet).*

---

## 1. Behavioral-collusion signals

| P2 fixture field (as shipped) | Lives in | Layer-2 edge (`edge_type`) | Layer-4 `evidence_type` | Notes |
|---|---|---|---|---|
| `soft_play_delta` (float, −1…0) | `players.json`, `relationships.json` | `SOFT_PLAYS_AGAINST` / `soft_play` | `soft_play` | Escalation threshold ≤ −0.60. CL-001: −0.75…−0.82 (fires); CL-002: −0.30…−0.35 (sub-threshold). |
| `outsider_pressure_signal` (bool) | `relationships.json` | `TARGETS_OUTSIDER` / `outsider_targeting` | `outsider_targeting` | Asserted boolean today; doc 10 derives from hand aggression/net-flow vs non-members. |
| `co_seating` `{ rate, shared_tables, opportunities }` | `relationships.json` | `CO_SEATED_WITH` / `co_seating` | `co_seating` | CL-001: 14/18 = 0.778. Field names already align with doc-10 edge props (`shared_tables`, `opportunities`, `rate`). |
| `timing_correlation` (float 0–1, pairwise) | `relationships.json` | `TIMING_CORRELATED` / `timing_correlation` | `timing_correlation` | CL-001 C↔A 0.88, C↔B 0.85. |
| `timing_regularity` (float 0–1, per-player) | `players.json` | — (no pairwise edge) | feeds `bot_like` (see §4) | Per-account regularity, **not** a pairwise timing edge — do not confuse with `timing_correlation`. |

## 2. Identity-linkage signals

| P2 fixture field | Lives in | Layer-2 edge | Layer-4 `evidence_type` | Notes |
|---|---|---|---|---|
| `device_group_id` (Account prop) | `players.json`, `devices.json`, `table_roster.json` | `SHARES_DEVICE` / `shares_device` | `device_link` | DG-001 = A/B (CL-001); DG-002 = H1/H2 (household FP). |
| `device_link` (bool, on cluster/household record) | `relationships.json` | `SHARES_DEVICE` / `shares_device` | `device_link` | Rolled-up presence flag; the raw substrate is `device_group_id`. |
| `household_id` / `H-0x` | `players.json`, `relationships.json` | weak `Customer` proxy (no KYC spine in fixtures) | `household_counter_evidence` (see §5) | Household membership is **exculpatory**, not incriminating, in CASE-E. |
| `cluster_id` (`CL-001`/`CL-002`) | `players.json`, `relationships.json` | `Cluster` node + `MEMBER_OF` | `active_cluster_presence` (table side) | CL-001 escalates; CL-002 is `neutral` (sub-threshold). |

## 3. Table-health signals

| P2 fixture field | Lives in | Graph term | Notes |
|---|---|---|---|
| health bands `low · neutral · high · manual_review` | scoring output (P3) | integrity band (Contract-2) | Band `monitor` was renamed `neutral` — **band sense only** (the `monitor` action/status is unchanged). |
| `paid_seat_time` / `paid_seat_time_trend` | `table_roster.json`, `room_state_hourly.json` | feeds `Health(T)` `P_frag` / `P_bleed` | Composition + observed terms; not a graph edge. |
| room KPI fields | `room_metrics_*.json` | `IMPACTS_TABLE` / `table_health_degradation` (demo-approximated) | Counterfactual aggregate, not a per-cluster derived edge yet (needs `hand_events` — see signal-gap doc Level 2). |

## 4. Bot-like signal (fixture-only sub-category)

| P2 fixture field | Lives in | Graph term | Notes |
|---|---|---|---|
| `bot_similarity_score` (float 0–1) | `players.json` | **no doc-10 edge** — account-level integrity sub-score | CASE-G (P-221, 0.87). Routes to a **bot review queue**, NOT the cluster/collusion queue. Doc 10 has no bot edge; keep as an account property + its own evidence/queue. Eval must keep it distinct from coordinated-cluster. |

## 5. Counter-evidence (attach via `CONTRADICTED_BY`)

The guardrail — "no single signal is proof" — lives structurally here. Every false-positive trap maps to a
named counter-evidence type:

| Fixture situation | Layer-4 counter-`evidence_type` | Case effect |
|---|---|---|
| Shared device, divergent schedule/style (CASE-E: H1 evenings / H2 mornings, co-seat 2/22) | `household_counter_evidence` | hold at `monitor`, do not escalate |
| High co-seating fully explained by stake/time (CASE-D: P-142/P-143 overlap, no device/soft-play) | `legitimate_regular_counter_evidence` | benign — schedule overlap, not collusion |
| Signal present but sub-threshold / thin support (CL-002: soft_play −0.30/−0.35 vs −0.60) | `low_sample_size_counter_evidence` | suppress until support clears threshold → band `neutral` |

---

## Drift watch — known naming mismatches to reconcile

These are the exact places the fixture vocabulary and doc-10 vocabulary differ. P3/P4 must map, not assume equality:

1. **`soft_play_delta` (fixture scalar) vs `soft_play` (edge_type) / `aggression_delta` (edge prop).** The fixture
   ships one rolled-up delta; doc 10's edge carries `aggression_delta` + `hand_count`. Packet should emit
   `evidence_type: soft_play` with the fixture's `soft_play_delta` as its score.
2. **`outsider_pressure_signal` (bool) vs `outsider_targeting` (edge) / `ev_extracted` + `aggression_lift` (props).**
   Boolean today; richer props only exist post-`hand_events`.
3. **`timing_regularity` (per-account) ≠ `timing_correlation` (pairwise).** Different objects. `regularity` feeds
   `bot_like`; `correlation` feeds `TIMING_CORRELATED`. Do not collapse.
4. **`bot_similarity_score`** has **no graph edge** — it is an account-level score with its own review queue.
   Keep CASE-G out of the collusion/cluster path.
5. **Integrity band `neutral`** (was `monitor`) — Contract-2 enum is `low · neutral · high · manual_review`.
   The *action*/*status* `monitor` is unchanged.

## Open coordination

- **`expected_category: monitor_low` / `monitor_low_medium`** in `seeded_case_labels.json` are band-ish labels P4
  reads in the eval harness. Whether they follow the `monitor → neutral` band rename is a **P2 ↔ P4** decision —
  tracked separately so the answer key and the rubric stay in sync. Until decided, they keep their current values.
