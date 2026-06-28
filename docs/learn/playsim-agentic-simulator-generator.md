# Playsim Agentic Simulator Generator

**Tagline:** an AI experiment scientist for poker-room economics: the LLM proposes the next falsifiable simulation, the validator keeps it honest, and playsim produces deterministic evidence.

## Purpose

We want a repeatable loop where an orchestrator proposes the next simulation experiment, a runner executes deterministic sweeps, an evaluator scores the result, and a reporter writes the evidence. The goal is faster iteration over room economics, scoring sensitivity, roster size, capacity, and behavior assumptions while preserving reproducibility and avoiding p-hacking.

This is an **experiment controller**, not an autonomous code editor. The simulator stays deterministic. The orchestrator can choose from approved knobs and named scoring variants, but every run must be traceable to a config file, git commit, seed set, and generated report.

The first implementation now lives inside playsim as a bounded command:

```bash
python -m playsim.cli agentic \
  --spec experiments/standard-vs-fairplay-liveness-agentic.json \
  --out-dir out/agentic
```

The demo-worthy version adds an optional LLM planner:

```bash
OPENAI_API_KEY=... python -m playsim.cli agentic \
  --spec experiments/standard-vs-fairplay-liveness-agentic.json \
  --out-dir out/agentic-llm \
  --planner llm
```

In LLM mode, the model reads the experiment spec and evaluation, returns a
structured planning decision, and may propose the next complete experiment spec.
That proposal is not trusted automatically. The same local schema validator must
accept it before the next sweep can run.

It is scoped to the current project goal: **Standard vs FairPlay-liveness**.
FairPlay-liveness is treated as the new FairPlay policy for these experiments.
Manual sweeps still work; the agentic command adds a repeatable control loop
around them.

## Six-Step Loop

1. **Run baseline static capacity sweep.**
   Compare `standard` vs `fairplay_liveness` across table inventory, active tables, arrival rates, and seeds.

2. **Evaluate economics and mechanism.**
   Score total paid seat-hours, vulnerable seat-hours, demand drop rate, all seated departures, non-reseat simulator exits, re-seat departures, forming seats, wait balks, and table activations.

3. **If FairPlay wins but demand drop rises, sweep behavior knobs.**
   Test formation willingness, wait tolerance, decline behavior, and liveness thresholds before claiming an improvement.

4. **If wins depend on extra empty tables, run matched-saturation sweeps.**
   Hold starting utilization constant across table counts so the comparison is not just "looser room wins."

5. **If demand appears constrained, run roster-size or arrival-model sweeps.**
   Increase roster size only to answer whether finite demand is binding. Do not use a larger roster to hide poor routing or excessive balking.

6. **If scoring appears to reject realistic short-handed tables, run scoring sensitivity.**
   Use temporary, named scoring variants. Do not mutate canonical backend scoring during an exploratory sweep.

## Architecture

```text
Context Pack
  prior findings, approved knobs, assumptions, caveats, forbidden claims
        |
        v
Autonomy Contract
  metrics, budgets, allowed knobs, escalation gates
        |
        v
Sweep Runner
  executes deterministic playsim commands
  writes raw JSON/markdown artifacts
        |
        v
Evaluator
  computes deltas, win stability, rates, and guardrail violations
        |
        v
Reporter
  writes teammate-facing findings and next recommendation
        |
        v
Experiment Orchestrator
  rule mode: deterministic holdout planner
  llm mode: structured OpenAI planner proposes a spec
        |
        v
Spec Validator
  accepts only approved knobs and Standard vs FairPlay-liveness policies
  rejects invalid LLM proposals before another simulation runs
```

The important demo point is that this is not "a chatbot runs shell commands."
The system records the hypothesis first, runs deterministic evidence, evaluates
the mechanism and guardrails, writes a ledger, and only stops when the autonomy
contract tells it to stop.

The stronger demo point is that the LLM is used where it is valuable: reading
the result like an experimental scientist and deciding what would be most
diagnostic next. It is not used where it is dangerous: changing simulator code,
changing canonical scoring, or silently relaxing guardrails.

Dashboard generation is currently a separate sweep-explorer path. The agentic
loop writes result JSON that can be adapted into dashboards later, but v1 does
not automatically rebuild `playsim/out/sweep-explorer.html`.

## Experiment Spec Shape

```yaml
experiment: static_capacity
objective:
  primary: total_paid_seat_hours_delta
  secondary:
    - vulnerable_paid_seat_hours_delta
    - demand_drop_rate_delta
    - departure_rate_per_hour_delta
    - terminal_churn_rate_per_hour_delta
    - reseek_departure_rate_per_hour_delta
    - formation_activation_delta
    - estimated_avg_user_session_min

fixed:
  horizon_min: 480
  seeds: [42, 7, 99]
  behavior: formation-aware
  formation_mode: forming
  samples: 1
  policies:
    - standard
    - fairplay_liveness

sweep:
  tables: [40, 50, 60, 70]
  active_tables: [35]
  arrival_rate_per_hour: [10, 20, 30, 40]

autonomy_contract:
  max_experiments: 1
  max_sim_runs_per_experiment: 96
  escalate_if:
    estimated_avg_user_session_min: "> 150"
    demand_drop_rate_delta: "> 0.10"
    terminal_churn_rate_per_hour_delta: "> 2.0"
```

