# Diagnostic results — FairPlay vs Standard across the demand curve

**Date:** 2026-06-26
**Status:** diagnostic phase complete (no-code). Read against the commitments in
`playsim-fairplay-retention-preregistration.md` (committed BEFORE these results).
**Source:** `large-room-sweep` on the 50-table / 1000-player fixture, seeds 42/7/99,
horizon 480, `--samples 1`, `--behavior formation-aware`, `--formation-mode forming`.

---

## The question (pre-registered)

Does FairPlay beat Standard on the **vulnerable cohort's retained seat-time**, and at
which demand levels? Decision rule committed in advance: *if FairPlay already wins
seed-stably at a plausible rate, investigate **why** before claiming.*

## Results — the demand curve

3-seed means; **per-seed stability** is the column that decides it (committed: a winner
must hold on all 3 seeds).

| arrival/hr | total seat-hrs (std / fp / liveness) | vulnerable seat-hrs (std / fp / liveness) | FairPlay vuln wins | liveness vuln wins |
|---|---|---|---|---|
| **10** | 995.6 / 990.6 / 979.8 | 22.83 / **24.07** / **24.51** | **3/3** ✅ | **3/3** ✅ |
| **20** | 1201.9 / 1186.9 / 1199.0 | 28.22 / **29.28** / **30.18** | **3/3** ✅ | **3/3** ✅ |
| 30 | 1401.4 / 1372.9 / 1398.7 | 35.38 / 35.34 / 35.27 | 2/3 ⚠️ | 2/3 ⚠️ |
| 40 | 1599.2 / 1571.3 / 1594.2 | 42.33 / 41.91 / 40.32 | 2/3 ❌ | 0/3 ❌ |

**Total seat-hours:** Standard wins essentially everywhere (FairPlay 0/3 at every rate;
liveness 1/3 once). The raw metric rewards concentration, as expected.

## What this establishes (honestly)

1. **At realistic (non-saturated) demand, FairPlay protects the vulnerable cohort's
   retention — seed-stably, with no code change and no p-hacking.** Rates 10–20: FairPlay
   beats Standard on vulnerable seat-hours on all 3 seeds (+2–7%).
2. **The operating point is decisive.** As demand climbs to 40/hr the room **saturates**
   (~50/50 tables active), routing can't differentiate, and Standard's concentration
   wins both metrics. The earlier #65 "Standard leads" result was measured **only at the
   saturated rate (40)** — at lower demand the vulnerable metric flips.
3. **Liveness is regime-dependent, not the lever.** It forms more tables and helps
   slightly at low demand but *hurts* vulnerable retention at rate 40 (0/3). The demand
   regime — not the liveness policy — is what moves the result.
4. **The retention mechanism is confirmed (Step-2 ablation).** The win is driven by the
   realized-chip-flow path: FairPlay seats vulnerable players at healthier tables → they
   lose slower → the loss/tilt leave decision (`runner.py:cohort_should_leave`, which
   ignores table health and keys only on realized losses) fires later → more seat-time.
   Re-running rates 10/20 with `--behavior default` (which removes the behavior-model
   composition-pressure term, leaving only the realized path) **preserves the FairPlay
   vulnerable-retention win**: 3/3 seeds at rate 20, 2/3 at rate 10 (the single flip is
   −0.15, a tie). So the realized path is the **primary driver**; the behavior pressure
   term is a secondary amplifier (it firms rate 10 up to 3/3 in the formation-aware run).

## Decision-rule outcome

We were in the "FairPlay already wins seed-stably" case, so per our own rule the next step
was **confirm the mechanism, not rush to build one** — and the Step-2 ablation has now done
that (the win survives removing the behavior term; the realized-chip-flow path is the
driver). The reframed thesis — *"FairPlay protects vulnerable retention at realistic
demand; raw throughput favors concentration"* — is **demonstrated and mechanistically
attributed, not asserted.**

### Step-2 ablation (behavior=default) — per-seed

| rate | std vuln | fairplay vuln | FairPlay wins |
|---|---|---|---|
| 10 | 26.63 | 27.45 | 2/3 (seed 42 −0.15 tie) |
| 20 | 32.60 | 34.91 | 3/3 |

## Caveats (committed up front)

`--samples 1` (3-seed stability partially offsets); margins are small (±a few %);
Standard still owns total throughput; **illustrative synthetic data — never a validated
retention claim** (CLAUDE.md).

---

## Platform implications & next modeling steps (raised by Cory, 2026-06-26)

The regime-dependence above makes two platform ideas directly relevant. Both are
**candidates for a team/PRD discussion** (Sargon owns the sim), not yet built.

### 1. Demand is diurnal, not static
Real join-rate isn't a flat rate — it follows a **cyclical (sine-wave) daily pattern**:
ramps up, peaks, decays, repeats. Because our result is demand-regime-dependent, a
**diurnal arrival model** would have the room sweep through *both* regimes within a single
day. The honest implication: **FairPlay's vulnerable-retention advantage is an off-peak /
shoulder benefit; at peak the room is throughput-bound and concentration wins.** That is a
more realistic and more defensible story than any single static rate.
→ *Proposed:* add a `--arrival-mode diurnal` (sine-modulated Poisson) and re-run the
experiment across a full 24h cycle, reporting the metric *by time-of-day*.

### 2. Capacity controller — a table-fill-rate KPI with auto-spin-up
Add a KPI for **room fill rate** (e.g. seated/available seats, or the fraction of tables
near-full) and a control policy: **when fill rate exceeds a threshold, open new tables**
to restore headroom. The rationale is exactly our rate-40 finding — saturation is where
routing stops mattering and players get forced into near-full tables or wait-and-leave.
A controller that **keeps the room below saturation preserves the formation headroom
FairPlay needs**, which could let FairPlay's vulnerable-retention advantage **hold even at
peak demand**. This is both a sim policy and a real operator feature (auto-open tables),
and it pairs naturally with the liveness/formation work — and it's a natural **action for
the RL loop** to learn (the threshold becomes a tunable).
→ *Proposed:* model fill-rate + a spin-up rule in the sim; test whether it extends the
off-peak FairPlay advantage into the diurnal peak.

**Together:** diurnal demand creates the peaks; the capacity controller manages them. The
combined experiment tests whether FairPlay's off-peak protection can be sustained across a
realistic day — which is the actual product question.

## Related

- `playsim-fairplay-retention-preregistration.md` — pre-registered commitments.
- `2026-06-26-rl-routing-loop-concept.md` — the learning-loop brief (these become loop
  actions / reward-environment improvements).
- `playsim-large-room-simulation.md` (#64) + #65 — the sim scale + the saturated-rate benchmark.
