# FairPlay Simulation Lab

> An AI simulation lab and operator copilot for online-poker **table health and integrity**.
> It classifies players, models table health under paid-seat-time economics, predicts risky
> seating, simulates adversarial integrity patterns, and writes grounded case summaries for
> human review — modeling risk **before** damage happens.
>
> **Stance: it recommends, explains, and lets an operator decide. It never accuses or auto-enforces.**

Capstone submission. Build: 7–10 days · 4 people.

---

## The one thing that can't break — the demo spine

```
Player lobby recommendation
  → pit-boss review / override
    → Standard-Room vs. FairPlay-Enabled 8-hour simulation
      → eval evidence
```

If a feature does not support one of the live demo moments, it is out of scope.

## The core idea

A poker room can look active while still being unhealthy: new players get seated into
predatory mixes and leave, casuals churn after a billing interval or two, promo hunters create
low-quality seat-time, linked accounts cluster and soft-play. **Every single signal misleads** —
high overlap isn't collusion, a shared device isn't cheating, a strong player isn't a risk, and
an active-looking table can still be bad.

The hard problem isn't "detect one known cheat pattern." It's whether an AI-assisted system can
**distinguish unhealthy table states from normal poker behavior** by combining weak signals across
player type, composition, paid seat-time, device/session relationships, and false-positive traps.

**The LLM is never the detector.** Structured analytics and scoring find the risk; the AI
Investigator receives a structured *evidence packet* — never raw data — and explains it: why it's
risky, why it's *not* proof, the counter-evidence, and the recommended human action.

## Architecture — 6-layer pipeline

```
L0  Simulator         seeded room, adversarial cases, two 8-hour counterfactual paths
L1  Classify + Graph  player segments · entities · relationships
L2  Health + Integrity features
L3  Scoring           seating risk · integrity risk · reason codes
L4  Evidence Packet   scores + top evidence + counter-evidence + uncertainty + allowed actions
L5  AI Investigator   grounded case summaries
L6  Human Review      queue · detail · operator actions
        ↑
   Eval Harness — seeded truth labels verify true-risk cases rank above false-positive
   traps and that AI summaries don't overclaim.
```

## Three mandatory demo cases

| Case | Expected outcome |
|------|------------------|
| New player + bad table mix (P-104 → Table 22) | Beginner-unfriendly; reroute to Table 8 |
| Coordinated cluster (accounts A/B/C) | Integrity review; hold formation, don't accuse |
| Shared-device household (H1/H2) | Monitor only; **not** escalated (false-positive trap) |

## Ownership (4-person team)

| | Lead | Owns |
|---|------|------|
| **P1** | Product + Review UX | lobby / pit-boss console / case detail / room-impact simulator / eval panel UI, demo deck |
| **P2** | Data Simulation + Scenario | deterministic room, archetypes, sessions, devices, seeded cases, counterfactual outputs, truth labels |
| **P3** | Table Health + Scoring + Evidence | classifier, health/seating/integrity scores, reason codes, evidence-packet generation, frontend API |
| **P4** | AI Investigator + Evals | evidence-packet schema, prompts, guardrails, AI summaries, eval rubric + panel |

The **evidence packet** is the shared seam: P4 defines it, P3 produces it. Final deck + demo script
are jointly owned by P1 + P4. See [`docs/PRD.md`](docs/PRD.md) for the full spec, contracts, and
day-by-day plan.

## Status

- [x] Repo + docs
- [ ] **Stack decision** (deferred — lock before any code)
- [ ] Day 1: lock demo contract (screens, cases, schemas, KPIs)
- [ ] Day 2: static end-to-end clickable flow from fixtures
- [ ] Days 3–6: working logic + counterfactual simulator
- [ ] Days 7–10: stabilize, eval, polish

## Tech stack

**To be decided.** Candidate options under consideration: a TypeScript monorepo
(Vite+React / Node / Anthropic SDK) or a Python sim+scoring core with a React+TS frontend.
Locked in a follow-up before implementation begins.
