# FairPlay Simulation Lab — Product Requirements

Compiled from the capstone 2-page brief, the Work-Backward Build Plan, and the Live Demo Playbook.
This is the source of truth for *what* to build. `../CLAUDE.md` holds the hard rules and house style.

---

## 1. Product summary

An AI simulation lab and operator copilot for online-poker **table health and integrity**. It
classifies players, models table health under paid-seat-time economics, predicts risky seating,
simulates adversarial integrity patterns, and writes grounded case summaries for human review —
modeling risk *before* damage happens.

- **Type:** copilot · simulation lab
- **Stance:** recommends — never accuses, never auto-enforces
- **Build:** 7–10 days · 4 people

### The problem

A poker room's integrity problem is not just catching collusion after the fact — it's knowing
whether a table composition is healthy *before* the damage happens. Tables decay when new players
are seated into predatory mixes, grinders drive casuals out, promo hunters complete the minimum and
leave, or linked accounts cluster and soft-play each other. Every single signal misleads: high
overlap doesn't prove collusion, shared devices don't prove cheating, a strong player isn't
automatically a risk, and an active-looking table can still be bad if players leave the moment they
qualify.

**The hard problem:** not "can we detect one known cheat pattern?" but whether an AI-assisted system
can distinguish unhealthy table states from normal poker behavior by combining weak signals across
player type, composition, paid seat-time, device/session relationships, and false-positive traps.

### Angle vs. prior art

Mature integrity systems detect bots/collusion/RTA/multi-accounting from real account/device/
location/hand signals with a high burden of proof — that's their home turf. FairPlay's different
angle: model **table health before damage** under paid-seat-time economics, predict risky seating,
and run an **AI investigation layer** — proven on simulated data and evals, not raw detection.

Three pillars: **Table Health Model** (healthy → integrity-candidate) · **Integrity Pattern Lab**
(simulated soft-play, clusters, promo abuse, bot-like similarity) · **AI Investigator** — the LLM
builds the case; the human judges it.

---

## 2. Architecture

Structured analytics and ML-style scoring find the risks; the AI Investigator explains them. The LLM
receives structured evidence, not raw data.

```
L0  Simulator (P2)         seeded room · adversarial cases · two 8-hour counterfactual paths
L1  Classify + Graph (P3)  segments · entities · relationships
L2  Health + Integrity (P3) features
L3  Scoring (P3)           seating risk · integrity risk · reason codes
L4  Evidence Packet        P4 defines schema · P3 produces · + counter-evidence
L5  AI Investigator (P4)   grounded case summaries
L6  Human Review (P1)      queue · detail · operator actions

Eval Harness (P4) — seeded truth labels verify true-risk cases rank above false-positive
traps and that AI summaries don't overclaim. Fed by both the evidence packet and the LLM output.
```

Three risk lenses:
- **Table health** — survival · seat-time · retention · skill mix · new-player risk
- **Seating risk** — player + mix · predicted impact · reason codes · routing
- **Integrity risk** — linkage · co-seating · soft-play · bot similarity · false-positive offset

---

## 3. The demo spine (do not cut)

```
lobby recommendation → pit-boss review/override → with-vs-without simulation → eval evidence
```

**Scope rule:** if it does not support one of the live demo moments, it is not in scope.

---

## 4. Shared integration contracts

```
simulation data → scores & recommendations → evidence packet → player/pit-boss/simulator UI → AI summaries & evals
```

### Contract 1 — Simulation data (produced by P2)
players · table roster and properties · sessions and seat events · player relationships / mocked
devices · hourly room outcome metrics · seeded truth labels

### Contract 2 — Scores and recommendations (produced by P3)
player profile · table health score · seating risk score · integrity risk score · lobby ranking
recommendation · pit-boss recommendation · reason codes

### Contract 3 — Evidence packet (defined by P4, produced by P3)
```json
{
  "case_id": "",
  "case_type": "",
  "scores": {},
  "top_evidence": [],
  "counter_evidence": [],
  "uncertainties": [],
  "recommended_action": "",
  "allowed_actions": []
}
```

### Contract 4 — UI state (produced by P1)
player lobby · pit-boss view · case detail · simulator comparison · eval panel

---

## 5. Ownership & must-builds

### P1 — Frontend, Product Flow, Demo Lead
Owns: player lobby UI · pit-boss console UI · case queue/detail UI · room-impact simulator UI · eval
panel UI · operator override interactions · lobby ranking/highlight interactions · demo copy/deck.

