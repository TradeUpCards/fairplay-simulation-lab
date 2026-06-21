# sim/cases — Mandatory Demo Case Scenarios (P2c)

The three **mandatory** demo cases (PRD §6) as operator-facing scenario fixtures. Each file is the
*shape* of a case that threads the demo spine — **structure, entity references, and expected
outcomes only**. No scores, no classifications: P3 computes those from this scaffold plus the
Contract-1 data. P2 supplies the scenario and the ground-truth seeds; P3/P4 supply the judgment.

## The three cases — one per risk lens (separation is load-bearing)

| File | case_id | demo_role | risk_lens | trap? | One-line |
|------|---------|-----------|-----------|-------|----------|
| `case_a_new_player.json` | CASE-A | `table_health` | `table_health` | no | New player (P-104) churns at predatory T-22; reroute to balanced T-8. |
| `case_c_coordinated_cluster.json` | CASE-C | `integrity` | `integrity_risk` | no | Cluster A/B/C (P-198/199/200) converge at T-11; hold 3rd seat for review. |
| `case_e_shared_device_fp.json` | CASE-E | `false_positive` | `integrity_risk` | **yes** | Household H1/H2 (P-192/193) share a device but nothing else; monitor only. |

**Why the lens split matters (PRD §7, task constraint):** conflation is a failing eval. CASE-A is a
*health* problem (silent churn, no cheating). CASE-C is the *true integrity* case. CASE-E is a
*false-positive trap* that probes the integrity lens — a shared device with every corroborating
collusion signal absent. The system must rank **CASE-C above CASE-E** and must never escalate the
household. Each file carries an explicit `lens_separation_guard` stating what it must NOT be
confused with.

## How a case file is structured

- `demo_role` / `risk_lens` / `is_false_positive_trap` — the lens contract (kept distinct on purpose).
- `entities` — references to canonical IDs in `data/players.json` (with table refs).
- `narrative` — the operator-facing scenario shape.
- `demo_spine` — what each stage (lobby → pit-boss → simulator → eval) shows for this case.
- `divergence_points` — links into `sim/counterfactual/decision_list.json` (the 5 decisions, hours
  0–3) that make the two paths differ for this case.
- `expected_outcome` — Standard vs FairPlay, pointing at `data/room_metrics_{standard,fairplay}.json`.
- `*_evidence_seed` / `convergent_signals` / `exculpatory_signals` — ground-truth seeds restated
  from `data/seeded_case_labels.json` as the demo target. **Simulated fields, never real detection.**
- `counter_evidence` — the innocent explanations the AI Investigator must surface.
- `labels_ref` — pointer back to the answer key in `data/seeded_case_labels.json`.
- `id_reconciliation` — any cross-file ID/label divergence this case depends on.

## Contract links

- **Ground truth / answer key:** `data/seeded_case_labels.json` (Aria) — CASE-A/C/E here mirror its
  canonical entities and `eval_checks`.
- **Divergence source:** `sim/counterfactual/decision_list.json` (Cleo) — the only thing that makes
  Standard and FairPlay differ.
- **Outcome metrics:** `data/room_metrics_{standard,fairplay}.json` (Cleo).
- **Consumers:** P3 (scores/evidence packet), P4 (AI summaries/evals), P1 (UI states).

## Cross-workstream reconciliation — RESOLVED

**Player-ID convention is canonical and consistent.** All P2 files use the answer-key namespace:
cluster **P-198/P-199/P-200**, household **P-192/P-193**. Bram migrated his roster/sessions/seat
events to these IDs (PR #8) and Cleo's `decision_list.json` + `room_metrics_*.json` were re-patched
off the earlier placeholder namespace to match. No outstanding player-ID conflicts.

**Table labels** are likewise canonical: `T-8` (no leading zero), `T-11` for the cluster (Aria's
join-key fix, PR #5) — adopted across CASE-A/C here.

## Not in scope here

CASE-B (grinder), CASE-D (regular overlap), CASE-F (promo abuse), CASE-G (bot-like) are eval-only
scenarios — they live in `data/seeded_case_labels.json` and are exercised by P4's eval harness, not
scaffolded as demo cases here (they are not mandatory demo cases per PRD §6).
