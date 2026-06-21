# sim/counterfactual — Counterfactual Decision List

## What this directory is

This directory defines the **only source of divergence** between the two 8-hour simulation paths
(Standard Room vs FairPlay Enabled). Everything else — the population, table roster, session
engine, and hour-0 room state — is shared and identical between paths.

## Contract

Both paths **replay from the same hour-0 start state** (produced by Bram's `room_state_hourly.json`
seeded from the shared `sim/config` seed). A simulation engine applies each decision in
`decision_list.json` according to which path it is running:

- **Standard path** → apply each decision's `standard` branch
- **FairPlay path** → apply each decision's `fairplay` branch

The result: `data/room_metrics_standard.json` and `data/room_metrics_fairplay.json` — 8 hourly rows
each, sharing hour-0 values and diverging only because of the decisions below.

## Critical rule: decisions are fixed data, not score-driven

The decisions in `decision_list.json` are **statically defined fixtures**, not computed from P3
scores at runtime. P3 scores may *justify* the decisions in the demo narrative, but they never
*drive* the simulation. This eliminates the P2→P3→P2 dependency cycle and keeps the simulation
fully deterministic and reproducible without the scoring engine present.

## Decision list summary (`decision_list.json`)

| id | hour | case | Standard branch | FairPlay branch |
|----|------|------|-----------------|-----------------|
| `t22-promotion-policy` | 0 | new-player | promote T-22 normally to new/rec players | suppress T-22 promotion to new/rec players |
| `new-player-route` | 1 | new-player | seat P-104 at T-22 (no risk routing) | seat P-104 at T-8 (balanced table) |
| `cluster-third-seat` | 2 | coordinated-cluster | seat P-200 at T-11, completing P-198/P-199/P-200 formation | hold 3rd seat at T-11 for pit-boss review |
| `cluster-pit-boss-accept` | 3 | coordinated-cluster | no action (formation already complete) | pit boss accepts containment; P-200 re-routed to separate table |
| `household-monitor` | 3 | shared-device-fp | no action on H1/H2 same-device flag | monitor only; no escalation |

Each decision traces directly to PRD §6 counterfactual runs. Note that `cluster-pit-boss-accept`
models the **resolution** of the hour-2 hold: without it, the FairPlay path would have an
unresolved held seat and hours 3–8 metrics would be ambiguous.

## Open placeholders (patch when dependencies land)

- `seed_ref: "TBD"` — update once Aria/Bram agree on the shared seed in `sim/config/`.

## Resolved references

- Cluster table is `"T-11"` (confirmed by `data/table_roster.json`).
- Cluster member IDs are canonical and consistent across `players.json`, `seeded_case_labels.json`,
  `table_roster.json` (Bram's migration, PR #8), and this decision list: **P-198/P-199/P-200**.
  Household IDs are likewise canonical: **P-192/P-193**. No outstanding ID conflicts.
- `case_ref: "shared-device-fp"` matches the CASE-E key in `data/seeded_case_labels.json`.

## File ownership

Cleo (P2c) owns all files in `sim/counterfactual/**`. Do not edit without coordinating with Cleo.
See `in-flight.md` for the full ownership map.
