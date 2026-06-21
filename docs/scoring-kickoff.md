# P3 Scoring Engine — Kickoff Work-Order

> **For:** P3 (Scoring, Recommendations, Evidence Engine lead). **Drafted by:** P2.
> **Status:** draft for P3 to adopt/adjust. **Produces:** Contract 2 (scores + recommendations) and, with P4, Contract 3 (evidence packet).
>
> This turns the architecture into a sequenced build plan: what to build, in what order, with the acceptance test for each. Everything here is grounded in already-merged P2 data and the design docs — nothing is blocked on more simulation work.

---

## 0. Required reading (30 min, in this order)

| Doc | Why |
|---|---|
| `docs/scoring-architecture.html` | The model map — every score, its method, champion/challenger, the dependency DAG. **This is your spec.** |
| `docs/index.html` | The canonical formulas: `Health(T) = 100 − P_pred − P_frag − P_clus − P_bleed`, `Rank(P,T) = w_fit·Fit + w_h·Health + w_Δ·ΔHealth`. |
| `docs/graph/fixture-vocab-mapping.md` | How P2's shipped field names map to the scoring / evidence vocabulary. Read before you touch `relationships.json`. |
| `docs/learn/` (6 guides) | Plain-English + runnable notebooks for classification (the first model) and clustering. Onboards anyone with no stats background. |
| `docs/PRD.md` §5 (P3) | Your charter and definition of done. |
| `docs/DECISIONS.md` D0b/D1/D7/D8/D10 | The open decisions that gate parts of this work (see §5 below). |

---

## 1. What you own (Contract 2)

Per PRD §5: player classification · table-health / seating-risk / integrity scoring · lobby ranking · pit-boss action logic · reason codes · evidence-packet generation · the frontend data adapter.

**Stack (D0, confirmed):** Python scoring core → **frozen JSON** → TS frontend. You read P2's `data/*.json`, compute scores, and emit JSON the frontend consumes. You never call the simulator live.

---

## 2. The eight scores, in build order

Build top-down — each score's dependencies must exist first. Acceptance tests are the three mandatory cases (CASE-A / C / E). **The whole demo runs on the deterministic "champion" of each score; the ML "challengers" are an additive upgrade (§4).**

### ① Classification — 9 archetypes  · **ROOT, build first**
- **Champion (ships demo):** threshold rules straight from `players.json`'s inference note (`registered_days_ago≤14 → new`; `vpip≥0.54 & pfr≥0.40 → aggressive_predatory`; `promo_redemptions_30d≥8 → promo_hunter`; `cluster_id set → cluster_member`; …).
- **Challenger (upgrade):** interpretable model — **recommend one-vs-rest binary logistic** (keeps the scorecard control surface; see `docs/learn/mn-vs-ovr.html`) or multinomial logistic.
- **Inputs:** the 9 numeric features in `players.json`.
- **Depends on:** nothing.
- **✅ Acceptance:** P-104=new · P-176/P-177=aggressive_predatory · P-164=grinder · P-184=promo_hunter · P-221=bot_like · P-198/199/200=cluster_member · P-192/193=shared_device_household.

### ② Integrity score — per cluster → `low · neutral · high · manual_review`  · **2nd root, build in parallel**
- **Method:** graph build from `relationships.json` → community detection (WCC/Louvain) → **convergence rule** (count independent signal families net of counter-evidence). **Not a trained model** — synthetic labels would make that circular.
- **Inputs:** `relationships.json` (clusters, `soft_play_delta` ≤−0.60 fires, `co_seating.rate`, `device_link`, `timing_correlation`), counter-evidence. Co-seating rates are now re-derivable from `seat_events.json`'s `co_seating_history`.
- **Depends on:** nothing (independent of classification).
- **✅ Acceptance:** CL-001 (P-198/199/200) → **high** (4 families converge) → recommend hold. Household H1/H2 (P-192/193) → **neutral** → monitor only. CL-002 → **neutral** (sub-threshold). **Never escalate the household** (CASE-E) — over-escalation is a failing eval.

### ③–⑥ Health(T) terms → Health(T)
- **P_pred** (predation pressure, 0–45): champion = skill-weighted aggressive:recreational ratio; challenger = monotonic GBM. Depends on **①**.
- **P_frag** (fragility, 0–25): deterministic formula from `table_roster.json` (`seated_count/max_seats`, `paid_seat_time_trend`). No challenger — calibrate constants.
- **P_clus** (active-cluster severity, 0–30): map the **integrity score ②** + fraction of seats held by cluster members → penalty.
- **P_bleed** (observed bleed, 0–20): rolling window over recreational session truncations (`room_state_hourly.json` / sessions). Held fixed between seatings.
- **Health(T)** = `100 − P_pred − P_frag − P_clus − P_bleed`, clamped [0,100] + band.
- **✅ Acceptance:** Health(T-22) = **38** → band *beginner-unfriendly*; T-8 healthy; T-11 (cluster seated) elevated `P_clus`.

