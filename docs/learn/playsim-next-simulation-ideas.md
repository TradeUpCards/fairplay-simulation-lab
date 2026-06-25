# Playsim Next Simulation Ideas

**Date:** 2026-06-25
**Status:** proposal for team discussion
**Audience:** FairPlay Simulation Lab team

## TL;DR

We have two promising directions that serve different goals:

1. **DES Room Economics Simulator** - use playsim for believable poker mechanics, then use a fast
   discrete-event simulation layer to run thousands of room-days and stress-test seating economics.
2. **Poker Training Game** - build a human-playable poker experience against configurable AI bots,
   turning the agent seam into a capstone-quality interactive product.

The first idea strengthens the FairPlay business case. The second idea strengthens the AI/product
demo and gives us a technically ambitious user-facing project.

## Idea 1: DES Room Economics Simulator

**Tagline:** playsim explains behavior; DES scales it into room economics.

**Summary:** Build a lightweight discrete-event simulation (DES) above playsim. Instead of dealing
every hand for every experiment, model the room as events: arrival, seat, decline, leave, re-seat,
table break, wait timeout, and session completion. Use playsim to produce grounded priors, then use
DES to run thousands of simulated room-days quickly.

### Why This Is Worth Considering

Our current playsim work is strongest when we need believable mechanics:

- hand-by-hand poker play,
- archetype behavior emerging from actual decisions,
- table thinning and break dynamics,
- loss/tilt/session signals,
- re-seat behavior and leave reasons,
- calibration priors for churn, wait tolerance, bad-fit decline, and table pressure.

That fidelity is valuable, but it is expensive. If we want to answer business-scale questions, we
need many more runs:

- How often do tables break?
- How much paid seat-time does each routing policy generate?
- How sensitive is FairPlay to arrivals, patience, table fullness, and re-seat behavior?
- How does the Standard-vs-FairPlay gap behave across 10,000 simulated room-days, and how sensitive is it to the assumptions?
- What happens if liquidity is tighter or looser?
- What has to be true for FairPlay to win?

A DES layer is the right tool for that class of question because room activity is naturally event
driven. Players arrive, choose seats, leave, wait, retry, or time out at irregular moments. We do not
need full hand-by-hand poker for every scenario sweep.

### Relationship to the room simulator we already have

DES is an **evolution of the shipped room simulator, not a new thing.** The current closed-loop room
sim already models arrivals, seating policies, the leave model, table breaks, re-seek, the acceptance
funnel, and break/churn metrics — but it deals *every hand* on PokerKit (~3 min per run), so it can't
do thousands of room-days and reports means over a few seeds, not confidence intervals. DES is
essentially **the same room loop minus the hand-dealing**: replace "play the hand" with a transition
probability (calibrated from playsim), and the same event skeleton runs orders of magnitude faster.
So DES doesn't invent new outputs — it scales analyses we already produce at small N and adds real CIs.

**Single source of truth (load-bearing).** The DES transition rates must be *derived from the same
calibrated behavioral parameters* as the room sim (the `PlayerBehaviorPolicy` / fit-aware model), not
independently invented — otherwise we end up with two behavioral models that can quietly contradict
each other, violating our "model the behavior once" discipline.

### The Proposed Architecture

```text
playsim
  hand-level poker mechanics
  small closed-loop room simulations
  observed proxy rates and behavioral priors
        |
        v
calibration parameters
        |
        v
DES room economics simulator
  arrivals
  seating
  leave reasons
  re-seat attempts
  table breaks
  wait timeouts
  paid seat-time
  Monte Carlo policy comparison
```

The DES layer should not replace playsim. It should consume assumptions from:

1. playsim-derived priors,
2. real Hijack data when available,
3. explicit sensitivity ranges when neither exists.