**Player Lobby** — each card shows: stakes/game type · seats filled & open · table running time ·
average pot size · average session length · pace · style/volatility label · FairPlay recommendation
badge where relevant.
The lobby **must not** show: numeric table-health score · player classifications · risk scores ·
"predator"/integrity language · individual player performance data.

**Pit Boss Console** — must display: table health · seating risk · integrity risk · player/table
composition · reason codes · evidence/counter-evidence · AI summary · recommended action.
Operator actions: accept · override · monitor · suppress table for a specific player · escalate.

**Room Impact Simulator** — Standard Room vs. FairPlay Enabled comparison · eight-hour cumulative
paid-seat-time chart · KPI cards (total paid seat-time · projected end-of-day seat-time · new-player
retention · average casual session · healthy tables at hour 8 · early table breaks · risk formations
prevented/reviewed · reward/fee ratio) · current simulated hour · scenario toggle / side-by-side.

**Definition of done:** a presenter can run the whole visual demo from static fixtures on Day 2,
then swap to computed data without changing the storyline.

### P2 — Simulation, Scenario, Counterfactual Data Lead
Owns: player population & archetypes · table state · sessions/seat events · mocked devices &
relationships · paid seat-time & six-minute intervals · rewards/promo events · seeded cases · room
simulation outputs · ground-truth labels.

Core population: 100–250 players · 10–20 tables · eight simulated hours. Archetypes: new ·
recreational · regular · grinder · aggressive/predatory · promo hunter · shared-device household ·
coordinated-cluster member · healthy anchor.

Required table fields: table ID · stakes · game type · max seats · seated players · running time ·
average pot size · average session length · hands/hour or pace label · style/volatility label · paid
seat-time trend.

**Output files:** `room_state_hourly.json` · `room_metrics_standard.json` ·
`room_metrics_fairplay.json` · `seeded_case_labels.json`. Each hourly metrics file includes:
cumulative paid seat-time · active players · active healthy tables · new-player retention · average
casual session length · early table breaks · projected end-of-day paid seat-time · reward/fee ratio ·
high-risk seating formations.

**Definition of done:** the two simulated paths share identical starting conditions and produce a
clear, internally consistent difference *because of* defined FairPlay decisions.

### P3 — Scoring, Recommendations, Evidence Engine Lead
Owns: player classification · table-health / seating-risk / integrity scoring · lobby ranking logic ·
pit-boss action logic · reason codes · evidence-packet generation · frontend data adapter/API.

- **Classification:** new/onboarding · recreational · regular · grinder · aggressive/predatory ·
  promo hunter · cluster candidate · shared-device low-risk · healthy anchor.
- **Table-health score:** numeric + band (healthy · fragile · beginner-unfriendly · promo-abuse
  prone · integrity-review candidate) + reason codes.
- **Seating/lobby rec:** per candidate table — ranking position · badge (Recommended for you / Good
  fit / Available) · risk level · neutral player-facing copy · operator reason codes · alternate
  table.
- **Integrity score:** low / monitor / high / manual review · recommended containment · counter-evidence.

**Required behavior:**
- P-104 → Table 8 *Recommended for you*, Table 14 *Good fit*, Table 22 *Available, de-prioritized internally*.
- Cluster C → don't surface current table as available; recommend pit-boss review before completing formation.
- Household H1/H2 → monitor only; no suppression, no enforcement.

**Definition of done:** every important UI state is driven by deterministic scores/reason codes, not
hand-written front-end text.

### P4 — AI Investigator, Evals, Trust Layer Lead
Owns: evidence-packet schema · prompt design · AI summaries · counter-evidence language · action
recommendations · guardrails · eval rubric · eval results/data · presenter talking points.

**Required AI outputs per case:** plain-language summary · why it's risky · why it's *not* proof ·
counter-evidence / innocent explanation · recommended human action · suggested next check.

**Guardrails (AI must):** never say a player cheated as fact · never recommend automatic
ban/enforcement · distinguish health from integrity risk · use only evidence in the packet ·
explicitly mention counter-evidence when relevant · use uncertainty language · recommend human action.

**Eval panel per seeded scenario:** expected category · predicted category · grounding pass/fail ·
no-overclaiming pass/fail · counter-evidence pass/fail · recommended-action quality score.

**Definition of done:** the AI visibly adds judgment and safety — it explains not only why something
is risky, but why it may still be innocent and what a human should do next.