The checked-in starter spec is:

```text
playsim/experiments/standard-vs-fairplay-liveness-agentic.json
```

The generated artifacts are:

- `experiment-000-spec.json` — the exact hypothesis and knob contract.
- `experiment-000-results.json` — raw deterministic sweep results.
- `experiment-000-evaluation.json` — verdict, guardrails, and cell deltas.
- `experiment-000-planner.json` — rule/LLM planner rationale, risks, decision, and optional proposed spec.
- `experiment-000-report.md` — teammate-facing findings and provenance.
- `experiment-000-next-spec.json` — only when the run can continue safely.
- `ledger.json` — durable history of what the autonomous loop tried.

## LLM Planner Contract

The LLM planner is optional and default-off. Offline and CI runs use
`--planner rule`.

When enabled with `--planner llm`, the planner:

- Calls the OpenAI Responses API with Structured Outputs.
- Receives the current spec, evaluation summary, notable cells, allowed spec keys, and hard rules.
- Returns JSON with `decision`, `rationale`, `mechanism_read`, `risk_flags`, and `proposed_spec_json`.
- Can only continue if `proposed_spec_json` parses and passes the local `validate_spec()` gate.
- Writes the raw planning decision to `experiment-000-planner.json`.

The local validator enforces the current v1 scope:

- policies must be `standard` and `fairplay_liveness`;
- unknown top-level, fixed, sweep, objective, or guardrail keys fail closed;
- unsupported guardrail metrics fail closed;
- `active_tables` cannot exceed total `tables`;
- proposed sweeps cannot exceed `autonomy_contract.max_sim_runs_per_experiment`;
- the LLM cannot make code or scoring changes because those are not valid spec fields.

This gives the project its technical talking point:

> The AI is not running the simulator by vibes. It proposes falsifiable
> experiments under a contract, the code validates the proposal, and the
> deterministic simulator produces the evidence.

## Metric Glossary

- `departure_rate_per_hour`: all seated session exits before the horizon, including players who leave a table and then re-seat elsewhere.
- `terminal_churn_rate_per_hour`: non-horizon exits that do not enter the re-seat flow. This is a simulator exit bucket, not validated product churn. It can include positive or neutral reasons such as profit-taking or time-budget completion.
- `reseek_departure_rate_per_hour`: non-horizon exits that represent table movement or continued-play intent, such as table thinning, table break displacement, bad-fit decline, or boredom/low-action reseeking.
- `demand_drop_rate`: arrival balks plus wait balks divided by arrivals. This measures demand the simulator failed to convert into play or continued waiting.

The default hard gate uses `terminal_churn_rate_per_hour_delta`, not all
departures, because FairPlay-liveness intentionally creates more table movement
when it seeds and grows healthier tables. All-departure deltas remain visible as
a mechanism/tradeoff metric.

## Approved Knob Catalog

### Room / Demand Knobs

- `tables`
- `active_tables`
- `max_seats`
- `arrival_rate_per_hour`
- `horizon_min`
- `roster_size`
- `archetype_mix`
- `fixture_seed`
- `simulation_seeds`
- future: diurnal arrival curve

Use these to test operating regimes. Example question: does FairPlay need spare visible capacity, or does it still work at matched starting saturation?

### Behavior Knobs

- formation willingness by archetype
- wait tolerance by leave reason
- decline probability / decline strength
- pressure and fit leave weights
- user session distribution by archetype
- session-time scale / cap for 8-hour room runs
- profit-taking threshold
- boredom / low-action threshold

Use these to test whether player-side behavior assumptions are driving the result.

For 8-hour room simulations, user session duration should be much smaller than
the room horizon. The orchestrator should treat inflated average play time as a
model warning, then sweep explicit session-duration assumptions instead of
letting long-lived players dominate seat-hour economics. Session-duration
sweeps should report median, p25, p75, p90, and horizon-censored player counts
by archetype and policy.

Example:

```yaml
behavior:
  user_session_distribution:
    mode: archetype_lognormal
    scale: [0.5, 0.75, 1.0]
    cap_min: [90, 150, 240]
    preserve_reseat_budget: true
```

### Policy Knobs

- `fairplay_liveness.dealable_health_floor`
- `fairplay_liveness.forming_health_floor`
- candidate selection order, such as grow existing one-player forming table before seeding empty
- future: predicted fill probability gate
- future: max concurrent forming tables