The validity of any DES verdict depends entirely on which of these it runs on. **(1) playsim-derived
priors make DES a *faster way to explore our own assumptions* — it inherits playsim's hand-authored
leave model, so a "FairPlay wins/loses" result from this source is not independent evidence; it's the
same baked-in story at scale.** Only **(2) real data** breaks that circularity and makes a retention
verdict meaningful. **(3) sensitivity ranges** answer the genuinely useful question — *what would have
to be true for FairPlay to win, and how robust is that* — without claiming any of it is validated. Lead
with (3), treat (1) as coverage not proof, and reserve verdicts for (2). See
`docs/learn/playsim-calibration-data.md`.

### Call It a Seat Economics Model, Not a Game Proxy

The risky version of this idea is too simplistic:

> Fish sits with Shark -> Fish churn probability increases by X%.

That can become hand-wavy fast. A stronger framing is a **Seat Economics Model** or **Table Pressure
Model**. It does not pretend to play poker. It estimates transition probabilities based on table and
player context.

Possible inputs:

- table fullness,
- player archetype mix,
- vulnerable-player exposure,
- recent loss rate,
- seat wait time,
- table break risk,
- player reason for leaving,
- re-seat tolerance,
- policy assignment.

Possible outputs:

- accept probability,
- churn probability,
- re-seat probability,
- wait-balk probability,
- expected paid seat-time,
- table survival probability.

### What It Could Produce

The output should look less like "one simulation result" and more like a decision surface:

- Standard vs FairPlay paid seat-time distributions,
- table-break rate by policy,
- re-seat funnel by leave reason,
- sensitivity sweeps over arrival rate and liquidity,
- confidence intervals across simulated room-days,
- break-even assumptions for FairPlay to outperform most-full routing.

This gives us investor/stakeholder-friendly economics without pretending the assumptions are already
validated.

### What It Proves, And What It Does Not

It can support:

- whether a routing policy wins under a stated set of behavioral assumptions,
- whether the result is robust across a range of assumptions,
- which assumptions matter most,
- what data we need from a real operator to validate the model.

It does not prove:

- that the behavioral assumptions are true,
- that FairPlay improves retention in production,
- that a modeled churn coefficient reflects real poker psychology.

The honest language should be:

> Here is the range of outcomes under explicit behavioral assumptions.

Not:

> This proves FairPlay improves retention.

**Scale is not validity.** Running 10,000 room-days does not make an uncalibrated result more true — it
only maps the assumption space more finely. Like the room sim, DES outputs stay **illustrative until
calibrated against real data** (`docs/learn/playsim-calibration-data.md`). If the goal is genuinely to
*strengthen the FairPlay business case*, the highest-leverage move is still securing operator data or a
pilot; DES is the analysis tool that sits on top of that data, not a substitute for it.

### MVP Shape

An MVP could be small:

- a `playsim/des/` or `playsim/playsim/des.py` module,
- a seeded event queue,
- a simple `SeatEconomicsModel`,
- Standard, Random, FairPlay, and most-full policies,
- JSON output with summary metrics,
- an analysis script that runs 1,000+ room-days and emits confidence intervals.

The first milestone should answer one question:

> Under reason-aware re-seating assumptions, how often does FairPlay lose because of liquidity vs
> because of table quality?

## Idea 2: Poker Training Game

**Tagline:** turn our agent seam into a playable AI poker coach.

**Summary:** Build a single-player poker training game where a human plays against configurable bots.
The product value is training: players learn to recognize styles, adapt strategy, and review mistakes.
The capstone value is AI: configurable agents, optional RL-trained bots, and a realistic multi-agent
game loop.

### Why This Is Worth Considering

This is a different kind of win than the DES idea. DES helps prove the FairPlay economics story.
The training game helps create a user-facing AI product.

**Be clear-eyed: this is largely orthogonal to FairPlay's mission.** FairPlay is a table-health /
integrity copilot; a poker *training coach* reuses the same engine (PokerKit + the `act()` seam) but
is a fundamentally different product with a different user. That's perfectly fine for a capstone, but
the team should pick it knowing it advances the *capstone/AI-demo* goal far more than the *FairPlay
product* goal — they share an engine, not a thesis.

