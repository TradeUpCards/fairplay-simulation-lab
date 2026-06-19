# CLAUDE.md — FairPlay Simulation Lab

> Capstone: an **AI simulation lab + operator copilot** for online-poker table health and
> integrity. Read `docs/PRD.md` for the full spec — it is the source of truth for *what* to build.
> This file is the *how we build* and the non-negotiable rules.

## What this is

A loop that proves an AI-assisted system can tell *unhealthy table states* apart from *normal poker
behavior* by combining weak signals — then explains its reasoning safely. The product
**recommends, explains, and lets a human operator decide. It never accuses or auto-enforces.**

The demo spine (never cut any link):

```
lobby recommendation → pit-boss review/override → Standard-vs-FairPlay 8-hour simulation → eval evidence
```

## Hard rules

- **The LLM is never the detector.** Structured scoring finds risk. The AI Investigator receives a
  structured **evidence packet only** (never raw data) and explains it. If you find yourself feeding
  raw player/session rows to the model, stop.
- **AI guardrails (must always hold):** never state a player cheated as fact · never recommend an
  automatic ban/enforcement · distinguish *health risk* from *integrity risk* · only use evidence in
  the packet · explicitly surface counter-evidence · use uncertainty language · always recommend a
  human action. "Elevated for review," never "these players cheated."
- **Player-facing vs. operator-facing separation is load-bearing.** The lobby shows neutral info
  (stakes, seats, pace, "Recommended for you") and **must not** expose numeric health scores, player
  classifications, risk scores, or "predator"/integrity language. That language lives only in the
  pit-boss console.
- **Determinism.** The simulator and scoring are seeded and reproducible. Every important UI state is
  driven by computed scores/reason codes — not hand-written front-end text. A presenter must be able
  to run the whole demo from static fixtures, then swap to computed data without changing the story.
- **The evidence packet is the contract seam.** P4 defines its schema; P3 produces it. Don't let the
  two drift — change the schema in one place.
- **Scope rule:** if it doesn't support a live demo moment, it's not in scope. No new major features
  after Day 1.
- **No secrets committed.** Use `.env` (with a committed `.env.example`). No API keys, no creds.
- **Integrity patterns are *simulated as fields*** (`bot_similarity_score`, `soft_play_delta`, mocked
  device groups). This is responsible-use modeling on synthetic data — **not** real detection, real
  device/location/OSINT, real gameplay/RTA, enforcement, KYC, or real-time routing. Those are
  explicit non-goals.

## The four contracts (the integration seams)

1. **Simulation data** (P2) — players, table roster, sessions/seat events, relationships/mocked
   devices, hourly room metrics, seeded truth labels.
2. **Scores + recommendations** (P3) — player profile, table-health / seating-risk / integrity
   scores, lobby ranking, pit-boss recommendation, reason codes.
3. **Evidence packet** (defined by P4, produced by P3) — `case_id`, `case_type`, `scores`,
   `top_evidence`, `counter_evidence`, `uncertainties`, `recommended_action`, `allowed_actions`.
4. **UI state** (P1) — player lobby, pit-boss view, case detail, simulator comparison, eval panel.

## Ownership

| Lead | Mission |
|------|---------|
| **P1 — Product + Review UX** | the visible product + the click path lobby→pit-boss→simulator; demo deck |
| **P2 — Data Simulation + Scenario** | deterministic synthetic room + two 8-hour counterfactual paths |
| **P3 — Scoring + Evidence Engine** | classification, scores, reason codes, evidence-packet generation, frontend API |
| **P4 — AI Investigator + Evals** | evidence schema, prompts, guardrails, summaries, eval rubric + panel |

## Working agreement

- Build **failing fixtures / contracts first**, then build to green. Day 2 is a fully clickable
  static flow before any real logic exists.
- Keep `docs/PRD.md` authoritative; update it when a contract changes rather than letting code drift.
- Tech stack is **not yet chosen** — do not scaffold app code until it's locked.

## When working with Claude models

Default to the latest, most capable Claude models for the AI Investigator. Check the project's
`claude-api` reference / official docs for current model IDs and pricing before wiring the SDK —
don't hardcode from memory.