Use these to test how the routing policy converts demand into active tables.

### Scoring Knobs

Scoring changes must be temporary, named variants inside analysis runs. They should not edit canonical backend defaults.

Examples:

```yaml
variants:
  - id: current
    scoring: {}

  - id: softer_short_table_fragility
    health:
      liveness_fragility_weight: 0.5

  - id: vulnerable_short_table_fit_neutral
    seating:
      vulnerable_short_table_penalty: 0.0

  - id: router_liveness_heavy
    router:
      fit_weight: 0.20
      health_weight: 0.55
      delta_health_weight: 0.25
```

## Roster-Size Rule

The orchestrator may propose increasing roster size, but only after diagnosing why.

Good reason:

> Demand is finite or exhausted, and we need to know whether results are constrained by player supply rather than routing.

Bad reason:

> FairPlay did not win, so make the pool larger until it does.

Recommended first roster sweep:

```text
tables: 50
active_tables: 35
arrival_rate_per_hour: [20, 40, 60]
roster_size: [500, 1000, 2000]
policies: standard, fairplay_liveness
metrics: total seat-hours, vulnerable seat-hours, demand drop rate, departures/hr, non-reseat exits/hr, re-seat departures/hr
```

## Scoring-Change Rule

The orchestrator can question the scoring model, but it should express that question as a named scoring sensitivity variant.

Good question:

> Does the current fragility score over-penalize healthy two- or three-handed tables?

Good experiment:

> Run `short_table_fragility_softened` vs `current` using the same seeds, arrival stream, and policies.

Bad experiment:

> Edit backend scoring until FairPlay wins.

## Evaluator Verdicts

The evaluator should return one of:

- `accept_for_holdout`: improves the primary metric across explored cells and no guardrail fires.
- `needs_followup`: mixed cells; the mechanism or operating regime matters.
- `reject_or_rethink`: fails the primary metric.
- `escalate`: an autonomy-contract guardrail fired, so the loop stops and surfaces the issue.

Example:

```text
Verdict: needs_followup
Reason:
- FairPlay-liveness wins total paid seat-hours in some cells.
- Vulnerable seat-hours improves in 13/16 cells.
- Demand drop rate rises sharply in loose-capacity regimes.
Next:
- Inspect demand drop, non-reseat exits, and re-seat departures.
- Sweep formation willingness and max concurrent forming tables.
- Then run matched-saturation confirmation if the mechanism still looks healthy.
```

In v1, one deliberate escalation gate is user-session realism. If the estimated
average user session is too long for an 8-hour room-day, the agent stops rather
than continuing to optimize around an unrealistic behavior assumption.

## Guardrails

- Every experiment spec is written before execution.
- LLM proposals are structured JSON and must pass local validation before execution.
- Every report includes git commit, seed set, fixture seed, and full knob config.
- Development seeds and confirmation seeds are separate.
- Generated wins are not product claims until calibrated against real traffic/churn data.
- Canonical backend scoring remains frozen unless a human explicitly promotes a tested variant.
- The simulator must stay deterministic and replayable.
- The orchestrator proposes specs and reports; it does not silently edit scoring code.

## Implemented v1

1. Departure, non-reseat-exit, re-seat-departure, and demand-drop metrics are emitted by `large-room-sweep` and shown in the sweep explorer.
2. `playsim/experiments/standard-vs-fairplay-liveness-agentic.json` defines the starter Standard vs FairPlay-liveness experiment.
3. `playsim/playsim/agentic.py` runs the bounded spec -> sweep -> evaluation -> report -> ledger loop.
4. `python -m playsim.cli agentic` provides reproducible local/demo execution.
5. `--planner rule` provides deterministic offline planning.
6. `--planner llm` adds an OpenAI-backed structured planner that proposes the next spec.
7. Specs are validated before execution; unknown guardrail metrics fail closed.
8. `max_sim_runs_per_experiment` prevents the LLM from widening a demo run into an expensive benchmark sweep.
9. Fixture paths include a deterministic fixture-config hash so changed roster/table configs cannot silently reuse stale fixtures.
10. Reports include git commit, spec hash, fixture seed, simulation seeds, and fixed/sweep config.
11. The loop stops on escalation, rejection, or mixed results in rule mode. LLM mode can propose a diagnostic follow-up, but only if validation accepts it.
12. `--max-iterations` is treated as a requested cap and cannot exceed `autonomy_contract.max_experiments`.
13. `playsim/out/agentic*/experiment-*-results.json` files are ingested by the existing sweep explorer.

## Planned Next

1. Add richer session-duration distribution outputs: median, p25, p75, p90, and horizon-censored counts by archetype and policy.
2. Add named scoring-variant execution without mutating canonical backend scoring.
3. Add matched-saturation experiment templates.
4. Add richer LLM planner policies for named matched-saturation, roster-size, and scoring-sensitivity templates once those spec fields exist.