It could satisfy a capstone requirement for technical ambition because poker is genuinely hard:

- imperfect information,
- stochastic outcomes,
- multi-agent strategy,
- bluffing and deception,
- hidden state,
- long-horizon skill evaluation,
- real-time human interaction,
- explainable feedback after each hand.

Most teams would struggle to build a realistic, playable, instructive poker experience with agents.
That is exactly why it could be a strong capstone project.

### Product Concept

The user sits at a poker table and plays against bots with different styles:

- **The Rock:** tight, high fold frequency, low aggression.
- **The Maniac:** loose, aggressive, high bluff rate, high variance.
- **The Calling Station:** calls too wide, rarely bluffs, punishes impatient players.
- **The Grinder:** selective, positional, value-heavy.
- **The Predator:** targets weak or tilted players.
- **The Solver-Like Bot:** optional trained/RL baseline or stronger policy.

The point is not just to beat bots. The point is to teach adaptation:

- "This opponent over-folds to turn pressure."
- "You are calling too wide against a value-heavy bot."
- "This table mix rewards patience, not bluffing."
- "You are losing money in dominated second-pair spots."

### Architecture Options

There are two plausible paths.

**Option A: Build on our playsim engine.**

This keeps PokerKit and the current `ArchetypeAgent.act(obs, rng)` seam. It is probably the fastest
path to a demo because we already have:

- poker hand execution,
- archetype knobs,
- agent decisions,
- hand records,
- feature extraction,
- room/table state concepts.

The main work would be productization:

- human player action UI,
- bot selection,
- table state rendering,
- hand history review,
- training feedback,
- difficulty presets,
- persistence/session stats.

**Option B: Use PettingZoo/RL interfaces for bot training.**

PettingZoo is a standard multi-agent reinforcement learning API. Its docs describe sequential
turn-based environments through the AEC API and simultaneous environments through the Parallel API.
It also includes classic poker environments, including Texas Hold'em and Texas Hold'em No Limit,
which wrap RLCard. The CleanRL tutorial shows how to implement PPO for PettingZoo environments.

This path is better if the core goal is a real RL training project:

- train or adapt a PPO/DQN-style bot,
- compare learned bots against heuristic bots,
- use standard MARL tooling,
- make the project legible as an AI-agent capstone.

The tradeoff is that PettingZoo's built-in No-Limit Hold'em environment is a two-player RL environment
with a discrete action space. A polished multi-seat poker training game may still need our own
PokerKit/playsim table layer for product realism.

**GTO caution:** a true GTO bot is not an MVP feature. We can use "solver-like" as a product label
for a stronger trained or benchmarked policy, but the team should avoid claiming mathematically
optimal play unless we actually integrate and validate against a solver abstraction.

### Recommended Hybrid

Use playsim/PokerKit for the playable product surface. Use PettingZoo/RLCard/CleanRL as the training
and benchmarking layer for selected bots.

```text
Human training game
  UI + PokerKit/playsim table loop
  configurable bot personalities
  hand replay and feedback
        |
        v
Bot policy seam
  heuristic ArchetypeAgent
  exploitative/adaptive variants
  optional RL-trained policy adapter
        |
        v
Training/benchmark layer
  PettingZoo/RLCard environments
  CleanRL/PPO experiments
  bot evaluation reports
```

This lets us ship something playable while still having a credible AI research component.

### Difficulty Should Be More Than Easy/Medium/Hard

Difficulty should be tied to exploitability and adaptation:

- **Beginner:** static bot with obvious leaks.
- **Intermediate:** fewer leaks, basic positional awareness, more balanced aggression.
- **Advanced:** detects simple user patterns and changes strategy.
- **Expert/solver-like:** trained or benchmarked policy, less exploitable, fewer obvious mistakes.

Useful knobs:

- fold frequency,
- preflop aggression,
- bluff rate,
- value-bet threshold,
- call-down looseness,
- positional awareness,
- adaptation speed,
- opponent-model memory,
- tilt exploitation.

The training game should expose styles, not just strength. A player learns more from facing a bad
but specific opponent than from facing a generic "hard" bot.

### What Would Make It Technically Innovative

The innovation is not just "poker against bots." The stronger version is:

- configurable bot personalities,
- adaptive opponents,
- post-hand coaching,
- replayable hand histories,
- explainable bot tendencies,
- skill progression over sessions,
- optional RL-trained agent behind the same policy seam,
- comparison between heuristic and learned bots.

The demo story becomes:

> We built an AI poker lab where agents do not just simulate room economics; they become opponents a
> human can train against.

### The central technical risk: coaching quality

Of everything above, **post-hand coaching is the make-or-break — and the hardest part.** Beating bots
is easy; explaining *why* a decision was a mistake credibly is not. Good feedback needs per-decision
EV/equity analysis (e.g., Monte-Carlo equity vs the opponent's range) or an LLM narrator over a
structured hand summary — and either is a real build. A training game whose coaching is shallow
("you should have folded") will read as thin in a demo no matter how polished the table UI is. Treat
coaching as the core deliverable to de-risk first, not a feature bullet to add at the end. (Note: an
LLM *coach* is fine — the "LLM is never the detector" rule is about risk detection, not teaching.)

### MVP Shape

An MVP should avoid overbuilding:

- heads-up or 3-player table first,
- one human vs 1-2 bots,
- 3 bot styles,
- fixed blinds and stack sizes,
- basic hand review,
- simple feedback rules,
- no real-money language,
- no multiplayer,
- no account system.

The first milestone should answer one question:

> Can a user play 20 hands against distinct bot styles and come away understanding what each bot is
> doing differently?

## How To Decide Between These Ideas

Pick **DES** if the team wants to strengthen the FairPlay routing and business-economics argument.
It is closer to our current playsim work and likely lower product risk.

Pick **Poker Training Game** if the team wants a more visible AI product and a more ambitious capstone
demo. It is higher risk, but more user-facing and easier for non-technical reviewers to understand.

**Rough effort (the asymmetry matters).** DES MVP is *small* — days, not weeks — because it reuses the
shipped room loop and the same behavioral parameters; the new work is the event queue and the analysis
harness. The training game is *materially larger* — weeks — dominated by the human-play UI, the table
loop, and (the real cost) coaching quality. DES is a fast analytical win on top of existing work; the
game is a sustained product build on a new surface.

They are not mutually exclusive, but they should not be started at the same time unless ownership is
clear. A practical split would be:

- DES as the next analytical/research track.
- Training game as a separate capstone/product track.

## Suggested Team Discussion Questions

- Are we trying to prove FairPlay economics or build an AI product demo?
- Do we need stakeholder confidence intervals, or a playable capstone?
- Do we have enough time to build a polished human-facing UI?
- Should RL be required for the training game, or optional behind the policy seam?
- What real Hijack data would most improve the DES calibration?
- Which idea best fits the grading rubric and company narrative?

## References

- Current playsim engine reference: `docs/learn/playsim-engine.html`
- Current room simulator guide: `docs/learn/playsim-room-simulator-guide.html`
- Current room-routing findings: `docs/learn/playsim-room-routing-findings.md`
- Calibration data note (why scale ≠ validity; the path to real data): `docs/learn/playsim-calibration-data.md`
- Behavioral model spec (the calibrated params DES should derive from): `docs/brainstorms/2026-06-24-behavioral-fidelity-fit-model-requirements.md`
- PettingZoo docs: https://pettingzoo.farama.org/
- PettingZoo Texas Hold'em No Limit: https://pettingzoo.farama.org/environments/classic/texas_holdem_no_limit/
- PettingZoo CleanRL PPO tutorial: https://pettingzoo.farama.org/tutorials/cleanrl/implementing_PPO/
