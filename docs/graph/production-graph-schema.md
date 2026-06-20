# 10 — Production Graph Schema: The Four-Layer Relationship Taxonomy

> **Scope: production-grade, not demo.** This is the implementation-ready property-graph schema for an
> online poker integrity + table-health system at a real cardroom. It supersedes the minimal 7-node
> demo ontology in [04](04-synthesis-recommendation.md) (which remains a valid *subset* for the seeded
> capstone) and realizes the production additions anticipated in [07](07-production-target-and-geo.md)
> (Customer/IP/Location/Payment, CHIP_FLOW, geo + AML). It is a **labeled property graph** (Neo4j /
> Memgraph), not RDF/OWL — verdict unchanged ([01](01-graph-vs-relational.md)).
>
> **Simulator handoff:** see [simulator-signal-gap.md](simulator-signal-gap.md) for the exact P2 fixture
> changes required to derive this schema's Layer-1 raw relationships and Layer-2 signal edges instead of
> asserting them as rolled-up fields.

## The four layers

The graph is organized as four taxonomic layers, each with a different job, lifecycle, and audience:

| Layer | What it is | Lifecycle | Audience |
|---|---|---|---|
| **1 · Raw** | Observed factual relationships, minimal interpretation | **compacted rollups / rolling-window in graph; full append-only history in lakehouse** | serving layer |
| **2 · Derived signal** | Computed risk relationships over a time window | recomputed on schedule; **latest active window in graph, prior windows archived to lakehouse** | scoring + detection |
| **3 · Case** | Investigation / evidence workflow edges | mutated by analysts, fully audited; **persists while under investigation** | analyst workflow |
| **4 · Evidence types** | Reason-code taxonomy on Evidence nodes | **materialized only for case-relevant or threshold-crossing signals** | reviewers + grounded LLM |

**Design law:** *raw is fact, derived is inference, case is judgment, evidence is explanation.* A signal
never overwrites a fact; a case never overwrites a signal; the LLM only ever reads evidence.