---

## 6. Demo fixtures (the three mandatory cases)

### New Player Case
P-104 (new player) · Table 22 (short-handed, high volatility, two aggressive/high-volume players) ·
Table 8 (balanced, healthier alternative) · comparable retention outcomes for both table types.

Worked pit-boss evidence for Table 22: table health 38/100 · new-player seating risk High · occupancy
3/6 · 2 high-volume/aggressive profiles · comparable new-player session 12 min vs. healthy-table 42
min · predicted state Fragile/beginner-unfriendly.

### Coordinated Cluster Case
Accounts A, B, C · A/B device linkage · C timing correlation · repeated co-seating (14 of 18 recent
tables) · within-cluster soft-play · outsider-pressure pattern · high casual-exit impact.
Counter-evidence: no individual signal proves collusion. → hold the third seat for pit-boss review.

### Shared-Device False Positive
Household H1/H2 · same device · little co-seating · different session patterns · no suspicious
interaction · no correlated profitability · no casual-exit increase. → **monitor only, do not escalate.**

### Counterfactual runs (same starting state)
- **Standard Room:** P-104 joins Table 22 · cluster account C joins A/B · no risk-aware routing · no pit-boss intervention.
- **FairPlay Enabled:** P-104 gets Table 8 · pit boss accepts cluster containment · Table 22 not promoted to new/rec players · cluster formation held for review.

---

## 7. Seven seeded eval cases

| | Scenario | Expected |
|---|----------|----------|
| A | New player + bad table mix | detected & rerouted (beginner-unfriendly) |
| B | Strong/valuable grinder | flagged room-health concern, **not** integrity |
| C | True coordinated cluster | ranked high on convergence → integrity review |
| D·E | Regular overlap & shared device | **not** over-escalated (low/medium; monitor) |
| F | Promo abuse | labeled distinctly, **not** collusion |
| G | Bot-like similarity | routed to its own review |

Plus an LLM rubric: evidence grounding · no overclaiming · health-vs-integrity separation · innocent
explanations · clear human action.

---

## 8. Scope

### Minimum shippable product
simulator · classifier · table-health score · seating-risk · relationship graph · integrity scoring ·
case queue + detail · evidence packet · LLM summaries · eval panel · demo script + diagram.

### Must have
lobby recommendations · pit-boss rationale & override · new-player bad-mix case · coordinated cluster
case · shared-device false positive · Standard-vs-FairPlay simulator · grounded AI case summaries · eval panel.

### Nice to have
promo-abuse case · bot-like pattern case · interactive relationship graph · reviewer Q&A · more
advanced forecasting.

### Cut first (in order)
bot-like case → promo-abuse case → interactive graph polish → reviewer chat → extra table/player segments.

### Non-goals
real gameplay/solver/RTA detection · real device/location/OSINT providers · enforcement/auto-ban ·
payments/KYC/full rewards platform · real-time lobby routing. Integrity patterns are *simulated as
fields* — responsible use, not real detectors.

---

## 9. Day-by-day plan

| Days | Focus | Checkpoint |
|------|-------|-----------|
| **1** | Lock demo contract: screens, 3 cases, lobby fields, sim assumptions, scores/actions, evidence schema, KPIs, narrative. **No new major features after Day 1.** | contract agreed |
| **2** | Static end-to-end: P1 clickable frontend on static JSON · P2 fixtures (3 cases + 2 paths) · P3 score fixtures · P4 mock packets/summaries/eval rows | click lobby → pit boss → cluster → false positive → simulator → eval panel? |
| **3–4** | Working logic: P2 generator v1 · P3 computes scores · P1 wires real contracts · P4 summaries from structured evidence | computed scores + generated fixtures for all mandatory cases? |
| **5–6** | Counterfactual simulator: P2 finalizes both paths · P3 intervention rules · P1 comparison screen · P4 eval results | same room shows an 8-hour difference with/without FairPlay? |
| **7–8** | Stabilize: remove non-demo work · lock case outputs · screenshots/video backup · rehearse | — |
| **9–10** | Polish only: UI/deck · timing · bug fixes · backup verification. No new modules unless all mandatory elements stable. | — |

---

## 10. Deferred decision

**Tech stack is not yet chosen.** Lock it before Day-2 implementation. Candidates: TypeScript
monorepo (Vite+React / Node / Anthropic SDK) vs. Python sim+scoring core with a React+TS frontend.