### ⑦ ΔHealth + Seating-risk + Fit
- **ΔHealth(P→T):** re-score the composition terms (P_pred/P_frag/P_clus) with P added, take the delta. Deterministic, O(1). Depends on **③–⑥ + ①**.
- **Fit(P,T):** champion = archetype × table-style matrix; challenger = session-length GBM. Depends on **①**.
- **Seating-risk:** composite + reason codes (health band + ΔHealth + new-player vulnerability + integrity gate).
- **✅ Acceptance:** P-104 new-player seating risk at T-22 = **HIGH**.

### ⑧ Router — `Rank(P,T)` → lobby badge  · **the decision, build last**
- **Method:** **frozen deterministic policy** `w_fit·Fit + w_h·Health + w_Δ·ΔHealth`, integrity **hard-gate first** (a flagged-cluster table is removed from candidates, not just ranked down). **No model — by design.** Weights calibrated offline on the eval lab.
- **Depends on:** ②, ⑥, ⑦.
- **✅ Acceptance:** P-104 → **T-8 "Recommended for you"** (rank 55.2) · **T-14 "Good fit"** (44.2) · **T-22 "Available"**, de-prioritized internally (13.0). T-22 not promoted to new/rec players.

---

## 3. Reason codes everywhere

Every score emits the structured **reason codes** behind it (PRD §5 DoD: *every important UI state is driven by deterministic scores/reason codes, not hand-written front-end text*). For the ML challengers, the reason codes are the model's coefficients / feature importances — which is exactly why we use interpretable models.

---

## 4. Champion → challenger (the ML story)

Build all **champions** first (deterministic; ships the whole demo). Then, for scores ①②③ only, add **interpretable ML challengers** and race them against the champion **in P4's eval lab** — promote a challenger only if it (a) beats the champion on labeled accuracy AND (b) stays interpretable. Decision layer (⑧) has no challenger, ever. Full rationale + model glossary in `docs/scoring-architecture.html`.

---

## 5. Decisions that gate your work (raise early)

| Decision | Status | What you need |
|---|---|---|
| **D7** — canonical 9-archetype list | proposed | Ratify the names; they're your classifier's target. Proposed set is in DECISIONS.md / fixture-vocab-mapping. |
| **D8** — band numeric thresholds | 🔴 open | **You publish these** (health + integrity cutoffs) in `docs/scoring-thresholds.md` before computed scoring. P4 can't write eval checks without them. |
| **D0b** — interpretable ML vs formula | open | Confirms the challenger family (logistic/GBM, not neural). Recommendation: interpretable. |
| **D1** — master seed | 🔴 open | Needed for reproducible fixtures, but your champions can start on the current committed data now. |
| **D3** — evidence packet schema | 🔴 open (P4) | P4 defines; you produce. Get one typed example per case from P4 before wiring the packet. |
| **D10** — clustering | recorded | Demo path is classification on defined labels; clustering is the real-data discovery step, not a demo blocker. |

---

## 6. Hard rules (non-negotiable — from CLAUDE.md)

- **Player lobby must NOT expose** numeric health scores, player classifications, risk scores, or "predator"/integrity language. That language lives **only** in the pit-boss console. Lobby badges are neutral (stakes/pace/seats/"Recommended for you").
- **Keep the three lenses separate:** table-health ≠ integrity ≠ promo-abuse. Conflating them is a failing eval (CASE-B grinder = health concern *not* integrity; CASE-E household = monitor *not* escalate).
- **`seeded_case_labels.json` is the operator-facing answer key** — never expose it in any player-facing path. Use it only to validate your scores against ground truth.
- The LLM is never the detector — you produce the structured evidence packet; P4's LLM only explains it.

---

## 7. Suggested sequence (maps to PRD §9)

1. **Day 2 (static):** classification champion + a fixture of computed scores for the 3 cases, so P1's clickable flow has real numbers. Publish **D8 thresholds**.
2. **Day 3:** integrity score (champion) + Health terms → Health(T). Wire P1 to real Contract-2 output.
3. **Day 3–4:** Fit champion + ΔHealth + Seating-risk; assemble the **Router**; calibrate weights on the 3 cases.
4. **Day 4:** evidence packet (with P4's schema) for the 3 cases.
5. **Day 4–5:** train the challengers (①②③), race in the eval panel, promote winners — the "ML in perception" reveal.

---

## 8. First concrete task

**Classification champion** — a Python function `classify(player) -> (archetype, reason_codes)` using the threshold rules, run over `data/players.json`, validated against the archetypes in `seeded_case_labels.json` for the case players. It's the root dependency, it's a few hours, and it unblocks everything else. The runnable notebooks in `docs/learn/` are a working starting point — the OvR notebook already derives labels and fits a model on this exact data.