> **The graph is a bounded serving layer, NOT the system of record.** The **lakehouse** is append-only
> and holds the full event history; the **graph** holds entities, current/rolling-window relationships,
> compacted raw rollups, high-signal derived edges, and case/evidence objects — and is aggressively
> windowed so it does not explode. See [Bounded graph contract](#bounded-graph-contract--what-lives-where)
> and [Retention](#retention--windowing) — these rules are load-bearing, not footnotes.

---

## Node catalog

Canonical labels are **UPPER_CAMEL** Cypher node labels; every node has a stable `*_id`. Hands are **not**
nodes — see [Retention](#retention--windowing).

| Node | Key id | Role | Notes |
|---|---|---|---|
| `Customer` | customer_id | KYC'd legal identity (the real person/entity) | **Identity backbone.** One Customer ⟶ many Accounts. Entity resolution merges here. |
| `Account` | account_id | A login / screen-name | The unit of play and of most signal edges. `archetype`, `risk_score`. |
| `Device` | device_id | Device fingerprint | Shared-attribute hub. |
| `IP` | ip_id | IP address / subnet | Churns fast → windowed; carries `asn`, `is_hosting`, `vpn_score`. |
| `Location` | location_id | Geo point / region + `jurisdiction` | Geofencing, impossible-travel. Jurisdiction may be its own node if regulatory modeling deepens. |
| `PaymentInstrument` | instrument_id | Card / bank / wallet | Deposits, withdrawals, AML. Shared payment = strong link. |
| `Session` | session_id | A login session (temporal anchor) | Device/IP/Location are observed *here*. Windowed at scale. |
| `Seating` | seating_id | **Reified seat event** (account at table during session) | Carries `paid_seat_time`. The node that makes "who sat with whom, when" queryable. |
| `Table` | table_id | Health-scored venue | `health_score`, `health_band`, `winnings_concentration`. |
| `Cluster` | case_id | Investigation case | `status ∈ {open, monitor, escalated, closed}`, `integrity_score`. |
| `Evidence` | evidence_id | One reason-coded, grounded fact | `evidence_type` (Layer 4), `score`, `is_counter_evidence`. |
| `Analyst` | analyst_id | Human reviewer (pit boss) | For the `ACTION_TAKEN` audit trail. |
| `Action` | action_id | Immutable decision record | Optional reification of `ACTION_TAKEN` for hard audit. |

---

## Bounded graph contract — what lives where

The single most important production rule: **the graph is a bounded serving layer, the lakehouse is the
append-only system of record, the feature store serves router-time scores.** Three stores, three jobs —
never collapse them.

> **Graph stores entities + current relationships + risk conclusions. Lakehouse stores full event history.
> Feature store serves router-time scores.**

| Store | Holds | Write pattern |
|---|---|---|
| **Property graph** (Neo4j/Memgraph) | entities; current / rolling-window event anchors; **compacted raw relationship rollups**; current materialized **high-signal** derived edges; case + evidence objects | bounded, windowed, compacted — **NOT append-only** |
| **Lakehouse / warehouse** | full hand history; full session history; full seating history; raw login / IP / location / payment events; historical detector outputs; **archived old graph windows** | **append-only**, partitioned by date |
| **Feature store** | router-time health / risk / fit scores; cached integrity gates; latest table / player features | upsert latest; low-latency read |

**What this means concretely:**
- A raw *source event* (a hand, a login, an IP touch) is append-only — **in the lakehouse**. It does **not**
  become a permanent graph node/edge.
- A graph *raw edge* (`USES_DEVICE`, `USES_IP`) is a **compacted/materialized rollup** of many such events
  (`first_seen`/`last_seen`/`session_count`), carried under a TTL or rolling window — not one edge per touch.
- A derived edge's **latest active window** lives in the graph; **prior windows are archived** to the
  lakehouse, not versioned indefinitely in the graph.
- Detailed backing records (the specific hands behind a `soft_play` signal) live in the **lakehouse**,
  referenced by id — they are not copied onto the graph edge.

See [Retention](#retention--windowing) and [Cardinality budget](#cardinality-budget--degree-caps) for the
enforced limits.

---

## Property conventions

**Every derived (Layer-2) edge MUST carry these:**

| Property | Type | Meaning |
|---|---|---|
| `window_start` | datetime | start of the observation window the signal was computed over |
| `window_end` | datetime | end of the window (signals are *always* time-bounded — no signal is "forever true") |
| `score` | float 0–1 | strength/magnitude of the signal, normalized |
| `confidence` | float 0–1 | how sure we are it's real (sample-adjusted; low support → low confidence) |
| `support_count` | int | how many underlying observations back it (hands, sessions, co-seats) |

Plus `algo_version` (which detector/version emitted it) and `computed_at` for reproducibility.
Raw (Layer-1) edges instead carry `first_seen` / `last_seen` / `observed_count` (or `source_event_id`).

**On `evidence_ids` — do NOT put large arrays on every derived edge.** An earlier draft attached an
`evidence_ids[]` back-pointer array to every signal edge; at production cardinality that bloats the graph.
Instead:
- Keep the **summary fields** (`score`, `confidence`, `support_count`) on the derived edge — that's enough
  for WCC/Louvain weighting and the integrity gate.
- Create **`Evidence` nodes only for case-relevant or threshold-crossing signals** (the ones an analyst will
  actually see). Most low-signal edges never need an Evidence node.
- For the detailed backing records, store a **single lakehouse reference** (e.g. `backing_ref` =
  a query key / partition pointer), not an inline array of ids. Heavy detail stays in the lakehouse.

---

## Layer 1 — Raw relationships (compacted observed facts)

> What *happened*, not what it *means*. **The raw source events are append-only in the lakehouse; the graph
> raw edges are compacted/materialized rollups with a TTL or rolling window.** A graph raw edge is never one
> row per touch — it is a `first_seen`/`last_seen`/`session_count` summary of many lakehouse events.

| Graph label | API `edge_type` | From → To | Required props | Optional props | Graph retention (full history → lakehouse) |
|---|---|---|---|---|---|
| `BELONGS_TO_CUSTOMER` | `belongs_to_customer` | Account → Customer | `first_seen` | `kyc_level`, `status` | long-lived (identity spine, KYC) |
| `USES_DEVICE` | `uses_device` | Account → Device | `first_seen`, `last_seen`, `session_count` | `user_agent`, `os` | **rollup**, ~180d rolling; longer only if tied to a case |
| `USES_IP` | `uses_ip` | Account → IP | `first_seen`, `last_seen`, `session_count` | `asn`, `vpn_score` | **short TTL / compacted last_seen rollup** (IPs churn); ~30–90d |
| `USES_PAYMENT` *(=FUNDED_BY)* | `funded_by` | Account → PaymentInstrument | `first_seen`, `last_seen` | `method_type`, `processor`, `direction` | long-lived (AML/KYC record) |
| `PLAYS_FROM_LOCATION` | `plays_from_location` | Account → Location | `first_seen`, `last_seen`, `observed_at` | `geo_source`, `jurisdiction` | **short TTL / compacted rollup**; ~30–90d, keep last-known longer |
| `LOGGED_IN_SESSION` | `logged_in_session` | Account → Session | `started_at`, `ended_at` | `device_id`, `ip_id`, `location_id` | **30–90d hot window**; prune Session nodes beyond, full history in lakehouse |
| `SEATED_AT` | `seated_at` | Account → Seating | `seated_at` | `buyin`, `left_at` | window with Seating (30–90d) |
| `AT_TABLE` | `at_table` | Seating → Table | `seated_at` | `seat_no` | **30–90d hot**, full history in lakehouse |
| `IN_SESSION` | `in_session` | Seating → Session | — | — | window with Session |

**Design note — temporal anchoring.** Device / IP / Location are *observed during a login session*. We
keep the graph compact by **materializing account-level edges** (`first_seen`/`last_seen`/`session_count`)
instead of one edge per touch, while the `Session` node retains the per-session `device_id`/`ip_id`/
`location_id` for forensic precision. High-assurance deployments may instead model `Session → Device`
edges directly — the schema supports either; pick one per the cardinality budget. **Either way, the per-touch
event log lives in the lakehouse, never as per-touch graph edges.**

---

## Layer 2 — Derived signal edges (computed risk over a window)

> Inference. Recomputed on a schedule. **Every edge carries the five required window/score props above.**
> These are the edges WCC/Louvain run on and the integrity score counts.

| Graph label | API `edge_type` | From → To | Dir | Signal-specific props | Feeds |
|---|---|---|---|---|---|
| `SHARES_DEVICE` | `shares_device` | Account ↔ Account | undirected | `shared_device_ids[]` | ER, ring linkage |
| `SHARES_IP` | `shares_ip` | Account ↔ Account | undirected | `shared_ip_ids[]`, `same_subnet` | ER, ring linkage |
| `SHARES_PAYMENT` | `shares_payment` | Account ↔ Account | undirected | `shared_instrument_ids[]` | ER, AML, chip dumping |
| `ENTITY_MATCHES` | `entity_resolution_link` | Account ↔ Account | undirected | `match_score`, `match_features[]` | **promotes to Customer merge** |
| `CO_SEATED_WITH` | `co_seating` | Account ↔ Account | undirected | `shared_tables`, `opportunities`, `rate` | collusion, community detection |
| `TIMING_CORRELATED` | `timing_correlation` | Account ↔ Account | undirected | `median_join_gap_sec`, `correlation` | coordinated entry |
| `SOFT_PLAYS_AGAINST` | `soft_play` | Account → Account | directed | `aggression_delta`, `hand_count` | collusion (won't bet into ally) |
| `TARGETS_OUTSIDER` | `outsider_targeting` | Account → Account (→victim) | directed | `aggression_lift`, `ev_extracted` | predation, **table-health bridge** |
| `CHIP_FLOW_TO` | `chip_flow` | Account → Account | directed | `net_amount`, `hand_count`, `pot_share` | chip dumping, **AML** |
| `JOIN_PATTERN_MATCHES` | `join_pattern_match` | Account ↔ Account | undirected | `pattern_score`, `n_co_joins` | coordinated lobbying |
| `MUTUALLY_AVOIDS` *(added)* | `mutual_avoidance` | Account ↔ Account | undirected | `avoidance_score`, `expected_vs_actual` | ring evasion (never same big pot) |
| `IMPACTS_TABLE` | `table_health_degradation` | Cluster → Table | directed | `health_delta`, `severity` | **integrity → health signal** |

**Three modeling calls baked in here:**
1. **`MUTUALLY_AVOIDS` is a recommended addition** — the proposal listed `mutual_avoidance` as an evidence
   type with no producing edge. Sophisticated rings *avoid* tangling with each other to dodge co-seating
   detection; the inverse signal needs its own edge so every evidence type has a source.
2. **`IMPACTS_TABLE` (derived, signal) ≠ `CONCERNS_TABLE` (case, workflow).** `IMPACTS_TABLE` is a *computed*
   "this active cluster is degrading this table's recreational health by Δ right now" — it feeds
   `P_clus`/`P_bleed` in `Health(T)` ([06](06-table-health-model.md), [09](09-router-decision-model.md)).
   `CONCERNS_TABLE` is the *analyst* link "this case is about this table." A table can be impacted before a
   case formally concerns it.
3. **`ENTITY_MATCHES` is the entity-resolution edge**, distinct from `SHARES_*`. Sharing a device is *one
   feature*; `ENTITY_MATCHES` is the *fused* same-person verdict over many features, and when `match_score`
   clears threshold it triggers a `Customer` merge (or a `same_customer` review).

**Materialization is thresholded — derived edges are NOT created for every pair.** A pairwise derived edge
exists in the graph only when it clears a materialization gate; everything below threshold stays as
lakehouse aggregates, never as a graph edge:
- **`CO_SEATED_WITH`:** materialize only above a **support + rate threshold** (e.g. `shared_tables ≥ k` *and*
  `rate ≥ r`). Two strangers who happened to share one table never get an edge.
- **Behavioral edges** (`SOFT_PLAYS_AGAINST`, `TARGETS_OUTSIDER`, `CHIP_FLOW_TO`, `JOIN_PATTERN_MATCHES`,
  `MUTUALLY_AVOIDS`): materialize only when **`support_count` and `confidence` both clear thresholds** —
  low-sample signals stay as `low_sample_size_counter_evidence`, not edges.
- **`SHARES_IP` is the dangerous one** — see the degree caps in
  [Cardinality budget](#cardinality-budget--degree-caps). High-degree shared attributes are **not**
  expanded into pairwise cliques.

---

## Layer 3 — Case relationships (investigation workflow)

> Judgment. Mutated by analysts. **Fully audited.** This is where detection output becomes an
> investigable, defensible case.

| Graph label | API `edge_type` | From → To | Required props | Optional props | Purpose |
|---|---|---|---|---|---|
| `MEMBER_OF` | `member_of` | Account → Cluster | `added_at`, `added_by` | `role`, `membership_confidence` | who is in the ring |
| `CONCERNS_TABLE` | `concerns_table` | Cluster → Table | `added_at` | `impact_summary` | which venues the case touches |
| `SUPPORTED_BY` | `supported_by` | Cluster → Evidence | `weight` | `added_by` | incriminating evidence |
| `CONTRADICTED_BY` | `contradicted_by` | Cluster → Evidence | `weight` | `added_by` | **counter-evidence — "no single signal is proof"** |
| `ACTION_TAKEN` | `action_taken` | Analyst → Cluster | `action_type`, `timestamp`, `prev_status`, `new_status` | `rationale`, `action_id` | audit trail of decisions |

**`CONTRADICTED_BY` is the structural home for the guardrail.** The product never auto-accuses; the
convergence gate must weigh evidence *against* a case as first-class. Counter-evidence types
(`household_counter_evidence`, `legitimate_regular_counter_evidence`, `low_sample_size_counter_evidence`)
attach via this edge and explicitly hold cases at `monitor` instead of `escalated`.

**`ACTION_TAKEN` for auditability.** `action_type ∈ {open, monitor, escalate, restrict, clear, file_sar,
reinstate}`. For regulator-grade audit, reify each action as an immutable `Action` node
(`Cluster → Action ← Analyst`) so the decision history is append-only and tamper-evident.

---

## Layer 4 — Reviewer-facing evidence types (reason codes)

> Explanation. These are the `evidence_type` values on `Evidence` nodes — the controlled vocabulary shown
> to analysts and fed verbatim into grounded LLM summaries. **snake_case**, API-stable, each traceable to
> a producing edge. Grouped by what they prove.

### Identity-linkage evidence
| `evidence_type` | Produced by | Tells the analyst |
|---|---|---|
| `device_link` | `SHARES_DEVICE` | accounts share a device fingerprint |
| `ip_link` | `SHARES_IP` | accounts share an IP / subnet |
| `payment_link` | `SHARES_PAYMENT` | accounts share a funding instrument |
| `entity_resolution_link` | `ENTITY_MATCHES` | accounts are likely the *same person* (fused score) |
| `known_counterparty_link` | `SHARES_*` / external watchlist | linked to a previously-actioned or watchlisted entity |

### Behavioral-collusion evidence
| `evidence_type` | Produced by | Tells the analyst |
|---|---|---|
| `co_seating` | `CO_SEATED_WITH` | sit together far more than chance ("14 of 18 tables") |
| `timing_correlation` | `TIMING_CORRELATED` | join within seconds of each other repeatedly |
| `soft_play` | `SOFT_PLAYS_AGAINST` | systematically under-aggress against each other |
| `outsider_targeting` | `TARGETS_OUTSIDER` | gang up on non-members (the victims) |
| `chip_flow` | `CHIP_FLOW_TO` | net chips consistently move one direction (dumping) |
| `mutual_avoidance` | `MUTUALLY_AVOIDS` | suspiciously *never* clash in big pots (ring evasion) |
| `join_pattern_match` | `JOIN_PATTERN_MATCHES` | coordinated lobby/seat-grab patterns |

### Table-health evidence (feeds Health(T), not just integrity)
| `evidence_type` | Produced by | Tells the analyst |
|---|---|---|
| `winnings_concentration` | Table metric (Gini/top-k over a *linked* cluster) | profit pooling in a connected group |
| `recreational_loss_velocity` | cohort loss-velocity vs fair-play baseline | fish losing faster than variance explains |
| `table_health_degradation` | `IMPACTS_TABLE` / `Health(T)` drop | this table's recreational health is falling |
| `active_cluster_presence` | `CONCERNS_TABLE` / `IMPACTS_TABLE` | an open/escalated case is seated here |

### Geo / network evidence
| `evidence_type` | Produced by | Tells the analyst |
|---|---|---|
| `impossible_travel` | `PLAYS_FROM_LOCATION` sequence | logins from locations too far apart in time |
| `vpn_proxy_signal` | `USES_IP` (`vpn_score`/`asn`) | play routed through VPN/hosting/proxy |

### Counter-evidence (attach via `CONTRADICTED_BY`)
| `evidence_type` | Tells the analyst | Effect |
|---|---|---|
| `household_counter_evidence` | shared device but divergent schedule/style → likely one household | hold at `monitor`, don't escalate |
| `legitimate_regular_counter_evidence` | high co-seating fully explained by stake/time preference | benign — schedule overlap, not collusion |
| `low_sample_size_counter_evidence` | signal rests on too few hands/sessions to trust | suppress until `support_count` clears threshold |

---

## How these edges feed WCC / Louvain / community detection

1. **Linkage subgraph for components.** Run **Weakly Connected Components** over the *identity-linkage*
   derived edges (`SHARES_DEVICE`, `SHARES_IP`, `SHARES_PAYMENT`, `ENTITY_MATCHES`) plus
   `CO_SEATED_WITH`/`TIMING_CORRELATED`. Each component is a *candidate* ring boundary.
2. **Louvain for sub-structure.** Within large components, **Louvain** (weighted by edge `score`) separates
   genuine tight rings from incidentally-linked crowds (e.g., a popular shared public IP).
3. **Convergence gate = the escalation rule.** A component escalates only when **N independent
   `evidence_type` families converge** on it (identity + behavioral + flow), *net of* `CONTRADICTED_BY`
   counter-evidence. "No single signal is proof" is implemented literally: one `device_link` alone →
   `monitor`; `device_link` + `co_seating` + `soft_play` + `chip_flow` with no counter-evidence →
   `escalated`. `confidence` and `support_count` weight each family so thin signals can't tip the gate.
4. **Why a graph.** This is multi-hop, shared-attribute fan-out that self-JOINs can't express at depth —
   the canonical case for an LPG ([01](01-graph-vs-relational.md)).

## How these edges feed scoring & routing

- **Integrity score** of a `Cluster` = weighted convergence count of its `SUPPORTED_BY` evidence families
  minus `CONTRADICTED_BY`, scaled by `confidence`. Drives `status`.
- **Health(T)** consumes graph output: `IMPACTS_TABLE.health_delta`, `active_cluster_presence`, and
  `winnings_concentration` feed `P_clus`/`P_bleed`; `TARGETS_OUTSIDER` and `recreational_loss_velocity`
  feed predation/bleed terms ([06](06-table-health-model.md), [09](09-router-decision-model.md)).
- **Routing** (`Rank = w_fit·Fit + w_health·Health + w_marg·ΔHealth`, integrity-gated first):
  the integrity **hard-gate** suppresses tables where seating would complete a flagged cluster, using the
  *derived* layer at seat-time (cached `Health(T)`, cheap `ΔHealth`) — no graph traversal in the request
  path beyond the gate lookup ([09](09-router-decision-model.md)).
- **Future ML/GNN (Phase 2).** The derived edges are the GNN's edge set; `score`/`confidence` are edge
  features; `Customer`/`Account` props are node features. The graph becomes a **feature factory** feeding an
  interpretable policy — ML in *perception*, never in the *decision* ([09](09-router-decision-model.md)).
  No schema change needed to add it.

## How these edges feed reviewer evidence packets & grounded LLM summaries

1. **The packet IS the case subgraph.** Anchor on `Cluster`; pull 2-hop: `MEMBER_OF` accounts, their
   `SUPPORTED_BY` and `CONTRADICTED_BY` `Evidence`, `CONCERNS_TABLE`/`IMPACTS_TABLE` tables.
2. **GraphRAG serialization.** Emit each edge as a `subject → relation → object {props}` triple; every
   `Evidence` node already carries a snake_case `evidence_type` (Layer 4) + `reason_code` + `score`.
3. **Grounding guarantee.** The LLM is prompted to summarize **only** from the serialized evidence triples,
   *including counter-evidence*. Because every claim back-references an `evidence_id`, the summary is
   "grounded, no invented facts" by construction — the eval-panel criterion — and the counter-evidence keeps
   it from overstating ("shared a device, but different schedules — held at monitor, not escalated").
4. **Auditability.** `ACTION_TAKEN` lets the packet show the full decision history; the human pit boss
   always decides — the system ranks and explains, never auto-bans.

---

## Naming conventions (canonical)

- **Graph relationship labels:** `UPPER_SNAKE_CASE` (Cypher convention) — `SOFT_PLAYS_AGAINST`.
- **Node labels:** `UpperCamelCase` — `PaymentInstrument`.
- **API `edge_type` and reviewer `evidence_type`:** `snake_case` — `soft_play`, `household_counter_evidence`.
- A relationship's `edge_type` need not equal its label lowercased (e.g. `USES_PAYMENT` ⟷ `funded_by`,
  `IMPACTS_TABLE` ⟷ `table_health_degradation`) — the mapping tables above are the source of truth.

## Retention & windowing

**The anti-explosion rules (non-negotiable):**
1. **Do not store every hand as a graph node.** Hands → lakehouse; the graph stores materialized *summaries*
   and *derived edges*, never per-hand nodes.
2. **Do not store every login / IP / location touch forever in the graph.** These are compacted to
   `first_seen`/`last_seen`/`session_count` rollups under a short TTL; the per-touch log lives in the lakehouse.
3. **Do not store every pairwise account relationship forever.** Pairwise derived edges are *thresholded*
   (support + confidence) and *windowed* — most account pairs never get an edge at all.
4. **Do not version every derived edge indefinitely in the graph.** Keep the **latest active window** only;
   archive prior windows to the lakehouse (`historical detector outputs`).
5. **Keep current hot windows in the graph; archive old windows to the lakehouse.**

**Per-type retention:**

| Graph object | Graph retention | Full history |
|---|---|---|
| `Session`, `Seating` (+ their edges) | **30–90d hot window** | lakehouse (append-only) |
| `USES_IP`, `PLAYS_FROM_LOCATION` | **short TTL** / compacted `last_seen`+`session_count` rollup (~30–90d) | lakehouse |
| `USES_DEVICE` | longer than IP, but still **rollup/windowed (~180d)** — extended only if tied to an open case | lakehouse |
| `BELONGS_TO_CUSTOMER`, `USES_PAYMENT`, `Customer`, `PaymentInstrument` | **long-lived** (AML/KYC obligation) | lakehouse mirror |
| Derived signal edges | **latest active window only** by default | prior windows → lakehouse |
| `Evidence`, `Cluster` (+ case edges) | **persist while part of an investigation**; archive on `closed` per policy | lakehouse audit store |

- **Derived edges are versioned by window** (`window_start`/`window_end`/`algo_version`) and expire: a signal
  true last month isn't asserted today unless recomputed.
- **Implementation:** unique constraint + index on every `*_id`; index derived edges on `window_end` and
  `score` for fast "current signals above threshold" queries; TTL jobs sweep expired windows to the lakehouse;
  partition the lakehouse by date.

## Cardinality budget & degree caps

**Bounded graph contract (order-of-magnitude targets for near-term production):**
- **Accounts:** hundreds of thousands to low millions.
- **Whole graph:** should stay in the **low tens of millions of nodes/edges** — a single-instance LPG regime,
  *not* the sharded-distributed-graph + always-on-GNN tier. If a design choice pushes toward billions of
  edges, it's wrong — push that volume to the lakehouse.
- **Hands:** lakehouse-only, always. Zero hand nodes in the graph.
- **Pairwise derived edges:** thresholded + windowed; the count is bounded by *flagged* pairs, not *possible* pairs.
- **High-degree hubs:** capped or represented as **aggregate evidence**, never expanded into cliques.

**Degree caps for dangerous high-cardinality shared attributes** — `SHARES_IP` is the canonical trap (public
Wi-Fi, VPN exit nodes, mobile-carrier CGNAT, office/venue networks, hosting ASNs can each touch thousands of
unrelated accounts; naïve pairwise expansion is an O(n²) clique bomb):
- **Never materialize pairwise `SHARES_IP` for high-degree IPs.** Above a degree cap (e.g. an IP touched by
  `> D` accounts, or a known VPN/hosting/CGNAT `asn`), keep only the `Account → IP` raw edges; **do not** create
  the account↔account clique.
- For those hubs, emit a **single aggregate `Evidence` node** ("N accounts share hosting IP X") with a
  **down-weighted** `score`/`confidence`, instead of N² edges. The hub is one fact, not a ring.
- **Apply the same degree cap + confidence penalty to `SHARES_DEVICE`** when a device looks like an
  **emulator farm or public/shared machine** (degree far above household norms) — high degree → lower
  per-pair confidence, not a giant escalatable component.
- **`SHARES_PAYMENT`** is lower-degree by nature (instruments are rarely shared widely) but apply the same cap
  defensively against processor-level shared tokens.
- These caps are *why* `confidence` and `support_count` are required on every derived edge: WCC/Louvain and the
  integrity gate weight by them, so a high-degree hub can't tip a case on its own. "No single signal is proof"
  and "no high-degree hub is a ring" are the same rule.

## Relationship to the demo subset & the rolled-up findings view

- The **capstone demo ontology** ([04](04-synthesis-recommendation.md)) is the strict subset of this schema
  needed for seeded data: `Account/Device/Table/Session/Seating/Cluster/Evidence` + the collusion-core
  derived edges. Building the demo on this schema means the production additions (Customer, IP, Location,
  Payment, geo/AML edges) are *extensions, not rewrites*.
- The **`fairplay-simulation-lab/data` fixtures** are a *rolled-up findings view* (a post-detection
  projection — see `dataset-vs-graph.html`); this Layer-1/2 schema is the **raw graph they project from**.
  `CONTRADICTED_BY` + the counter-evidence types here close the "counter-evidence is prose" gap that view
  had.

**One-liner:** four layers — *raw facts → windowed signals → audited cases → reason-coded evidence* — over
a labeled property graph that keeps entities and conclusions, not every hand, and feeds detection, health,
routing, analyst packets, and (later) GNNs from one schema.
