# Day-1 Decisions to Lock — FairPlay Simulation Lab

**Status: DRAFT for team ratification.** Source: two independent PRD audits (feasibility + coherence) run 2026-06-20.
This is the Day-1 "contract lock" deliverable from PRD §9. **No new major features after Day 1.** Until a decision is
`✅ LOCKED`, it is a risk that will surface as rework on Days 3–6.

How to use: in the Day-1 sync, walk top to bottom. For each, pick an option, write it on the `Decision:` line, flip the
box to `✅ LOCKED`, and (where relevant) update `docs/PRD.md` so the spec stays authoritative. Owner = who drives the
decision; **Affects** = who builds against it.

Legend: 🔴 blocker · 🟠 major · 🟡 minor · ⬜ open · ✅ locked

---

## D0 — Tech stack 🔴  ⬜ OPEN
**Affects:** everyone. **Gates:** D1 (determinism), the whole Day-2 build. **Owner:** team.

The PRD §10 leaves this open; it must be settled **before** Day-2 implementation (effectively a Day-0 item, because it
decides whether determinism even holds — see D1).

| Option | Pros | Cons |
|---|---|---|
| **A. TypeScript monorepo** (Vite+React / Node sim+scoring / Anthropic TS SDK) | One seeded RNG across sim+scoring; one shared set of contract types (the evidence packet is a shared typed object); frontend imports fixtures directly; one toolchain/CI | Awkward if D0b wants **trained** models (no scikit/pandas) — would mean ML in TS or train-in-Python-export-weights |
| **B. Python sim+scoring + React/TS frontend** | Natural for numeric/stats; pydantic schema validation | Two RNG worlds (determinism risk); contract types defined twice → drift; two toolchains + an export/API seam |
| **C. Python sim (P2) → frozen JSON, TS everywhere else** | All RNG stays in P2's hands (the recommended determinism fix); P2 can stay Python | Duplicated schema seam between Python output and TS consumers |

**Recommendation: contingent on D0b (modeling approach) — decide D0b first.**
- If D0b = transparent/weighted scoring → **A (all-TypeScript monorepo)**: TS wins on determinism across the sim↔scoring seam and one shared contract-type definition for four parallel builders.
- If D0b = trained supervised models (logistic/GBM/scikit) → **C (Python sim+scoring → frozen JSON, TS frontend)**: keeps all RNG + the ML in Python where the tooling lives, while P1/P4 stay in TS over frozen JSON. Cost is the schema seam (mitigate with pydantic→JSON-Schema→TS codegen).
- **B** only if the team is Python-strong and wants a live API rather than frozen JSON.

