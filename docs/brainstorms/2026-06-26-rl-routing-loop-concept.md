# Concept brief — a learning loop for the routing/scoring strategy

**Date:** 2026-06-26
**Status:** concept brief (NOT a PRD yet). Posted to invite owners. If it gets traction
it graduates to a `docs/brainstorms/*-prd.md` work-order like #59/#60.
**Raised by:** Cory (P3, scoring/routing) + Sargon (playsim; offered to lead the agentic
angle). **Open invite:** Jordan / Dean.
**Audience:** the team — decide if this is worth owning, and who owns it.

---

## One line

Close the loop on routing: *propose a policy → run the seeded sim → measure → update →
repeat* — with a deterministic optimizer at the core and an optional LLM "research
scientist" on top that hypothesizes changes, reads results, and explains *why*.

## Why now (grounded, not hypothetical)

We are already running this loop **by hand**. The diagnostic work this week
(`playsim-fairplay-retention-preregistration.md`) is exactly: pre-register → sweep the
sim → interpret the metrics → propose the next change. Two findings make a learning loop
worth considering:

1. At large-room scale, **Standard (most-full) beats FairPlay on the naive metric**
   (total paid seat-hours), and FairPlay-liveness doesn't overtake (#65: 1672 vs 1680).
2. The reason is structural: the metric rewards concentration and the sim has **no
   health→retention feedback loop** (`runner.py:cohort_should_leave` ignores table
   health). The router's knobs (`router.py` weights `0.30/0.40/0.30`, health floors,
   formation-willingness) are a real search space we are currently exploring manually.

A loop could (a) search that space far more thoroughly than we can by hand, and (b) — the
interesting part — *reason about which mechanism is missing*, not just tune numbers.

## Deterministic vs agentic — the honest decomposition

These are **separable layers**; don't conflate them.

- **The optimization is deterministic.** "policy → seeded sim → reward → update" over a
  deterministic environment is a textbook closed loop. Cross-entropy method / bandit /
  Bayesian opt / simple policy-gradient over the router params. **No LLM required.** Fits
  our determinism rule perfectly. This is the rigorous core and ships value alone.
- **The agentic layer is the research scientist, not the router.** An LLM agent that
  proposes policy/mechanism *hypotheses*, designs the experiment, calls the sim as a
  tool, reads the structured metrics, reasons about *why* a policy failed, proposes the
  next variant, and writes the findings. This is a genuine agentic use case
  (closed-loop automated experimentation), and it's where an LLM beats blind search:
  hypothesis generation + qualitative "why" over a combinatorial design space.

**Load-bearing rule:** the agent *optimizes and interprets*; the deterministic scoring
stays the detector/router. If the LLM ever becomes the routing function, we've violated
CLAUDE.md ("the LLM is never the detector") — stop.

## What we could implement (MVP → ambitious)

1. **Deterministic optimizer (honest core).** CEM/policy-gradient over the router knobs,
   reward = a sim metric. Cheap, rigorous, demo-able on its own.
2. **Agentic research loop.** One agent, two tools (`run_sweep`, `read_metrics`),
   iterating N rounds under a pre-registration guardrail: hypothesize → simulate →
   interpret → write up. Output is a findings log a human reviews.
3. **Hybrid (recommended).** Agent decides *what to search and why* (mechanism design,
   hypothesis generation, interpretation); the deterministic loop does the reward
   optimization. The division of labor is itself the architecture story.

## The trap that must be designed around (headline)

**Reward-objective gotcha.** If the reward is **total paid seat-hours**, the loop just
rediscovers **most-full (Standard)** — because the metric rewards concentration and the
sim has no health→retention loop. So a learning loop is only meaningful **after / paired
with** the structural retention mechanism (the thing we pre-registered). Building the
loop first would burn weeks learning "concentrate everyone." This idea **depends on**
the retention-mechanism work, not the other way around.

## Guardrails (built in, not bolted on)

- **LLM never the detector/router.** Agent hypothesizes & interprets; deterministic
  scoring routes.
- **Anti-reward-hacking / anti-p-hacking at machine speed.** An agent optimizing "make
  FairPlay win" is automated p-hacking. The reward must be an *honest* objective (e.g.
  vulnerable retained seat-time under a mechanism calibrated to an external anchor), with
  pre-registration and full-grid reporting baked into the loop itself.
- **Determinism / reproducibility.** Seeded env, logged configs, replayable.
- **Synthetic-data caveat stays visible.** Illustrative — never a validated retention claim.

## MVP scope (if someone takes it)

- Wrap the existing `large-room-sweep` as a callable reward oracle (it already emits the
  metrics: total + vulnerable seat-hours, breaks, balks, formation activations).
- A deterministic CEM/bandit over ~4–6 router knobs; report the search trace + best config
  vs Standard, full grid.
- *Optional* agent wrapper that proposes the next knob region + a one-paragraph rationale
  each round and writes a findings log.
- Hard dependency note: pair with the health→retention mechanism so the reward is honest.

## Open questions for the team

1. **Agentic or deterministic first?** (Recommend: deterministic core MVP, agentic layer
   as a fast-follow once the reward objective is honest.)
2. **What's the reward objective?** (Total seat-hours is a trap; vulnerable retention
   needs the mechanism first.)
3. **Who owns it?** Sargon offered to lead the agentic angle; Cory owns scoring/routing.
   Jordan/Dean welcome.

## The ask

Is this worth a work-order? If yes, who's in? If there's interest, the next step is
promoting this brief to a PRD and pre-registering the reward objective before any tuning.

## Related

- `docs/learn/playsim-fairplay-retention-preregistration.md` — the manual version of this loop.
- `docs/brainstorms/2026-06-25-liveness-aware-routing-and-formation-prd.md` (#59) — the policy knobs.
- `docs/learn/playsim-large-room-simulation.md` (#64) + #65 — the sim scale + current benchmark.
