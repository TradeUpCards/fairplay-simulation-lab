---
date: 2026-06-21
topic: demo-ui
---

# FairPlay Demo UI

## Summary

A presenter-driven React demo of the FairPlay copilot, built around three views — a **Pit Boss index** that ranks tables healthiest-first and re-ranks live as an 8-hour simulation replays, a **Pit Boss table view** showing each seat's propensity-to-leave (PTL) with the integrity case and counter-evidence folded in for flagged tables, and a **personalized player lobby** — all framed by a **Standard-vs-FairPlay comparison** driven by a recommendation-adherence lever, with Fit scores recomputed live by a FastAPI service, plus a small **eval/proof tab**.

---

## Problem Frame

The capstone has to convince a review panel that an AI-assisted system can tell *unhealthy table states* apart from *normal poker behavior* by combining weak signals — and that it does so **safely**. The hard part a reviewer needs to see isn't catching one cheat; it's that the system models damage *before* it happens, shows the *causal* difference its decisions make, and **refuses to over-accuse** (the shared-device household that looks suspicious but isn't).

Today there is no UI. The technical-approach deck (`docs/index.html`) explains the model — health bands, the router formula, the relationship graph, the eval rubric — but a reviewer can't *see* it work end-to-end, can't watch the Standard-vs-FairPlay outcomes diverge from a shared start, and can't watch the system hold a benign case at monitor instead of escalating it. The demo's job is to make the model legible and the safety stance visible, on the mock fixtures that exist, with little real intelligence wired in yet.

---

## Actors

- A1. Presenter: drives the demo live; needs a hard-to-fail, recoverable flow with no dead ends.
- A2. Pit boss (operator persona): sees true scores, evidence/counter-evidence, and takes review actions.
- A3. Player (e.g., P-104): sees a neutral, personalized lobby; never sees scores or integrity language.
- A4. Capstone reviewer: the audience; judges breadth (does it work end-to-end) and rigor (is it safe and real).
- A5. Scoring engine (FastAPI): recomputes Fit live from table actions using P3's scoring logic.

---

## Key Flows

- F1. Standard-vs-FairPlay run
  - **Trigger:** presenter starts the simulation and sets the adherence lever.
  - **Actors:** A1, A4, A5
  - **Steps:** pick a path / lever value → play the 8-hour clock → KPIs and table rankings update each hour → compare the two paths side-by-side.
  - **Outcome:** the reviewer sees the same room diverge in retention *and* integrity outcomes because of FairPlay decisions.
  - **Covered by:** R1, R2, R3, R4, R5

- F2. Pit-boss triage of the cluster
  - **Trigger:** a flagged table surfaces in the Pit Boss index.
  - **Actors:** A2, A4
  - **Steps:** open the flagged table (T-11) → see per-seat PTL → see convergent evidence grouped by family + counter-evidence + the monitor-vs-escalate call → take an operator action.
  - **Outcome:** the reviewer sees a defensible flag, not a black-box accusation.
  - **Covered by:** R6, R7, R8, R9, R10, R11, R15

- F3. Player routing moment
  - **Trigger:** player P-104 is seeking a seat.
  - **Actors:** A3, A4, A5
  - **Steps:** lobby ranks candidate tables for *this* player (Fit recomputed live) → shows neutral badges (Recommended / Good fit / Available), gated tables hidden → never shows a health number.
  - **Outcome:** the reviewer sees the player-vs-operator wall and personalized routing in action.
  - **Covered by:** R12, R13, R14

- F4. Eval / proof review
  - **Trigger:** presenter opens the eval tab.
  - **Actors:** A1, A4
  - **Steps:** show seeded cases with expected vs. predicted + the safety checks (grounding, no-overclaiming, counter-evidence, action quality).
  - **Outcome:** the reviewer sees the rigor is measured, not asserted.
  - **Covered by:** R16

---

## Requirements

**Simulation & comparison frame**
- R1. Standard and FairPlay paths share the hour-0 starting state and replay over 8 hours from fixtures.
- R2. A single sim-time control (play / pause / scrub, hours 0–8) drives every time-varying view at once.
- R3. A recommendation-adherence lever sets how often players follow FairPlay recommendations, where 0% ≡ the Standard path and 100% ≡ the FairPlay path.
- R4. The comparison surfaces the room KPIs from `room_metrics_*` (paid seat-time, retention, healthy tables, early breaks, reward/fee, high-risk formations) for both paths and their divergence over the run.
- R5. The lever visibly changes both retention outcomes *and* the integrity outcome (low adherence → the cluster forms at T-11; high → the seat is held for review).

**Pit Boss index**
- R6. Lists tables ranked healthiest-first using operator-facing health scores and bands.
- R7. Re-ranks live as the sim clock advances and as the lever changes.
- R8. May show operator-facing context (health band, risk flags) — this view is operator-only.

**Pit Boss table view**
- R9. Shows a table's seat-by-seat composition with each seat's PTL (propensity to leave).
- R10. When a flagged table is opened, surfaces the integrity case inline: convergent evidence grouped by family, counter-evidence, and the resulting monitor-vs-escalate call.
- R11. Offers the operator actions (accept · override · monitor · suppress · escalate) per `docs/PRD.md` §5, drawn from the case's `allowed_actions`.

**Player lobby**
- R12. Lists tables available to a *specific* player, ranked by personalized recommendation (Fit + ΔHealth over a shared table Health), not by raw table health.
- R13. Shows neutral, player-safe info plus a badge (Recommended for you / Good fit / Available); integrity-gated tables are hidden.
- R14. Recomputes Fit live (via the engine) as table actions change the composition.

**Eval / proof tab**
- R15. (cross-flow) Flagged-case views always show uncertainty language and counter-evidence — never a bare accusation.
- R16. Shows the seeded eval cases with expected vs. predicted category and the safety checks: grounding, no-overclaiming, counter-evidence, recommended-action quality.

**Guardrails (cross-cutting)**
- R17. The player lobby never exposes numeric health scores, player classifications, risk scores, or "predator"/integrity language.
- R18. No view states a player cheated as fact or recommends automatic enforcement; integrity language stays operator-only.

**Platform & data**
- R19. The frontend is a React (Vite) SPA; all data and scoring access goes through one async data layer (so live API vs. frozen fixtures is swappable without touching components).
- R20. A FastAPI service wraps P3's pure scoring functions and serves live Fit recomputation; the same functions generate the frozen fixtures, so live and frozen agree.
- R21. The demo runs FastAPI on localhost and retains frozen JSON as a fallback source, so an API failure degrades to fixtures rather than breaking the live demo.
- R22. PTL (per seat) and per-hour table health are produced (derived), since neither exists in the current fixtures.

---

## Acceptance Examples

- AE1. **Covers R3, R5.** Given the adherence lever at 0%, when the run plays to hour 8, then outcomes match the Standard path and the cluster has formed at T-11; at 100%, outcomes match the FairPlay path and the T-11 seat shows held-for-review.
- AE2. **Covers R12, R13, R17.** Given P-104 in the lobby, when tables are ranked, then T-8 reads "Recommended for you," T-22 is de-prioritized or hidden, and no numeric health score appears anywhere player-facing.
- AE3. **Covers R10, R15, R18.** Given the shared-device household table is opened, when viewed, then it is shown as monitor-only with counter-evidence and is not escalated.
- AE4. **Covers R7.** Given the simulation playing, when the clock advances an hour, then the Pit Boss index re-orders as table health changes.
- AE5. **Covers R21.** Given the FastAPI service is unreachable, when the demo loads or runs, then it falls back to frozen fixtures and the flow continues.

---

## Success Criteria

- A reviewer can watch the full spine (lobby → pit boss → simulator → eval) and articulate both the difference FairPlay makes *and* why the system did **not** escalate the household case.
- Moving the adherence lever visibly drives both retention and integrity divergence from a shared starting state.
- The player-vs-operator wall is observable: the same room shows true scores to the pit boss and neutral, personalized recommendations to the player.
- `ce-plan` can proceed without inventing product behavior — views, data sources, guardrails, the action set, and the API/data seam are all specified.

---

## Scope Boundaries

- Real device/location/OSINT, trained-model detection of integrity, enforcement/auto-ban, KYC/AML, and real-time lobby routing — non-goals (the production graph in `docs/graph/` stays out of the demo).
- Promo-abuse and bot-similarity cases beyond what is already seeded — deferred (the PRD cut-first list).
- A standalone Case Detail screen — folded into the Pit Boss table view instead.
- A hardened/cloud-hosted FastAPI deployment — the demo runs on localhost; production API hardening is out of scope.
- High-fidelity visual polish beyond what reads as credible — breadth and rigor are prioritized over pixel polish for this audience.

---

## Key Decisions

- Stack: React (Vite) SPA + a localhost FastAPI live-scoring service (D0 Option B). Justified now that live Fit recompute is a real demo feature; frozen JSON remains the canonical fallback so determinism never depends on a live server.
- Personalized *recommendation*, not personalized *health*: the lobby ranks by Fit + ΔHealth over a shared table Health and never shows the health number (honors the player/operator guardrail and matches the router model in `docs/index.html`).
- Integrity folded into the Pit Boss table view + a lightweight eval tab, rather than separate Case Detail and Simulator screens — keeps the three-view spine while putting rigor where reviewers look.
- One sim clock + the adherence lever drive all time-varying views from shared state.
- Operator actions follow `docs/PRD.md` §5; the integrity band uses `neutral` (not `monitor`), per `docs/graph/fixture-vocab-mapping.md`.
- FastAPI wraps P3's pure scoring functions (the same functions that build the fixtures) to avoid live-vs-frozen drift.

---

## Dependencies / Assumptions

- P3 exposes scoring as pure, file-I/O-free functions the FastAPI layer and the fixture generator both call. Coordination dependency on the P3 teammate.
- PTL (per seat) and per-hour, per-table health must be produced — derived from existing fields or supplied by P3 — since the current fixtures lack both.
- Demo Fit is cheap to recompute per request at this scale (≤250 players × ≤20 tables × 8 hours), so live recompute is performant.
- Running FastAPI on localhost (not over a network) is acceptable for the demo and removes the main live-server failure mode.
- The counterfactual interventions remain a fixed decision-list fixture (DECISIONS D2), so the sim is replayable; scores justify the decisions in the narrative without driving the replay.

---

## Outstanding Questions

### Deferred to Planning

- [Affects R20][Technical] The module boundary / contract between the FastAPI layer and P3's pure scoring functions.
- [Affects R22][Needs research] How PTL and per-hour table health are derived — own formula in the demo vs. supplied by P3.
- [Affects R19, R21][Technical] Whether FastAPI also serves the built static frontend or deploys separately.
- [Affects R3] Lever as continuous vs. discrete steps — default continuous (each value triggers a live recompute); revisit only if a no-server precompute fallback is wanted.
- [Affects R16] Eval-tab data source — default to mock packets/summaries now, swap to P4's real output when available.