**Why C over B (if Python):** nothing in this product recomputes interactively — real-time routing is a non-goal (PRD §8)
and the simulator is a fixed 8-hour *replay*. Frozen JSON *is* the Day-2 fixtures-first plan (§9) and the "swap to computed
data without changing the story" DoD; it's deterministic by construction, has no demo-day server/CORS/"API-down" failure
mode, and decouples the four humans (P1 builds against committed files without running P3's Python). A live API buys
fragility, not capability, for a tiny dataset (≤250 players · ≤20 tables · 8 hours) that freezes trivially.

**C → B later is a cheap stretch — don't build B up front, just don't foreclose it.** B is C plus a thin FastAPI layer that
imports the *same* scoring functions. Keep it cheap by designing two seams now: (1) **scoring as pure functions decoupled
from file I/O** (the export script and a future API route both just call them); (2) **one pydantic schema** serialized to
both JSON files and API responses (byte-compatible); (3) **frontend reads through a single data-access shim** (`loadCase(id)`,
ideally `async`/Promise-returning so the later swap to `fetch()` changes the *implementation*, not the call sites). Even if
you later add the API, **keep the frozen JSON as the canonical demo source** (API for interactivity, artifacts for the
rehearsed/recorded demo) so determinism never depends on a live server.

**"Design the API for B" is NOT the same as "doing B" — the line is transport + runtime, not the contract.** C already
defines the contract (frozen JSON shape = the pydantic schema); `GET /api/case/{id}` would return exactly those bytes. Three
levels, only the third is B:

| Level | What you do | Is it B? |
|---|---|---|
| **1 — API-shaped C** | Resources with stable shapes (`Case`/`TableScore`/`EvidencePacket`), named like endpoints; pure scoring functions; one schema; frontend behind a `loadCase(id)` shim. Deliver via files. | **No — this is C done well.** ~0 extra cost. **Do this.** |
| **2 — Spec without a server** | Write the intended endpoints (paths + response shapes) as a *design note*. | **No, if it's prose.** Capture in ARCHITECTURE; don't code stub routes. |
| **3 — Running server** | Stand up FastAPI, serve routes, frontend fetches at runtime, keep a process alive. | **Yes — this is B.** Defer until interactive recompute earns it. |

**Trap to avoid: over-architecting an API that supports no demo moment** (scope rule: "if it doesn't support a live demo
moment, it's not in scope"). A stub server that just reads frozen files is the worst of both — B's maintenance, C's
capability. Design the *seams* (Level 1) so B is an afternoon away; don't build the *server* now. Design-for-B-up-front is
only warranted if interactive recompute becomes a core feature — which the non-goals (real-time routing) rule out.
*(Owner: P3/P1 — this is their architecture to ratify.)*

**Decision:** **C — Python sim+scoring → frozen JSON artifacts, React/TS frontend + AI Investigator consume the JSON.**
Follows from D0b = (i) (Python ML) + the C-over-B rationale above (nothing recomputes interactively). Build with **Level-1
API-shaped seams** (pure scoring functions · one pydantic schema · async `loadCase(id)` data shim); **B (live FastAPI) is a
deferred stretch, not built now.** Frozen JSON stays the canonical demo source even if B is added later.
**Reversible:** because we build the Level-1 seams, the team can opt into B now (or any time) at low cost — if P3/P1 want the
live API from the start, switch without rework. *Proposed by P2 2026-06-20 — pending P3/P1 ratification.*

---

## D0b — Modeling approach: how much real ML? 🔴  ⬜ OPEN
**Affects:** P3, P4, and the stack (D0). **Owner:** P3. **Decide before D0.**

PRD §2 frames this as "ML-style scoring," "classification," and "predicts risky seating." Because P2 emits synthetic data
**with ground-truth labels**, supervised ML is genuinely on the table — and a capstone reviewer may expect to *see* it.
But determinism (D1), reason codes, demo-control, and the 10-day window pull toward interpretable methods. And by hard rule,
integrity signals (`bot_similarity_score`, `soft_play_delta`) are **simulated fields**, so integrity scoring *aggregates given
signals — it does not train a detector* ("the LLM is never the detector," "not real detection").

| Option | What it means | Tooling pull |
|---|---|---|
| **(i) Interpretable supervised models** | Multiclass classifier (logistic / gradient-boosted trees) for the 9 archetypes; regressor for table-health (0–100) + seating-risk; graph/anomaly features for integrity. Reason codes from coefficients / SHAP. | Python + scikit-learn → pushes D0 to C/B |
| **(ii) Transparent weighted scoring** | Hand-tuned feature weights + thresholds → scores + reason codes directly; no training. Deterministic by construction, trivially interpretable, demo-controllable. | TS or Python — keeps D0=A viable |
| **(iii) Hybrid (recommended)** | **Trained** classifier for archetypes (labels make it honest) · **transparent weighted** indices for health/seating (demo control + easy reason codes) · **graph + aggregation** for integrity, consuming P2's simulated fields (NOT a trained detector, per hard rule). | Mild Python pull (the classifier) |

**Per-score model menu (for option i/iii):**
- **Archetype classification (9-class):** multinomial logistic regression (coefficients → reason codes) *or* LightGBM/XGBoost (+ SHAP). A small MLP is overkill on synthetic labels.
- **Table-health (0–100):** linear/GBM regressor, or survival/retention model (PRD lists "survival · retention"), or a weighted index.
- **Seating-risk:** Δhealth counterfactual from the health model, or a (player × table) classifier.
- **Integrity-risk:** graph community detection (clusters) + co-seating/timing features + anomaly score, aggregating P2's `bot_similarity_score` / `soft_play_delta` fields with a false-positive offset. **Not a trained detector.**

**Recommendation: (iii) hybrid, leaning interpretable.** Demonstrates real ML competence (a trained classifier + the §7 eval
harness) without sacrificing determinism, reason codes, or demo control — and respects the "simulated-as-fields / LLM-is-not-
the-detector" hard rules for integrity. **This decision drives D0:** trained models → prefer C/Python; transparent only → A/TS.

**Decision:** **(i) Interpretable supervised models** — trained classifier for the 9 archetypes + trained regressors for
table-health & seating-risk; integrity stays graph + aggregation of P2's simulated fields (the hard rule means (i) and (iii)
are identical *for integrity* — you don't train a detector either way; the only delta is health/seating = trained regressor,
not weighted index). *Proposed by P2 2026-06-20 — pending P3 ratification.*

**Consequences:**
- **Stack → Python (D0 = C or B).** scikit-learn/pandas is the home for (i). All-TS (A) is off the table.
- **Training determinism (refines D1):** model training has its own randomness (train/test split, GBM subsampling, init).
  Treat training as a **seeded build-step that commits a frozen model artifact**; **inference is deterministic** over P2's
  frozen JSON. So "no RNG in P3" becomes "no RNG in P3 *inference*; training RNG is seeded + the artifact is committed."
- **Reason codes** come from the model (logistic coefficients, or SHAP on a GBM) — verify they read cleanly before locking
  the model family; interpretability is a hard requirement, not a nice-to-have.

---

## D1 — Determinism: single RNG owner + cross-seam rule 🔴  ⬜ OPEN
**Affects:** P2, P3. **Owner:** P2.

Determinism is a hard rule (CLAUDE.md) and the demo rests on "two paths share identical hour-0" + "swap to computed data
without changing the story." If randomness ever crosses a language/role boundary it silently breaks.

**Recommendation:** One master seed, committed in `sim/config/` and owned by **P2**. **All** sim stochasticity lives in the
sim layer. P3 **inference** must be pure/deterministic over P2's frozen output — no RNG at scoring time. Per D0b=(i), P3 also
has a **training** step with its own randomness: seed it (`random_state`/`numpy` seed committed alongside the model), and
**commit the trained model artifact** so inference replays identically without retraining. Net rule: *sim RNG → P2 only;
training RNG → seeded + artifact committed; inference → deterministic.* With D0=C (Python both sides, TS only consumes frozen
JSON), there's no live cross-language RNG seam to worry about.

**Decision:** _______________________

---

## D2 — Counterfactual divergence mechanism 🔴  ⬜ OPEN
**Affects:** P2 (cleo), P3. **Owner:** P2.

The two paths must share hour-0 then diverge *because of* FairPlay decisions (P-104→Table 8 not 22; cluster seat held).
But if those routing decisions depend on **P3 scores**, then P2's "two paths" secretly depend on P3 — a hidden P2→P3→P2
cycle that §9 schedules as P2-only on Days 5–6.

**Recommendation:** Encode the interventions as a **fixed decision-list fixture** owned by P2 (in `sim/counterfactual/`):
which player goes to which table, which seat is held — so the counterfactual is replayable without round-tripping through
live scoring. The scores can *justify* the decisions in the demo narrative without *driving* the sim.

**Decision:** _______________________

---

## D3 — Evidence-packet schema: ship a typed example, not a skeleton 🔴  ⬜ OPEN
**Affects:** P3 (produces), P4 (defines + enriches), P1 (renders). **Owner:** P4, with P3.

Contract 3 (PRD §4) is a skeleton — `scores:{}`, `top_evidence:[]`, `allowed_actions:[]` with no element shapes. Yet P1
(case detail) and P4 (prompts) must build against it on **Day 2**, before P3 produces it. It also omits fields §5-P4
*requires*: `summary`, `why_risky` / `why_not_proof`, `suggested_next_check`.

**Recommendation:** On Day 1, produce **one fully-typed example packet per mandatory case** (new-player, cluster, shared-
device) — a concrete instance *is* the contract. Define element shapes for `top_evidence` / `counter_evidence` /
`uncertainties`, make `allowed_actions` an enum (accept · override · monitor · suppress-for-player · escalate), and
explicitly split **which fields P3 fills vs. which P4 enriches**. Put the canonical schema in one place (CLAUDE.md calls
this seam load-bearing).

**Decision:** _______________________

---

## D4 — Eval cases: mandatory vs. stretch 🔴  ⬜ OPEN
**Affects:** P2, P4. **Owner:** P4, with P2.

PRD §7 treats promo-abuse (F) and bot-like-similarity (G) as required eval cases; PRD §8 lists them "nice to have" and
first on the cut list. P2 and P4 can't tell whether to build F/G fixtures.

**Recommendation:** Split §7 into **mandatory eval cases (A, C, D·E)** — anchored to the §6 demo fixtures — and **stretch
(B, F, G)**, built only if the schedule allows. Update PRD §7/§8 to agree.

**Decision:** _______________________

---

## D5 — Asserted numbers: targets or illustrative? 🟠  ⬜ OPEN
**Affects:** P2, P3, P1. **Owner:** P2, with P3.

The PRD asserts concrete values: Table 22 health **38/100**, cluster **14 of 18** co-seating, new-player **12 vs 42 min**.
If P1 hardcodes them Day 2 and P3 computes 45 on Day 3, the formula gets reverse-engineered or the demo copy drifts.

**Recommendation:** Pick one Day 1:
- **(a) Illustrative** — fixtures get regenerated from computed output; demo copy reads from data, never hardcoded. *(Lower risk; preferred.)*
- **(b) Hard targets** — then **P2 must seed the room so the co-seating count (≥18 opportunities for A/B/C) is achievable**, and P3 calibrates its formula to land near the stated values.

**Decision:** _______________________

---

## D6 — Lobby badge must not leak operator-only risk 🟠  ⬜ OPEN
**Affects:** P1, P3. **Owner:** P1, with P3.

The lobby "must not show player classifications / risk scores" (PRD §5.1, CLAUDE.md). But the badge tiers
("Recommended for you / Good fit / Available — *de-prioritized internally*") risk being a player-facing risk classification,
and "de-prioritized internally" leaks operator logic.

**Recommendation:** Define the badge as **neutral table-fit** (stakes/pace/seat availability match), with all integrity-aware
filtering happening **silently / pit-boss-side**. The lobby never explains *why* a table is de-prioritized.

**Decision:** _______________________

---

## D7 — Canonical 9-archetype classification list 🟠  ⬜ OPEN
**Affects:** P2 (seeded labels), P3 (classifier). **Owner:** P3, with P2.

PRD §2 and §5.3 list the nine player archetypes with drifting names: "coordinated-cluster member" vs "cluster candidate";
"shared-device household" vs "shared-device low-risk". P2 needs one canonical list for `seeded_case_labels.json`; P3 needs
it for the classifier.

**Recommendation:** Agree one canonical name per archetype and use it in §2, §5.3, the seeded labels, and the classifier.
Proposed canonical set:
`new · recreational · regular · grinder · aggressive_predatory · promo_hunter · cluster_member · shared_device_household · healthy_anchor`.

**Decision:** _______________________

---

## D8 — Band thresholds (health + integrity) 🟠  ⬜ OPEN
**Affects:** P3 (computes), P4 (eval validates), P1 (displays). **Owner:** P3.

Health bands (healthy · fragile · beginner-unfriendly · promo-abuse-prone · integrity-review-candidate) and integrity bands
(low / monitor / high / manual-review) have no numeric cutoffs. P3 would invent them and P4's eval couldn't validate scoring.

**Recommendation:** Define numeric thresholds + the decision rule for assigning each band (e.g. integrity 0–30 = low,
31–60 = monitor, …). Document them where P3 and P4 both read.

**Decision:** _______________________

---

## D9 — One canonical metric-key list 🟡  ⬜ OPEN
**Affects:** P2 (emits), P1 (displays). **Owner:** P2, with P1.

The hourly-metrics field list (PRD §2.2 / §5-P2 output) and the simulator KPI cards (§5-P1) nearly match but drift:
"high-risk seating formations" (P2 output) vs "risk formations prevented/reviewed" (P1 card); "active healthy tables" vs
"healthy tables at hour 8".

**Recommendation:** One canonical metric-key list, defined once, consumed by both P2's `room_metrics_*.json` and P1's cards.
Clarify whether "risk formations prevented" is computed (from pit-boss action diffs) or just a label.

**Decision:** _______________________

---

## D10 — Taxonomy validation: cluster-first vs assume archetypes 🟡  ⬜ OPEN
**Affects:** P3 (classifier target), P2 (archetype definitions). **Owner:** P3, with P2.

We assumed 9 archetypes (D7) from common sense. The sound way to confirm a taxonomy you're unsure of is **unsupervised
clustering** (K-means to find the count, GMM for soft membership / BIC) → name the clusters → then train the supervised
classifier on them. But our data is **synthetic** — generated *from* the archetype rules — so clustering it mostly
**rediscovers** those rules (circular).

**Recommendation:** Treat clustering as **demonstration, not requirement, on synthetic data** — it validates the *workflow*
on data where we already know the answer, and is a useful rigor artifact ("we didn't just assume 9"). On **real player data
it is essential discovery** and would run before any classifier is trained. The classifier path for the demo stays
multinomial / one-vs-rest on the defined labels. Walkthrough + runnable notebook:
`docs/learn/clustering-walkthrough.html` and `docs/learn/clustering-notebook.ipynb`.

**Decision:** _______________________

---

## Sign-off

| Role | Name | Ratified |
|---|---|---|
| P1 — Product/UX | | ⬜ |
| P2 — Data Sim (this checkout) | Cory | ⬜ |
| P3 — Scoring/Evidence | | ⬜ |
| P4 — AI Investigator/Evals | | ⬜ |

Once all `✅ LOCKED`: update `docs/PRD.md` for any contract changes (D3, D4, D6, D7, D9 touch the spec), then start Day-2
static end-to-end.
