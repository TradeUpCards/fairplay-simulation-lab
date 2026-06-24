# Decision — How (and where) AI generates poker play in FairPlay

> **Status: PROPOSED for team ratification · v2 (evolved from v1, framing clarified).** Source: a 5-phase
> deep-research run (21 claims verified 3-of-3 against primary sources), the project's hard rules, and a team
> direction to put **AI agents** in gameplay/simulation. Companion learning artifact:
> [`ai-hand-generation.html`](ai-hand-generation.html).
>
> **The decision in one line:** *Build **one agent-based simulator** (PokerKit environment, one agent per
> seat). Choose each agent's **brain** — seeded policy vs. live LLM — **per seat**, by whether *reasoning* is
> the product there. Run **two loops** on it: a deterministic **health/routing backtest** (the headline) and a
> scoped **LLM collusion** case (integrity). **Freeze every run** so the demo is reproducible.*

---

## 1. The question we researched

The team asked, reasonably: *the capstone "needs to incorporate AI" — could we use AI agents to generate
gameplay per archetype, then (a) test our scoring/integrity system and (b) see how our routing/health system
performs?* Anchored on the PHH dataset
([Zenodo 17136841](https://zenodo.org/records/17136841) · [phh-dataset repo](https://github.com/uoftcprg/phh-dataset)).

## 2. The mental model: one agent-based simulator, and its agents' brains

The earlier framing said "agents vs. policies" — that was misleading. **"Agent" does not mean "LLM."** A
poker table is an **environment**; each seat is an **agent**; the room over 8 hours is the **simulation**.
Pluribus, RLCard, and OpenSpiel are all "agents in an environment" — none are LLMs. So an **agent-based
environment simulator is the architecture, full stop.** That part isn't in question.

The only real choice is **what's inside each agent's head** — its *brain*, a function from game-state →
action. There are four sources, and **all four are still agents in the same simulator**:

| Agent brain | Deterministic? | Cost | Right for |
|---|---|---|---|
| **Heuristic rules** (hand-coded archetype) | Yes (seeded) | ~0 | most archetypes — hits target VPIP/PFR/aggression |
| **Equilibrium / RL** (CFR · RLCard · OpenSpiel · Deep-CFR/NFSP) | Yes (seeded) | Low | when you want bots that genuinely play *well* |
| **LLM + tools** (reasons in-persona, calls a solver) | No (unless frozen) | High | when the *reasoning / emergence* is the product (collusion) |
| **Raw LLM** (reasons, no tools) | No | High | rarely — plays badly ([ToolPoker](https://arxiv.org/abs/2602.00528)) |

**The thesis:** the architecture is fixed (agent-based sim); we **pick a brain per seat**, mixing them in one
table. Two project rules — *not* a preference about "agents" — constrain the choice:

1. **The demo must replay identically → freeze the run.** Whatever brains you use, generate the simulation
   **once, offline**, commit the trajectory, and the demo replays the file. Non-determinism only bites in the
   *live* path; freezing removes it. (This is `DECISIONS.md` D0-option-C's "frozen JSON.")
2. **The counterfactual is a controlled experiment → seeded brains for the bulk.** "FairPlay routing made
   tables healthier by Δ" is only valid if the Standard and FairPlay paths share seed/deck/intentions and
   differ *only* in the routing decision. A live LLM injects uncontrolled variance you can't attribute. So the
   health/routing loop uses **seeded** brains — not because "agents are bad," but because a controlled
   experiment needs reproducible inputs.

## 3. Decision evolution — v1 → v2

A history, not a retcon. The v1 reasoning still holds; what changed is the **brain of the
integrity-critical seats**.

| | **v1 — research-driven** | **v2 — this decision** |
|---|---|---|
| **Integrity-critical seats' brain** | Deterministic policy (LLM never plays) | **LLM + tools** (reasons + calls a solver) |
| **LLM role** | Explanation only (AI Investigator) | Explanation **+ one scoped gameplay case** |
| **Determinism** | Native | **Freeze-and-replay** (agents generate once offline, output committed) |

**What flipped, and why it's defensible:** (1) the team committed to AI agents in gameplay; (2) ToolPoker
shows raw LLMs fail but **tool-grounded** agents reach pro play; (3) freeze-replay reconciles any brain with
the determinism rule; (4) two LLM agents sharing a side-channel produce **emergent** collusion the scorer
catches — a story a scripted policy can't truthfully tell. **Nothing from v1 is thrown away** — the engine,
PHH calibration, freeze pattern, and detector wall all remain.

## 4. The two loops — and why each wants a different brain

The simulator serves **two distinct validation loops.** They're easy to conflate; they want different brains.

| | **Integrity loop** | **Health/routing loop** *(the headline)* |
|---|---|---|
| **Question** | Does the scorer *catch* bad behavior? | Does the router's seating *produce healthier tables*? |
| **Generate** | The colluding pair | The **whole table, all archetypes, over 8 hours** |
| **Measure** | `SOFT_PLAYS_AGAINST` fires from real play | Realized `Health(T)` — winnings concentration, recreational-loss velocity, retention, early breaks |
| **Validates** | The evidence / integrity engine | **`ΔHealth`, the router, the whole table-health thesis** |
| **Agent brain** | **LLM + tools** (emergence is the product) | **Seeded policies** (controlled experiment + statistical outcomes) |

The **health/routing loop is the closed-loop backtest of the product's core claim.** The router predicts
`ΔHealth` when it seats a player; the only way to know it was right is to **play the table out and measure
realized health**, then compare predicted vs. actual. Today `room_metrics_standard.json` vs
`room_metrics_fairplay.json` *assert* that divergence; the simulator *derives* it. This is the demo's third
link (Standard-vs-FairPlay 8-hour sim) made real, and the `Health(T)` outcome-terms payoff
[`simulator-signal-gap.md`](../graph/simulator-signal-gap.md) Addition 1 flagged.

> **⚠ The circularity guardrail (makes or breaks the backtest).** If the same model that *scores* health also
> *generates* the gameplay, the "validation" is a tautology — the router succeeds by construction. The
> generator's sense of who wins, loses, busts, and leaves must come from **independent first-principles poker
> economics** (actual chip flow from played hands, equity realized by the engine, EV extraction by skill) —
> **never from re-running `Health(T)`'s own formula.** Then realized health (measured bottom-up) is a genuine
> *independent* check on the router's top-down prediction. Same "derive, don't assert" discipline, applied to
> the *outcome* side.

## 5. The decision — the concrete per-seat assignment

| Layer | Agent brain | Why |
|---|---|---|
| **The 8-hour room & the Standard-vs-FairPlay counterfactual** | **Seeded policies** (heuristic; equilibrium/RL optional) | The headline routing backtest — needs a controlled, reproducible experiment |
| **The collusion showcase** (coordinated pair; optional bot-like) | **LLM + tools** (persona + CFR/equity solver) | The one place an LLM playing earns it: **emergent**, *derivable* collusion + the agentic-AI headline |
| Legal moves, state, equity, showdown | **PokerKit** (the environment / referee) | Agents *propose* actions; the engine enforces legality — no illegal/weird play |
| "Is this realistic?" | **PHH 21.6M-hand corpus** (distribution reference) | Validate generated play falls in-distribution — provable realism |
| Scenario direction · persona narration · evidence explanation | **LLM (non-authoritative)** incl. the AI Investigator (P4) | Reasoning/language is the product; never the detector, never live in scoring |

**Determinism for all of it:** generate once offline → commit `hand_events.json` / room metrics → demo
replays the frozen files. **Live agents sit behind a feature flag** for an optional "watch it generate"
view — never in the demo's reproducible hot path.

## 6. Why — the five facts (now *constraints*, not vetoes)

In v1 these argued *against* LLM gameplay; in v2 they **shape which brain goes where**. (Provenance: 1, 3
verified 3-0 in the research run; 1b, 5 verified directly vs. primary source.)

1. **No archetype labels — and almost nothing FairPlay needs.** PHH has no field for style/skill/archetype,
   nor account metadata, devices, relationships, session-health, or integrity labels. → *We author archetype
   behavior ourselves regardless of brain; with an LLM brain, the archetype is the **persona**.*
   *(arXiv 2312.11753v3 — verified 3-0 ×4.)*

   **1b. The corpus is the wrong shape.** ~20.3 GB / ~641.7M hands, but ~620M are heads-up/3-player **bot**
   hands; only **21.6M** are real-money multi-handed NLHE. → *Distribution reference only — never a sim.
   (verified vs. Zenodo API.)*

2. **The simulator must be seeded and reproducible** (`CLAUDE.md`). → ***Freeze-and-replay**, and **seeded
   brains** for the controlled counterfactual.*

3. **A deterministic engine already does the hard part.** PokerKit (MIT, >1M evals/s) is the **environment /
   referee** for every brain. *(arXiv 2308.07327 — verified 3-0 ×6.)*

4. **Our archetype targets are already fields we own** (`vpip`, `pfr`, `soft_play_delta`, …). → *They are the
   brain's **tuning targets** and the check that an archetype "fired."*

5. **Raw LLMs are weak players; tool-grounding fixes it.** PokerBench + ToolPoker; *contra:* PokerSkill
   (2605.30094). → *LLM-brained seats are **tool-grounded**, not raw. (verified vs. primary source.)*

## 7. The options we weighed (ranked)

| # | Approach | Determinism | Cost | Realism | Effort | Verdict |
|---|---|---|---|---|---|---|
| **★** | **Agent-based sim; seeded brains for the room/routing loop + LLM-brained collusion case; all frozen** | Full (frozen) | Med (once) | High where it matters | Med-High | **✅ Adopt — v2 decision** |
| **A** | Seeded brains *everywhere* (incl. a *scripted* pair); LLM only explains | Full | Negligible | Good | Medium | **Substrate & fallback** — the "clean compromise" |
| **B** | LLM-brained agents for **all** gameplay | Full (frozen) | High | High | High | Only if team insists — pays the cost/QA/iteration tax everywhere |
| **C** | **Raw** LLM brains (no solver tool) for canonical play | Frozen only | High | Weak/odd play | Low-Med | Reject for canonical play — flavor only |
| **D** | Fine-tune a sequence model on the 21.6M PHH hands | Hard | Train cost | Unproven | High | Reject — no labels, low ROI |
| **E** | Status quo — assert health/integrity signals as fields | Full | None | Can't prove signals fire | None | Demo-only fallback |

**★ over B:** LLM brains add nothing to the deterministic room/routing loop, and would *break* its controlled
experiment; scoping them to one case buys ~80% of the agentic-AI story for ~20% of the cost. **★ over A /
the compromise:** A is excellent and nearly identical, but its pair is *scripted* — ★ keeps one LLM-brained
case so the collusion is **emergent**. **★ degrades to A** cleanly if the team wants zero LLM-in-gameplay.

## 8. What this is NOT (scope guards)

- **Not** LLM brains in the room/routing loop. That loop is the controlled counterfactual — **seeded brains
  only**, or the "routing improved health" claim is invalid.
- **Not** live LLMs in the demo's reproducible path. Default is **frozen**; live is a feature-flagged view.
- **Not** the LLM as detector. Gameplay agents and the scorer are different components; the scorer derives
  signals from the frozen play, the Investigator only explains. The wall holds.
- **Not** generating health outcomes from the health model itself (the **circularity** trap — see §4).
- **Not** redistributing PHH *data* (CC-BY-4.0; attribution applies). **Not** a player-facing real-time coach
  (that's **RTA**, treated as cheating) — any sim is **offline / operator** training/demo.

## 9. Consequences

- **The headline becomes provable.** "Our routing makes tables healthier" stops being asserted in
  `room_metrics_*.json` and becomes a measured predicted-vs-realized `ΔHealth` result.
- **Honest integrity signals.** Drop `soft_play_delta` → recompute `SOFT_PLAYS_AGAINST` from the (frozen) play.
- **A real build cost**, bounded by scoping LLM brains to one case and freezing aggressively.
- **An iteration discipline** — changing a seeded scenario is instant; changing the LLM-brained case means
  re-generate + re-validate. Keep that case singular.

## 10. How to defend it — on two fronts

**Front 1 — the determinism skeptic ("don't put an LLM in gameplay"):**

| They say… | You say… |
|---|---|
| "An LLM brain breaks reproducibility." | "It doesn't touch the reproducible path. The agent generates **offline, once**; we commit the output; the demo replays the **frozen** file. Same pattern as `DECISIONS.md` D0-option-C." |
| "LLMs play bad poker." | "Raw ones do (ToolPoker). Our LLM-brained seats are **tool-grounded** — they call a CFR/equity solver, the research's own fix. Realism is checked vs. 21.6M PHH hands." |
| "Isn't the LLM now the detector?" | "No. The gameplay agent and the scorer are separate components. The scorer derives signals from frozen play; the Investigator only explains." |
| "Won't agents wreck the routing experiment?" | "That's why the **room/routing loop uses seeded brains** — a controlled experiment needs reproducible inputs. LLM brains are scoped to the one collusion case." |

**Front 2 — the maximalist ("use LLM agents for everything"):**

| They say… | You say… |
|---|---|
| "Make every seat an LLM agent." | "Agents are still agents with a seeded brain — that *is* the simulator. LLM brains add nothing to the room/routing loop, multiply cost/QA/iteration, and would break the controlled counterfactual. We scope them to where reasoning is the product." |
| "A rules engine isn't real AI." | "It's an agent-based multi-agent sim with tool-grounded LLM agents where it counts, plus the AI Investigator. Restraint is the sophistication for a responsible-AI integrity product." |

## 11. Open questions

1. **Which seeded brain for the room loop — heuristic or RL (RLCard/OpenSpiel)?** Heuristic ships fastest;
   RL plays more convincingly. Start heuristic.
2. **Does the live feature-flag view ship in the demo, or stay a dev tool?** Default: dev tool; canonical demo is frozen.
3. **Where do the independent health-outcome economics live** (the anti-circularity layer)? Confirm chip-flow /
   EV are computed from played hands, not from `Health(T)`.
4. **Operator- or player-facing training sim?** Operator/offline avoids the RTA line.

## 12. Sources (all primary, verified)

- PHH format & spec — arXiv [2312.11753](https://arxiv.org/abs/2312.11753) · [phh-std](https://github.com/uoftcprg/phh-std) (MIT) · [phh.readthedocs.io](https://phh.readthedocs.io/en/stable/)
- PHH dataset — [Zenodo 17136841](https://zenodo.org/records/17136841) ([API](https://zenodo.org/api/records/17136841)) / [13997158](https://zenodo.org/records/13997158) (CC-BY-4.0); **~20.3 GB / ~641.7M hands** — **~620M heads-up/3-player ACPC *bot* hands**, **21.6M** real-money HandHQ NLHE, 10k Pluribus, 83 WSOP 2023; anonymized, no style labels
- PokerKit (environment/referee) — arXiv [2308.07327](https://arxiv.org/abs/2308.07327) · [repo](https://github.com/uoftcprg/pokerkit) (MIT) · [PHH load/dump](https://pokerkit.readthedocs.io/en/stable/notation.html)
- Agent-brain lineage — [Slumbot2019](https://github.com/ericgjackson/slumbot2019) (CFR, MIT) · [RLCard](https://rlcard.org/) · OpenSpiel · Deep-CFR / NFSP
- LLM-poker evidence — PokerBench [2501.08328](https://arxiv.org/abs/2501.08328) (AAAI 2025) · **ToolPoker [2602.00528](https://arxiv.org/abs/2602.00528)** · *contra:* PokerSkill [2605.30094](https://arxiv.org/abs/2605.30094)
- Pluribus prior art — [Brown & Sandholm 2019](https://www.science.org/doi/10.1126/science.aay2400) · RTA — [PokerNews](https://www.pokernews.com/news/2020/10/what-is-meant-by-real-time-assistance-rta-38054.htm) · market: [GTO Wizard](https://gtowizard.com/)
- Project rules — [`CLAUDE.md`](../../CLAUDE.md), [`simulator-signal-gap.md`](../graph/simulator-signal-gap.md), [`DECISIONS.md`](../DECISIONS.md)
