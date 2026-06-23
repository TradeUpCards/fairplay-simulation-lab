# CLAUDE.md — FairPlay Simulation Lab

> An **AI simulation lab + operator copilot** for online-poker table health and integrity. Read
> `docs/PRD.md` for the full spec — it is the source of truth for *what* to build. This file is the
> *how we build* and the non-negotiable rules.

## What this is

A loop that proves an AI-assisted system can tell *unhealthy table states* apart from *normal poker
behavior* by combining weak signals — then explains its reasoning safely. The product
**recommends, explains, and lets a human operator decide. It never accuses or auto-enforces.**

The demo spine (never cut any link):

```
lobby recommendation → pit-boss review/override → Standard-vs-FairPlay 8-hour simulation → eval evidence
```

## How this is built

One owner, handling all of it. There is no role split to coordinate across and no one to defer to —
**make the call and move.** The codebase is:

- `scoring/` — the Python scoring engine (classification, table health, integrity, seating, router).
  Calibrated and deterministic; the canonical source of truth for every score. `scripts/build_*.py`
  freeze its output to `data/derived/*.json`.
- `frontend/` — the Vite/React/TS SPA. Binds the frozen `data/derived/*.json` via the typed seam in
  `frontend/contract2.d.ts`, with the data layer (`src/data/shim.ts`) the single swap point.
- `api/` — an optional FastAPI service that wraps the same `scoring/` engine to recompute scores
  on the fly and stream them to the frontend (SSE). The frontend falls back to the static JSON when
  it's offline.
- `data/` — the synthetic room (players, roster, sessions, relationships, room metrics, seeded
  labels) plus the frozen `derived/` scores.

Don't re-introduce a multi-person ownership story or "coordinate with X before touching Y" gates —
that framing was removed on purpose because it stalled decisions.

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
  pit-boss console. (Enforced in types by `LobbyTable` / the `OperatorOnly` brand.)
- **Determinism.** The simulator and scoring are seeded and reproducible. Every important UI state is
  driven by computed scores/reason codes — not hand-written front-end text. A presenter must be able
  to run the whole demo from static fixtures, then swap to computed/live data without changing the story.
- **The evidence packet is the contract seam.** Its schema is defined in exactly one place — don't let
  the producer and consumer drift; change the schema once.
- **Scope rule:** if it doesn't support a live demo moment, it's not in scope.
- **No secrets committed.** Use `.env` (with a committed `.env.example`). No API keys, no creds.
- **Integrity patterns are *simulated as fields*** (`bot_similarity_score`, `soft_play_delta`, mocked
  device groups). This is responsible-use modeling on synthetic data — **not** real detection, real
  device/location/OSINT, real gameplay/RTA, enforcement, KYC, or real-time routing. Those are
  explicit non-goals.

## The integration seams

The data contract that holds the pieces together (the typed shapes live in `frontend/contract2.d.ts`):

1. **Simulation data** — players, table roster, sessions/seat events, relationships/mocked devices,
   hourly room metrics, seeded truth labels (`data/*.json`).
2. **Scores + recommendations** — player classification, table-health / seating-risk / integrity
   scores, lobby ranking, pit-boss recommendation, reason codes (`data/derived/*.json`).
3. **Evidence packet** — `case_id`, `case_type`, `scores`, `top_evidence`, `counter_evidence`,
   `uncertainties`, `recommended_action`, `allowed_actions`.
4. **UI state** — player lobby, pit-boss view, case detail, simulator comparison, eval panel.

## Working agreement

- Build **failing fixtures / contracts first**, then build to green.
- Keep `docs/PRD.md` authoritative; update it when a contract changes rather than letting code drift.
- The frontend gate is `tsc --noEmit` + `vite build` + the Vitest suite; keep them green.

## When working with Claude models

Default to the latest, most capable Claude models for the AI Investigator. Check the project's
`claude-api` reference / official docs for current model IDs and pricing before wiring the SDK —
don't hardcode from memory.
